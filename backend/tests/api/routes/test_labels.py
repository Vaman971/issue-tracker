"""Tests for project labels and issue label assignment."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.issue import Issue, IssuePriority, IssueStatus
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole


async def _setup(db: AsyncSession):
    admin = User(
        email="lbladmin@test.com",
        hashed_password=hash_password("Password123"),
        role=UserRole.ADMIN,
        is_active=True,
        is_email_verified=False,
    )
    dev = User(
        email="lbldev@test.com",
        hashed_password=hash_password("Password123"),
        role=UserRole.DEVELOPER,
        is_active=True,
        is_email_verified=False,
    )
    db.add_all([admin, dev])
    await db.commit()
    await db.refresh(admin)
    await db.refresh(dev)

    project = Project(name="LBL Project", leader_id=admin.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)

    db.add(ProjectMember(project_id=project.id, user_id=dev.id))

    issue = Issue(
        title="LBL Issue",
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
async def test_create_label(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    resp = await client.post(
        f"/projects/{project.id}/labels/",
        json={"name": "bug", "color": "#FF0000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "bug"
    assert data["color"] == "#FF0000"


@pytest.mark.asyncio
async def test_create_label_invalid_color(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    resp = await client.post(
        f"/projects/{project.id}/labels/",
        json={"name": "bad-color", "color": "red"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_label_name_rejected(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    await client.post(
        f"/projects/{project.id}/labels/",
        json={"name": "feature", "color": "#00FF00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.post(
        f"/projects/{project.id}/labels/",
        json={"name": "feature", "color": "#0000FF"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_labels(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    await client.post(f"/projects/{project.id}/labels/", json={"name": "a"}, headers={"Authorization": f"Bearer {token}"})
    await client.post(f"/projects/{project.id}/labels/", json={"name": "b"}, headers={"Authorization": f"Bearer {token}"})

    resp = await client.get(f"/projects/{project.id}/labels/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_developer_cannot_create_label(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    dev_token = await _token(client, dev.email)

    resp = await client.post(
        f"/projects/{project.id}/labels/",
        json={"name": "dev-label"},
        headers={"Authorization": f"Bearer {dev_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_add_and_remove_label_from_issue(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    label_resp = await client.post(
        f"/projects/{project.id}/labels/",
        json={"name": "urgent"},
        headers={"Authorization": f"Bearer {token}"},
    )
    label_id = label_resp.json()["id"]

    add_resp = await client.post(
        f"/issues/{issue.id}/labels/{label_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert add_resp.status_code == 201

    # Duplicate add rejected
    dup = await client.post(
        f"/issues/{issue.id}/labels/{label_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dup.status_code == 400

    rem_resp = await client.delete(
        f"/issues/{issue.id}/labels/{label_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rem_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_label(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    label_resp = await client.post(
        f"/projects/{project.id}/labels/",
        json={"name": "to-delete"},
        headers={"Authorization": f"Bearer {token}"},
    )
    label_id = label_resp.json()["id"]

    del_resp = await client.delete(
        f"/projects/{project.id}/labels/{label_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(
        f"/projects/{project.id}/labels/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(list_resp.json()) == 0
