from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.core.tokens import create_access_token, create_refresh_token, decode_refresh_token, utc_now
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.refresh_token import RefreshToken
from app.api.deps import get_current_user
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenResponse,
    RegisterRequest,
    TokenPairResponse
)
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    existing_user_result = await db.execute(select(User).where(User.email == payload.email))

    existing_user = existing_user_result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    user = User(
        email = payload.email,
        hashed_password = hash_password(payload.password),
        role=UserRole.VIEWER
    )

    db.add(user)

    await db.commit()
    await db.refresh(user)

    return user

@router.post(
    "/login",
    response_model=TokenPairResponse,
)
async def login_user(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    user_result = await db.execute(select(User).where(User.email == payload.email))

    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if not verify_password(
        payload.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    access_token = create_access_token(user.id, user.role.value)

    refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(user_id=user.id)

    db.add(
        RefreshToken(
            jti = refresh_jti,
            user_id = user.id,
            expires_at=refresh_expires_at
        )
    )

    await db.commit()

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post(path="/refresh", response_model=TokenPairResponse)
async def refresh_access_token(
    payload: RefreshTokenResponse,
    db: AsyncSession = Depends(get_db)
):
    try:
        decoded_token = decode_refresh_token(payload.refresh_token)

        token_type = decoded_token.get("type")
        user_id = decoded_token.get("sub")
        refresh_jti = decoded_token.get("jti")

        if token_type != "refresh" or user_id is None or refresh_jti is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    token_result = await db.execute(select(RefreshToken).where(RefreshToken.jti == refresh_jti))

    stored_token = token_result.scalar_one_or_none()
    now = utc_now()

    if stored_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked"
        )

    if stored_token.user_id != int(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    if stored_token.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has already been used"
        )

    if stored_token.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired"
        )

    # we fetch the user from the database still and do not rely on the user_id retured by the token as db is the source of truth at the end
    user_result = await db.execute(select(User).where(User.id == int(user_id)))

    user = user_result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code= status.HTTP_401_UNAUTHORIZED,
            detail=" User no longer exists"
        )

    new_access_token = create_access_token(
        user_id=user.id,
        role=user.role.value
    )

    # create new refresh token on cycle, as one refresh token should be used only once for generating access token
    new_refresh_token, new_refresh_jti, new_refresh_expires_at = create_refresh_token(
        user_id=user.id
    )

    # expire the stored token
    stored_token.revoked_at  = now
    stored_token.replaced_by_jti = new_refresh_jti

    db.add(
        RefreshToken(
            jti = new_refresh_jti,
            user_id=user.id,
            expires_at=new_refresh_expires_at,
        )
    )

    # will refresh the database
    await db.commit()

    return TokenPairResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )

@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role.value,
    }