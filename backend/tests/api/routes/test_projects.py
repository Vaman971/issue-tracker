import pytest

from app.core.security import hash_password
from app.models.project_member import ProjectMember
from app.models.project import Project
from app.models.user import User, UserRole
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

async def create_user(db_session: AsyncSession, email: str, role: UserRole):
    user = User(
        email=email,
        hashed_password=hash_password("testpassword123"),
        role=role
    )

    db_session.add(user)

    await db_session.commit()
    await db_session.refresh(user)

    return user

async def login_user(email: str, client: AsyncClient):
    response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "testpassword123"
        }
    )

    return response.json()["access_token"]

@pytest.mark.asyncio
async def test_admin_can_create_project(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(
        db_session,
        "admin@example.com",
        UserRole.ADMIN
    )

    leader = await create_user(
        db_session,
        "leader@example.com",
        UserRole.PROJECT_LEADER,
    )

    token = await login_user(admin.email, client)

    response = await client.post(
        "/projects/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "Alpha Project",
            "description": "First project",
            "leader_id": leader.id
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Alpha Project"
    assert data["leader_id"] == leader.id

@pytest.mark.asyncio
async def test_admin_cannot_create_project_with_non_leader_user(
    client: AsyncClient,
    db_session: AsyncSession
):
    admin = await create_user(
        db_session,
        "admin2@example.com",
        UserRole.ADMIN
    )

    developer = await create_user(
        db_session,
        "developer@example.com",
        UserRole.DEVELOPER
    )

    token = await login_user(admin.email, client)

    response = await client.post(
        "/projects/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "Invalid Leader Project",
            "description": "This should fail",
            "leader_id": developer.id,
        },
    )

    assert response.status_code == 400

@pytest.mark.asyncio
async def test_project_leader_sees_only_their_projects(client: AsyncClient, db_session: AsyncSession):
    leader_one = await create_user(
        db_session,
        "leader1@example.com",
        UserRole.PROJECT_LEADER,
    )

    leader_two = await create_user(
        db_session,
        "leader2@example.com",
        UserRole.PROJECT_LEADER
    )

    project_one = Project(
        name="Leader one Project",
        description="Visible to leader one",
        leader_id=leader_one.id
    )

    project_two = Project(
        name = "Leader two Project",
        description="Visible to leader two",
        leader_id=leader_two.id
    )

    db_session.add_all([project_one, project_two])
    await db_session.commit()

    token = await login_user(leader_one.email, client)

    response = await client.get(
        "/projects/",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Leader one Project"

@pytest.mark.asyncio
async def test_project_member_sees_assigned_projects(
    client: AsyncClient,
    db_session: AsyncSession
):
    leader = await create_user(
        db_session,
        "leader-member@example.com",
        UserRole.PROJECT_LEADER,
    )

    viewer = await create_user(
        db_session,
        "viewer-member@example.com",
        UserRole.VIEWER,
    )

    visible_project = Project(
        name="Visible Member Project",
        description="Visible to member",
        leader_id=leader.id,
    )

    hidden_project = Project(
        name="Hidden Member Project",
        description="Not visible to member",
        leader_id=leader.id,
    )

    db_session.add_all([visible_project, hidden_project])
    await db_session.commit()
    await db_session.refresh(visible_project)
    await db_session.refresh(hidden_project)

    db_session.add(
        ProjectMember(
            project_id=visible_project.id,
            user_id=viewer.id,
        )
    )
    await db_session.commit()

    token = await login_user(viewer.email, client)

    response = await client.get(
        "/projects/",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Visible Member Project"
