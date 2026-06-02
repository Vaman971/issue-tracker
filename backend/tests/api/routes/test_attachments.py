"""Tests for issue attachments (upload, list, URL, delete)."""

import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.issue import Issue, IssuePriority, IssueStatus
from app.models.project import Project
from app.models.user import User, UserRole

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def _setup(db: AsyncSession):
    admin = User(
        email="attadmin@test.com",
        hashed_password=hash_password("Password123"),
        role=UserRole.ADMIN,
        is_active=True,
        is_email_verified=False,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    project = Project(name="ATT Project", leader_id=admin.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)

    issue = Issue(
        title="ATT Issue",
        status=IssueStatus.TODO,
        priority=IssuePriority.MEDIUM,
        project_id=project.id,
        creator_id=admin.id,
    )
    db.add(issue)
    await db.commit()
    await db.refresh(issue)

    return admin, issue


async def _token(client, email):
    resp = await client.post("/auth/login", json={"email": email, "password": "Password123"})
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_png_attachment(client: AsyncClient, db_session: AsyncSession):
    admin, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    resp = await client.post(
        f"/issues/{issue.id}/attachments/",
        files={"file": ("screenshot.png", io.BytesIO(PNG_1PX), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["original_filename"] == "screenshot.png"
    assert data["mime_type"] == "image/png"
    assert data["file_size_bytes"] == len(PNG_1PX)


@pytest.mark.asyncio
async def test_upload_disallowed_type(client: AsyncClient, db_session: AsyncSession):
    admin, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    resp = await client.post(
        f"/issues/{issue.id}/attachments/",
        files={"file": ("hack.exe", io.BytesIO(b"MZ\x90"), "application/x-msdownload")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_attachments(client: AsyncClient, db_session: AsyncSession):
    admin, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    await client.post(
        f"/issues/{issue.id}/attachments/",
        files={"file": ("a.png", io.BytesIO(PNG_1PX), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/issues/{issue.id}/attachments/",
        files={"file": ("b.png", io.BytesIO(PNG_1PX), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/issues/{issue.id}/attachments/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_attachment_download_url(client: AsyncClient, db_session: AsyncSession):
    admin, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    upload = await client.post(
        f"/issues/{issue.id}/attachments/",
        files={"file": ("img.png", io.BytesIO(PNG_1PX), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    att_id = upload.json()["id"]

    resp = await client.get(
        f"/issues/{issue.id}/attachments/{att_id}/url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "download_url" in resp.json()


@pytest.mark.asyncio
async def test_delete_attachment(client: AsyncClient, db_session: AsyncSession):
    admin, issue = await _setup(db_session)
    token = await _token(client, admin.email)

    upload = await client.post(
        f"/issues/{issue.id}/attachments/",
        files={"file": ("del.png", io.BytesIO(PNG_1PX), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    att_id = upload.json()["id"]

    del_resp = await client.delete(
        f"/issues/{issue.id}/attachments/{att_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(
        f"/issues/{issue.id}/attachments/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(list_resp.json()) == 0
