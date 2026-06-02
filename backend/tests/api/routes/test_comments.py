"""Tests for issue comments (CRUD + threading)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.issue import Issue, IssuePriority, IssueStatus
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole


async def _setup(db: AsyncSession):
    """Create admin, project, issue. Returns (admin, project, issue)."""
    admin = User(
        email="cmtadmin@test.com",
        hashed_password=hash_password("Password123"),
        role=UserRole.ADMIN,
        is_active=True,
        is_email_verified=False,
    )
    dev = User(
        email="cmtdev@test.com",
        hashed_password=hash_password("Password123"),
        role=UserRole.DEVELOPER,
        is_active=True,
        is_email_verified=False,
    )
    db.add_all([admin, dev])
    await db.commit()
    await db.refresh(admin)
    await db.refresh(dev)

    project = Project(name="CMT Project", leader_id=admin.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)

    db.add(ProjectMember(project_id=project.id, user_id=dev.id))

    issue = Issue(
        title="Comment Test Issue",
        status=IssueStatus.TODO,
        priority=IssuePriority.MEDIUM,
        project_id=project.id,
        creator_id=admin.id,
    )
    db.add(issue)
    await db.commit()
    await db.refresh(issue)

    return admin, dev, project, issue


async def _token(client, email):
    resp = await client.post("/auth/login", json={"email": email, "password": "Password123"})
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_comment(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    resp = await client.post(
        f"/issues/{issue.id}/comments/",
        json={"content": "This is a comment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "This is a comment"
    assert data["author"]["email"] == admin.email


@pytest.mark.asyncio
async def test_list_comments(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    await client.post(
        f"/issues/{issue.id}/comments/",
        json={"content": "First"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/issues/{issue.id}/comments/",
        json={"content": "Second"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/issues/{issue.id}/comments/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_threaded_reply(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    admin_token = await _token(client, admin.email)
    dev_token = await _token(client, dev.email)

    parent = await client.post(
        f"/issues/{issue.id}/comments/",
        json={"content": "Parent comment"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    parent_id = parent.json()["id"]

    reply = await client.post(
        f"/issues/{issue.id}/comments/",
        json={"content": "Reply to parent", "parent_id": parent_id},
        headers={"Authorization": f"Bearer {dev_token}"},
    )
    assert reply.status_code == 201
    assert reply.json()["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_update_own_comment(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    create_resp = await client.post(
        f"/issues/{issue.id}/comments/",
        json={"content": "Original"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cid = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/issues/{issue.id}/comments/{cid}",
        json={"content": "Updated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["content"] == "Updated"
    assert update_resp.json()["updated_at"] is not None


@pytest.mark.asyncio
async def test_cannot_update_others_comment(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    admin_token = await _token(client, admin.email)
    dev_token = await _token(client, dev.email)

    create_resp = await client.post(
        f"/issues/{issue.id}/comments/",
        json={"content": "Admin wrote this"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/issues/{issue.id}/comments/{cid}",
        json={"content": "Dev trying to edit"},
        headers={"Authorization": f"Bearer {dev_token}"},
    )
    assert update_resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_own_comment(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    create_resp = await client.post(
        f"/issues/{issue.id}/comments/",
        json={"content": "To be deleted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cid = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/issues/{issue.id}/comments/{cid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_comment_on_nonexistent_issue(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    resp = await client.post(
        "/issues/99999/comments/",
        json={"content": "Ghost comment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
