import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import rate_limit as rate_limit_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register(client, email="test@example.com", password="Password123", full_name=None):
    body = {"email": email, "password": password}
    if full_name:
        body["full_name"] = full_name
    return await client.post("/auth/register", json=body)


async def _login(client, email="test@example.com", password="Password123"):
    return await client.post("/auth/login", json={"email": email, "password": password})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await _register(client)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "viewer"
    assert data["is_email_verified"] is False
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_with_full_name(client: AsyncClient):
    resp = await _register(client, full_name="Alice Smith")
    assert resp.status_code == 201
    assert resp.json()["full_name"] == "Alice Smith"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await _register(client)
    resp = await _register(client)
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    resp = await client.post("/auth/register", json={"email": "a@b.com", "password": "short"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await _register(client, email="login@example.com")
    resp = await _login(client, email="login@example.com")
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await _register(client, email="wrong@example.com")
    resp = await _login(client, email="wrong@example.com", password="BadPassword1")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient):
    resp = await _login(client, email="nobody@example.com")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Refresh token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient):
    await _register(client, email="refresh@example.com")
    login = await _login(client, email="refresh@example.com")
    old_rt = login.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": old_rt})
    assert resp.status_code == 200
    assert resp.json()["refresh_token"] != old_rt


@pytest.mark.asyncio
async def test_refresh_token_reuse_rejected(client: AsyncClient):
    await _register(client, email="reuse@example.com")
    login = await _login(client, email="reuse@example.com")
    old_rt = login.json()["refresh_token"]
    await client.post("/auth/refresh", json={"refresh_token": old_rt})
    resp = await client.post("/auth/refresh", json={"refresh_token": old_rt})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    await _register(client, email="me@example.com")
    login = await _login(client, email="me@example.com")
    token = login.json()["access_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_get_me_no_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_email_success(client: AsyncClient, db_session: AsyncSession):
    await _register(client, email="verify@example.com")

    from app.models.email_verification import EmailVerificationToken
    result = await db_session.execute(
        select(EmailVerificationToken).order_by(EmailVerificationToken.id.desc())
    )
    record = result.scalars().first()
    assert record is not None

    # Reconstruct the raw token by generating a matching one is impossible;
    # instead expose the hash and reverse-engineer — we store the hash, not the raw token.
    # For tests we create a fresh token directly.
    raw = secrets.token_urlsafe(32)
    record.token_hash = hashlib.sha256(raw.encode()).hexdigest()
    record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    await db_session.commit()

    resp = await client.post("/auth/verify-email", json={"token": raw})
    assert resp.status_code == 200
    assert "verified" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient):
    resp = await client.post("/auth/verify-email", json={"token": "totally-invalid-token"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_expired_token(client: AsyncClient, db_session: AsyncSession):
    await _register(client, email="expired@example.com")

    from app.models.email_verification import EmailVerificationToken
    result = await db_session.execute(
        select(EmailVerificationToken).order_by(EmailVerificationToken.id.desc())
    )
    record = result.scalars().first()
    assert record is not None

    raw = secrets.token_urlsafe(32)
    record.token_hash = hashlib.sha256(raw.encode()).hexdigest()
    record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    await db_session.commit()

    resp = await client.post("/auth/verify-email", json={"token": raw})
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Forgot / reset password
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_forgot_password_always_returns_200(client: AsyncClient):
    resp = await client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_success(client: AsyncClient, db_session: AsyncSession):
    await _register(client, email="reset@example.com")

    await client.post("/auth/forgot-password", json={"email": "reset@example.com"})

    from app.models.password_reset import PasswordResetToken
    result = await db_session.execute(
        select(PasswordResetToken).order_by(PasswordResetToken.id.desc())
    )
    record = result.scalars().first()
    assert record is not None

    raw = secrets.token_urlsafe(32)
    record.token_hash = hashlib.sha256(raw.encode()).hexdigest()
    record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    await db_session.commit()

    resp = await client.post(
        "/auth/reset-password", json={"token": raw, "new_password": "NewPassword99"}
    )
    assert resp.status_code == 200

    # Old password should no longer work
    old_login = await _login(client, email="reset@example.com", password="Password123")
    assert old_login.status_code == 401

    # New password should work
    new_login = await _login(client, email="reset@example.com", password="NewPassword99")
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient):
    resp = await client.post(
        "/auth/reset-password", json={"token": "bad-token", "new_password": "NewPassword99"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_token_reuse_rejected(client: AsyncClient, db_session: AsyncSession):
    await _register(client, email="reuse-reset@example.com")
    await client.post("/auth/forgot-password", json={"email": "reuse-reset@example.com"})

    from app.models.password_reset import PasswordResetToken
    result = await db_session.execute(
        select(PasswordResetToken).order_by(PasswordResetToken.id.desc())
    )
    record = result.scalars().first()
    raw = secrets.token_urlsafe(32)
    record.token_hash = hashlib.sha256(raw.encode()).hexdigest()
    record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    await db_session.commit()

    await client.post("/auth/reset-password", json={"token": raw, "new_password": "NewPass99"})
    resp = await client.post("/auth/reset-password", json={"token": raw, "new_password": "AnotherPass99"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Change password (authenticated)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient):
    await _register(client, email="change@example.com")
    login = await _login(client, email="change@example.com")
    token = login.json()["access_token"]

    resp = await client.post(
        "/auth/change-password",
        json={"current_password": "Password123", "new_password": "Changed456!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    new_login = await _login(client, email="change@example.com", password="Changed456!")
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient):
    await _register(client, email="changefail@example.com")
    login = await _login(client, email="changefail@example.com")
    token = login.json()["access_token"]

    resp = await client.post(
        "/auth/change-password",
        json={"current_password": "WrongCurrent1", "new_password": "New456!!1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_change_password_same_as_current(client: AsyncClient):
    await _register(client, email="samepass@example.com")
    login = await _login(client, email="samepass@example.com")
    token = login.json()["access_token"]

    resp = await client.post(
        "/auth/change-password",
        json={"current_password": "Password123", "new_password": "Password123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_rate_limit(client: AsyncClient):
    for _ in range(2):
        await _login(client, email="rl@example.com", password="wrongpassword1")
    resp = await _login(client, email="rl@example.com", password="wrongpassword1")
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_register_rate_limit(client: AsyncClient):
    await _register(client, email="rl2@example.com")
    for _ in range(2):
        await _register(client, email="rl2@example.com")
    resp = await _register(client, email="rl2@example.com")
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_fails_open_when_redis_unavailable(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _register(client, email="failopen@example.com")
    monkeypatch.setattr(rate_limit_service, "get_redis_client", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    resp = await _login(client, email="failopen@example.com")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Resend verification (Bug fix: was 422 because frontend sent no body)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resend_verification_requires_auth(client: AsyncClient):
    """Unauthenticated request must be rejected — endpoint now requires JWT."""
    resp = await client.post("/auth/resend-verification")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_resend_verification_creates_new_token_for_unverified_user(
    client: AsyncClient, db_session: AsyncSession
):
    """Authenticated unverified user receives a 200 and a new DB token is created."""
    await _register(client, email="resend@example.com")
    login = await _login(client, email="resend@example.com")
    token = login.json()["access_token"]

    from app.models.email_verification import EmailVerificationToken
    before_count_result = await db_session.execute(select(EmailVerificationToken))
    before_count = len(before_count_result.scalars().all())

    resp = await client.post(
        "/auth/resend-verification",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "verification link" in resp.json()["message"].lower()

    after_count_result = await db_session.execute(select(EmailVerificationToken))
    after_count = len(after_count_result.scalars().all())
    assert after_count == before_count + 1


@pytest.mark.asyncio
async def test_resend_verification_noop_for_verified_user(
    client: AsyncClient, db_session: AsyncSession
):
    """Already-verified user gets 200 but no new token is inserted."""
    await _register(client, email="verified@example.com")
    login = await _login(client, email="verified@example.com")
    token = login.json()["access_token"]

    # Mark the user as verified directly in the DB
    from app.models.user import User
    result = await db_session.execute(select(User).where(User.email == "verified@example.com"))
    user = result.scalar_one()
    user.is_email_verified = True
    await db_session.commit()

    from app.models.email_verification import EmailVerificationToken
    before_count_result = await db_session.execute(select(EmailVerificationToken))
    before_count = len(before_count_result.scalars().all())

    resp = await client.post(
        "/auth/resend-verification",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    after_count_result = await db_session.execute(select(EmailVerificationToken))
    after_count = len(after_count_result.scalars().all())
    assert after_count == before_count  # no new token created
