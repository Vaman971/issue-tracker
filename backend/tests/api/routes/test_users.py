import io

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Helpers shared with original tests
# ---------------------------------------------------------------------------

async def create_user(db_session: AsyncSession, email: str, role: UserRole, password: str = "Password123"):
    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
        is_email_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def login_user(client: AsyncClient, email: str, password: str = "Password123"):
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


async def _register(client, email, password="Password123"):
    resp = await client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Original cache test (kept)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_users_list_is_cached_and_invalidated_after_role_update(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis,
):
    admin = await create_user(db_session, "admin-cache@example.com", UserRole.ADMIN)
    developer = await create_user(db_session, "dev-cache@example.com", UserRole.DEVELOPER)

    token = await login_user(client, admin.email)

    list_resp = await client.get("/users/", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.status_code == 200
    assert any(key.startswith("users:list:") for key in fake_redis.store)

    update_resp = await client.patch(
        f"/users/{developer.id}/role",
        json={"role": "qa"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_resp.status_code == 200
    assert not any(key.startswith("users:list:") for key in fake_redis.store)


# ---------------------------------------------------------------------------
# List project leaders (GET /users/leaders)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_leaders_returns_only_eligible_roles(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "ul-admin@example.com", UserRole.ADMIN)
    await create_user(db_session, "ul-leader@example.com", UserRole.PROJECT_LEADER)
    await create_user(db_session, "ul-dev@example.com", UserRole.DEVELOPER)
    await create_user(db_session, "ul-qa@example.com", UserRole.QA)

    token = await login_user(client, admin.email)
    resp = await client.get("/users/leaders", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    roles = {u["role"] for u in resp.json()}
    assert roles <= {"admin", "project_leader"}, f"Unexpected roles in response: {roles}"

    emails = {u["email"] for u in resp.json()}
    assert "ul-dev@example.com" not in emails
    assert "ul-qa@example.com" not in emails


@pytest.mark.asyncio
async def test_list_leaders_non_admin_forbidden(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "ul-notadmin@example.com", UserRole.PROJECT_LEADER)
    token = await login_user(client, leader.email)
    resp = await client.get("/users/leaders", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_leaders_excludes_inactive(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "ul-adm2@example.com", UserRole.ADMIN)
    inactive = User(
        email="ul-inactive-leader@example.com",
        hashed_password=hash_password("Password123"),
        role=UserRole.PROJECT_LEADER,
        is_active=False,
        is_email_verified=False,
    )
    db_session.add(inactive)
    await db_session.commit()

    token = await login_user(client, admin.email)
    resp = await client.get("/users/leaders", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert "ul-inactive-leader@example.com" not in emails


# ---------------------------------------------------------------------------
# List users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_users_requires_admin(client: AsyncClient, db_session: AsyncSession):
    viewer = await create_user(db_session, "viewer-list@example.com", UserRole.VIEWER)
    token = await login_user(client, viewer.email)
    resp = await client.get("/users/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_as_admin(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "admin-list@example.com", UserRole.ADMIN)
    token = await login_user(client, admin.email)
    resp = await client.get("/users/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Update role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_user_role(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "admin-role@example.com", UserRole.ADMIN)
    target = await create_user(db_session, "target-role@example.com", UserRole.VIEWER)
    token = await login_user(client, admin.email)

    resp = await client.patch(
        f"/users/{target.id}/role",
        json={"role": "developer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "developer"


@pytest.mark.asyncio
async def test_update_role_not_found(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "admin-404@example.com", UserRole.ADMIN)
    token = await login_user(client, admin.email)
    resp = await client.patch(
        "/users/99999/role",
        json={"role": "developer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Activate / deactivate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deactivate_blocks_login(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "admin-deact@example.com", UserRole.ADMIN)
    target = await create_user(db_session, "deact-target@example.com", UserRole.VIEWER)
    token = await login_user(client, admin.email)

    deact = await client.patch(
        f"/users/{target.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    login_resp = await client.post(
        "/auth/login", json={"email": "deact-target@example.com", "password": "Password123"}
    )
    assert login_resp.status_code == 403


@pytest.mark.asyncio
async def test_reactivate_allows_login(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "admin-react@example.com", UserRole.ADMIN)
    target = await create_user(db_session, "react-target@example.com", UserRole.VIEWER)
    token = await login_user(client, admin.email)

    await client.patch(f"/users/{target.id}/deactivate", headers={"Authorization": f"Bearer {token}"})
    await client.patch(f"/users/{target.id}/activate", headers={"Authorization": f"Bearer {token}"})

    login_resp = await client.post(
        "/auth/login", json={"email": "react-target@example.com", "password": "Password123"}
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_self(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "selfdeact@example.com", UserRole.ADMIN)
    token = await login_user(client, admin.email)
    resp = await client.patch(
        f"/users/{admin.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Profile update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_my_profile(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session, "profile-me@example.com", UserRole.VIEWER)
    token = await login_user(client, user.email)

    resp = await client.patch(
        "/users/me",
        json={"full_name": "Jane Doe"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Jane Doe"


# ---------------------------------------------------------------------------
# Avatar upload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_avatar_png(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session, "avatar-up@example.com", UserRole.VIEWER)
    token = await login_user(client, user.email)

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    resp = await client.post(
        "/users/me/avatar",
        files={"file": ("avatar.png", io.BytesIO(png_bytes), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["avatar_key"] is not None


@pytest.mark.asyncio
async def test_upload_avatar_disallowed_type(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session, "bad-avatar@example.com", UserRole.VIEWER)
    token = await login_user(client, user.email)

    resp = await client.post(
        "/users/me/avatar",
        files={"file": ("script.sh", io.BytesIO(b"#!/bin/bash"), "application/x-sh")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Admin cannot change their own role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_cannot_change_own_role(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "self-role-admin@example.com", UserRole.ADMIN)
    token = await login_user(client, admin.email)

    resp = await client.patch(
        f"/users/{admin.id}/role",
        json={"role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "own role" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Max admin limit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cannot_promote_to_admin_when_limit_reached(
    client: AsyncClient, db_session: AsyncSession
):
    """When MAX_ADMINS=1 and one admin exists, promoting another user to admin is blocked."""
    admin = await create_user(db_session, "maxadm-admin@example.com", UserRole.ADMIN)
    target = await create_user(db_session, "maxadm-target@example.com", UserRole.VIEWER)

    token = await login_user(client, admin.email)

    resp = await client.patch(
        f"/users/{target.id}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "admin" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_can_change_other_user_role(
    client: AsyncClient, db_session: AsyncSession
):
    """Admin can change a non-admin user's role freely (e.g. viewer → developer)."""
    admin = await create_user(db_session, "maxadm2-admin@example.com", UserRole.ADMIN)
    target = await create_user(db_session, "maxadm2-target@example.com", UserRole.VIEWER)

    token = await login_user(client, admin.email)

    resp = await client.patch(
        f"/users/{target.id}/role",
        json={"role": "developer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "developer"
