import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.issue import Issue
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole

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

async def user_login(client: AsyncClient, email: str):
    response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "testpassword123"
        },
    )

    return response.json()["access_token"]

@pytest.mark.asyncio
async def test_member_sees_only_project_issues(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "leader@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "dev@example.com", UserRole.DEVELOPER)

    project_one = Project(name = "Project One", description=None, leader_id=leader.id)
    project_two = Project(name = "Project Two", description=None, leader_id=leader.id)

    db_session.add_all([project_one, project_two])
    await db_session.commit()
    await db_session.refresh(project_one)
    await db_session.refresh(project_two)

    project_member = ProjectMember(project_id=project_one.id, user_id=developer.id)
    db_session.add(project_member)

    await db_session.commit()
    await db_session.refresh(project_member)

    issue_one = Issue(
        title="Visible Issue",
        description=None,
        project_id=project_one.id,
        creator_id=developer.id,
    )

    issue_two =  Issue(
        title="Hidden Issue",
        description=None,
        project_id=project_two.id,
        creator_id=leader.id
    )

    db_session.add_all([issue_one, issue_two])
    await db_session.commit()
    await db_session.refresh(issue_one)
    await db_session.refresh(issue_two)

    token = await user_login(client, developer.email)

    response = await client.get(
        "/issues/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert data[0]["title"] == "Visible Issue"

@pytest.mark.asyncio
async def test_issue_pagination_limit(client : AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "admin@example.com", UserRole.ADMIN)

    project = Project(
        name="Pagination Project",
        description=None,
        leader_id=admin.id
    )

    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    issues = [
        Issue(
            title=f"Issue {index}",
            description=None,
            project_id=project.id,
            creator_id=admin.id
        ) for index in range(5)
    ]

    db_session.add_all(issues)
    await db_session.commit()

    for issue in issues:
        await db_session.refresh(issue)

    token = await user_login(client, admin.email)

    response = await client.get(
        "/issues/?skip=0&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

@pytest.mark.asyncio
async def test_viewer_member_cannot_create_issue(
    client: AsyncClient,
    db_session: AsyncSession
):
    leader = await create_user(db_session, "leader3@example.com", UserRole.PROJECT_LEADER)
    viewer = await create_user(db_session, "viewer@example.com", UserRole.VIEWER)

    project = Project(
        name="Viewer Project",
        description=None,
        leader_id=leader.id
    )

    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(
        ProjectMember(
            project_id=project.id,
            user_id=viewer.id
        )
    )

    await db_session.commit()

    token = await user_login(client, viewer.email)

    response = await client.post(
        "/issues/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Viewer issue",
            "description": "Should not be allowed",
            "project_id": project.id,
        },
    )

    assert response.status_code == 403

@pytest.mark.asyncio
async def test_assignee_must_be_project_member(
    client: AsyncClient,
    db_session: AsyncSession
):
    viewer = await create_user(db_session, "viewer@example.com", UserRole.VIEWER)
    leader = await create_user(db_session, "leader4@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "outside-dev@example.com", UserRole.DEVELOPER)

    project = Project(
        name="Assignee Project",
        description=None,
        leader_id=leader.id
    )

    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await user_login(client, viewer.email)

    response = await client.post(
        "/issues/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Invalid assignee",
            "description": None,
            "project_id": project.id,
            "assignee_id": developer.id,
        },
    )

    assert response.status_code == 403

@pytest.mark.asyncio
async def test_developer_member_can_only_update_issue_status(
    client: AsyncClient,
    db_session: AsyncSession
):
    leader = await create_user(db_session, "leader5@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "dev5@example.com", UserRole.DEVELOPER)

    project = Project(
        name="Status Only Project",
        description=None,
        leader_id=leader.id
    )

    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(
        ProjectMember(
            project_id=project.id,
            user_id=developer.id
        )
    )
    await db_session.commit()

    issue = Issue(
        title="Original title",
        description="Original description",
        project_id=project.id,
        creator_id=leader.id,
    )

    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, developer.email)

    response = await client.patch(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Developer changed title"
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Project members can only update issue status"
