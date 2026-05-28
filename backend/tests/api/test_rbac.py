import pytest

from app.core.security import hash_password
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole

async def create_user(
    email: str,
    password: str,
    role: UserRole,
    db_session: AsyncSession
):
    user = User(
        email = email,
        hashed_password = hash_password(password),
        role=role,
    )

    db_session.add(user)

    await db_session.commit()

@pytest.mark.asyncio
async def test_viewer_cannot_access_admin_dashboard(client: AsyncClient, db_session: AsyncSession):
    await create_user(
        email="viewer@example.com",
        password="testpassword@123",
        role=UserRole.VIEWER,
        db_session=db_session
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "viewer@example.com",
            "password": "testpassword@123"
        },
    )

    tokens = login_response.json()
    access_token = tokens["access_token"]

    response = await client.get(
        "/admin/dashboard",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    assert response.status_code == 403

@pytest.mark.asyncio
async def test_admin_can_access_admin_dashboard(client: AsyncClient, db_session: AsyncSession):
    await create_user(
        email="admin@example.com",
        password="testpassword123",
        role=UserRole.ADMIN,
        db_session = db_session
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "admin@example.com",
            "password": "testpassword123"
        },
    )

    tokens = login_response.json()
    access_token = tokens["access_token"]

    response = await client.get(
        "/admin/dashboard",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["role"] == "admin"