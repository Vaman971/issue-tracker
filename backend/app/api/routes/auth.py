import hashlib
import logging
import secrets
import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.core.tokens import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    utc_now,
)
from app.db.session import get_db
from app.models.email_verification import EmailVerificationToken
from app.models.password_reset import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshTokenResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPairResponse,
    VerifyEmailRequest,
)
from app.schemas.user import UserRead
from app.services.rate_limit import (
    build_rate_limit_key,
    enforce_rate_limit,
    reset_rate_limit,
)
from app.services.email import send_password_reset
from app.services.email import send_email_verification

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _dispatch_password_reset_email(to: str, token: str, full_name: str | None) -> None:

    # In dev mode skip Celery entirely — task.delay() silently queues to Redis
    # but no worker is running, so the email would never be sent/logged.
    if not settings.EMAILS_ENABLED:
        try:
            asyncio.run(send_password_reset(to=to, token=token, full_name=full_name))
        except Exception:
            logger.exception("Failed to send password reset email to %s", to)
        return

    try:
        from app.worker.tasks import send_password_reset_email as celery_task
        celery_task.delay(to=to, token=token, full_name=full_name)  # type: ignore[attr-defined]
    except Exception:
        logger.warning("Celery unavailable; sending reset email inline")
        try:
            asyncio.run(send_password_reset(to=to, token=token, full_name=full_name))
        except Exception:
            logger.exception("Failed to send password reset email to %s", to)



def _dispatch_verification_email(to: str, token: str, full_name: str | None) -> None:

    # In dev mode skip Celery entirely — task.delay() silently queues to Redis
    # but no worker is running, so the email would never be sent/logged.
    if not settings.EMAILS_ENABLED:
        try:
            asyncio.run(send_email_verification(to=to, token=token, full_name=full_name))
        except Exception:
            logger.exception("Failed to send verification email to %s", to)
        return

    try:
        from app.worker.tasks import send_verification_email as celery_task
        celery_task.delay(to=to, token=token, full_name=full_name)  # type: ignore[attr-defined]
    except Exception:
        logger.warning("Celery unavailable; sending verification email inline")
        try:
            asyncio.run(send_email_verification(to=to, token=token, full_name=full_name))
        except Exception:
            logger.exception("Failed to send verification email to %s", to)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: RegisterRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    client_ip = _get_client_ip(request)
    rate_limit_key = build_rate_limit_key("auth", "register", client_ip, payload.email)

    await enforce_rate_limit(
        key=rate_limit_key,
        max_attempts=settings.AUTH_RATE_LIMIT_REGISTER_MAX_ATTEMPTS,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
        detail="Too many registration attempts. Please try again later.",
    )

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.VIEWER,
        full_name=payload.full_name,
        is_active=True,
        is_email_verified=False,
    )
    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    await db.refresh(user)

    # Create email verification token
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = _utc_now() + timedelta(hours=settings.EMAIL_VERIFY_TOKEN_EXPIRES_HOURS)

    db.add(EmailVerificationToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()

    # Queue email in background (Celery task)
    background_tasks.add_task(
        _dispatch_verification_email,
        to=user.email,
        token=raw_token,
        full_name=user.full_name,
    )

    await reset_rate_limit(rate_limit_key)
    return user

# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    token_hash = _hash_token(payload.token)
    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    now = _utc_now()

    if record is None or record.verified_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or already used token")

    if record.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token has expired")

    record.verified_at = now
    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.is_email_verified = True

    await db.commit()
    return MessageResponse(message="Email verified successfully")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client_ip = _get_client_ip(request)
    rate_limit_key = build_rate_limit_key("auth", "resend-verify", client_ip, current_user.email)

    await enforce_rate_limit(
        key=rate_limit_key,
        max_attempts=3,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
        detail="Too many resend requests. Please try again later.",
    )

    if not current_user.is_email_verified:
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = _utc_now() + timedelta(hours=settings.EMAIL_VERIFY_TOKEN_EXPIRES_HOURS)

        db.add(EmailVerificationToken(user_id=current_user.id, token_hash=token_hash, expires_at=expires_at))
        await db.commit()

        background_tasks.add_task(
            _dispatch_verification_email,
            to=current_user.email,
            token=raw_token,
            full_name=current_user.full_name,
        )

    return MessageResponse(message="If your email is not yet verified, a new verification link has been sent.")


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenPairResponse)
async def login_user(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    client_ip = _get_client_ip(request)
    rate_limit_key = build_rate_limit_key("auth", "login", client_ip, payload.email)

    await enforce_rate_limit(
        key=rate_limit_key,
        max_attempts=settings.AUTH_RATE_LIMIT_LOGIN_MAX_ATTEMPTS,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
        detail="Too many login attempts. Please try again later.",
    )

    user_result = await db.execute(select(User).where(User.email == payload.email))
    user = user_result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token = create_access_token(user.id, user.role.value)
    refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(user_id=user.id)

    db.add(RefreshToken(jti=refresh_jti, user_id=user.id, expires_at=refresh_expires_at))
    await db.commit()
    await reset_rate_limit(rate_limit_key)

    return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_access_token(
    payload: RefreshTokenResponse,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    client_ip = _get_client_ip(request)
    rate_limit_key = build_rate_limit_key("auth", "refresh", client_ip, payload.refresh_token)

    await enforce_rate_limit(
        key=rate_limit_key,
        max_attempts=settings.AUTH_RATE_LIMIT_REFRESH_MAX_ATTEMPTS,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
        detail="Too many refresh attempts. Please try again later.",
    )

    try:
        decoded_token = decode_refresh_token(payload.refresh_token)
        token_type = decoded_token.get("type")
        user_id = decoded_token.get("sub")
        refresh_jti = decoded_token.get("jti")

        if token_type != "refresh" or user_id is None or refresh_jti is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    token_result = await db.execute(select(RefreshToken).where(RefreshToken.jti == refresh_jti))
    stored_token = token_result.scalar_one_or_none()
    now = utc_now()

    if stored_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    if stored_token.user_id != int(user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if stored_token.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has already been used")

    if stored_token.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired")

    user_result = await db.execute(select(User).where(User.id == int(user_id)))
    user = user_result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")

    new_access_token = create_access_token(user_id=user.id, role=user.role.value)
    new_refresh_token, new_refresh_jti, new_refresh_expires_at = create_refresh_token(user_id=user.id)

    stored_token.revoked_at = now
    stored_token.replaced_by_jti = new_refresh_jti

    db.add(RefreshToken(jti=new_refresh_jti, user_id=user.id, expires_at=new_refresh_expires_at))
    await db.commit()
    await reset_rate_limit(rate_limit_key)

    return TokenPairResponse(access_token=new_access_token, refresh_token=new_refresh_token)


# ---------------------------------------------------------------------------
# Current user
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# Change password (authenticated)
# ---------------------------------------------------------------------------

@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must differ from current")

    current_user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return MessageResponse(message="Password changed successfully")


# ---------------------------------------------------------------------------
# Forgot / reset password (unauthenticated)
# ---------------------------------------------------------------------------

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    client_ip = _get_client_ip(request)
    rate_limit_key = build_rate_limit_key("auth", "forgot-password", client_ip, payload.email)

    await enforce_rate_limit(
        key=rate_limit_key,
        max_attempts=3,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
        detail="Too many password reset requests. Please try again later.",
    )

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Always return success — prevents email enumeration
    if user and user.is_active:
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = _utc_now() + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRES_HOURS)

        db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
        await db.commit()

        background_tasks.add_task(
            _dispatch_password_reset_email,
            to=user.email,
            token=raw_token,
            full_name=user.full_name,
        )

    return MessageResponse(message="If your email is registered, a password reset link has been sent.")



@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    token_hash = _hash_token(payload.token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()
    now = _utc_now()

    if record is None or record.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or already used token")

    if record.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token has expired")

    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    user.hashed_password = hash_password(payload.new_password)
    record.used_at = now
    await db.commit()

    return MessageResponse(message="Password reset successfully")
