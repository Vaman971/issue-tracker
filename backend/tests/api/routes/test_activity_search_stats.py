"""Tests for activity log, search, and stats endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.activity import ActivityAction, IssueActivity
from app.models.issue import Issue, IssuePriority, IssueStatus
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole


async def _setup(db: AsyncSession, prefix: str = ""):
    admin = User(
        email=f"{prefix}admin@test.com",
        hashed_password=hash_password("Password123"),
        role=UserRole.ADMIN,
        is_active=True,
        is_email_verified=False,
    )
    dev = User(
        email=f"{prefix}dev@test.com",
        hashed_password=hash_password("Password123"),
        role=UserRole.DEVELOPER,
        is_active=True,
        is_email_verified=False,
    )
    db.add_all([admin, dev])
    await db.commit()
    await db.refresh(admin)
    await db.refresh(dev)

    project = Project(name=f"{prefix}Project", leader_id=admin.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)

    db.add(ProjectMember(project_id=project.id, user_id=dev.id))

    issue = Issue(
        title=f"{prefix}Issue",
        description="A test issue for search",
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


# ===========================================================================
# Activity log
# ===========================================================================

@pytest.mark.asyncio
async def test_activity_log_shows_create_entry(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session, "act-")
    token = await _token(client, admin.email)

    # Seed an activity entry
    db_session.add(
        IssueActivity(
            issue_id=issue.id,
            actor_id=admin.id,
            action=ActivityAction.CREATED,
            new_value="Created the issue",
        )
    )
    await db_session.commit()

    resp = await client.get(
        f"/issues/{issue.id}/activity/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.json()]
    assert "created" in actions


@pytest.mark.asyncio
async def test_activity_log_forbidden_for_outsider(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session, "act2-")

    outsider = User(
        email="outsider-act@test.com",
        hashed_password=hash_password("Password123"),
        role=UserRole.VIEWER,
        is_active=True,
        is_email_verified=False,
    )
    db_session.add(outsider)
    await db_session.commit()

    outsider_token = await _token(client, outsider.email)

    resp = await client.get(
        f"/issues/{issue.id}/activity/",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_activity_logged_on_comment_creation(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session, "act3-")
    token = await _token(client, admin.email)

    await client.post(
        f"/issues/{issue.id}/comments/",
        json={"content": "Activity trigger"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/issues/{issue.id}/activity/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.json()]
    assert "comment_added" in actions


# ===========================================================================
# Search
# ===========================================================================

@pytest.mark.asyncio
async def test_search_returns_matching_issue(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session, "srch-")
    token = await _token(client, admin.email)

    resp = await client.get(
        "/search/", params={"q": "srch-Issue"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(i["title"] == "srch-Issue" for i in data["issues"])


@pytest.mark.asyncio
async def test_search_returns_matching_project(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session, "srchp-")
    token = await _token(client, admin.email)

    resp = await client.get(
        "/search/", params={"q": "srchp-Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(p["name"] == "srchp-Project" for p in data["projects"])


@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session, "srch0-")
    token = await _token(client, admin.email)

    resp = await client.get(
        "/search/", params={"q": "zzznomatch_xyz"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["issues"] == []
    assert data["projects"] == []


@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient):
    resp = await client.get("/search/", params={"q": "test"})
    assert resp.status_code == 401


# ===========================================================================
# Stats
# ===========================================================================

@pytest.mark.asyncio
async def test_project_stats(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session, "stats-")
    token = await _token(client, admin.email)

    resp = await client.get(
        f"/projects/{project.id}/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project.id
    assert data["total_issues"] >= 1
    assert "issues_by_status" in data
    assert "completion_rate" in data


@pytest.mark.asyncio
async def test_project_stats_forbidden_for_outsider(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session, "stats2-")

    outsider = User(
        email="outsider-stats@test.com",
        hashed_password=hash_password("Password123"),
        role=UserRole.VIEWER,
        is_active=True,
        is_email_verified=False,
    )
    db_session.add(outsider)
    await db_session.commit()

    outsider_token = await _token(client, outsider.email)
    resp = await client.get(
        f"/projects/{project.id}/stats",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats(client: AsyncClient, db_session: AsyncSession):
    admin, dev, project, issue = await _setup(db_session, "adminstats-")
    token = await _token(client, admin.email)

    resp = await client.get("/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "total_projects" in data
    assert "total_issues" in data
    assert "issues_by_status" in data
    assert "users_by_role" in data


@pytest.mark.asyncio
async def test_admin_stats_requires_admin(client: AsyncClient, db_session: AsyncSession):
    dev = User(
        email="dev-adminstats@test.com",
        hashed_password=hash_password("Password123"),
        role=UserRole.DEVELOPER,
        is_active=True,
        is_email_verified=False,
    )
    db_session.add(dev)
    await db_session.commit()

    token = await _token(client, dev.email)
    resp = await client.get("/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
