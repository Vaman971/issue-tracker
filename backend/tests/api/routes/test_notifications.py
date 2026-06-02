"""Tests for user notifications."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole


async def _make_user(db: AsyncSession, email: str, role=UserRole.VIEWER):
    user = User(
        email=email,
        hashed_password=hash_password("Password123"),
        role=role,
        is_active=True,
        is_email_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _seed_notifications(db: AsyncSession, user_id: int, count: int = 3):
    for i in range(count):
        db.add(
            Notification(
                user_id=user_id,
                type=NotificationType.ISSUE_CREATED,
                title=f"Notification {i}",
                message=f"Message {i}",
                is_read=False,
            )
        )
    await db.commit()


async def _token(client, email):
    resp = await client.post("/auth/login", json={"email": email, "password": "Password123"})
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_notifications(client: AsyncClient, db_session: AsyncSession):
    user = await _make_user(db_session, "notif-list@test.com")
    await _seed_notifications(db_session, user.id, count=3)
    token = await _token(client, user.email)

    resp = await client.get("/notifications/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_list_unread_only(client: AsyncClient, db_session: AsyncSession):
    user = await _make_user(db_session, "notif-unread@test.com")
    await _seed_notifications(db_session, user.id, count=3)

    # Mark one as read directly in DB
    from sqlalchemy import select
    result = await db_session.execute(
        select(Notification).where(Notification.user_id == user.id).limit(1)
    )
    n = result.scalar_one()
    n.is_read = True
    await db_session.commit()

    token = await _token(client, user.email)
    resp = await client.get(
        "/notifications/", params={"unread_only": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_notification_count(client: AsyncClient, db_session: AsyncSession):
    user = await _make_user(db_session, "notif-count@test.com")
    await _seed_notifications(db_session, user.id, count=4)
    token = await _token(client, user.email)

    resp = await client.get("/notifications/count", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert data["unread"] == 4


@pytest.mark.asyncio
async def test_mark_notification_read(client: AsyncClient, db_session: AsyncSession):
    user = await _make_user(db_session, "notif-read@test.com")
    await _seed_notifications(db_session, user.id, count=1)
    token = await _token(client, user.email)

    list_resp = await client.get("/notifications/", headers={"Authorization": f"Bearer {token}"})
    nid = list_resp.json()[0]["id"]

    read_resp = await client.patch(
        f"/notifications/{nid}/read",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True


@pytest.mark.asyncio
async def test_mark_all_read(client: AsyncClient, db_session: AsyncSession):
    user = await _make_user(db_session, "notif-all@test.com")
    await _seed_notifications(db_session, user.id, count=5)
    token = await _token(client, user.email)

    resp = await client.patch("/notifications/read-all", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204

    count_resp = await client.get("/notifications/count", headers={"Authorization": f"Bearer {token}"})
    assert count_resp.json()["unread"] == 0


@pytest.mark.asyncio
async def test_delete_notification(client: AsyncClient, db_session: AsyncSession):
    user = await _make_user(db_session, "notif-del@test.com")
    await _seed_notifications(db_session, user.id, count=1)
    token = await _token(client, user.email)

    list_resp = await client.get("/notifications/", headers={"Authorization": f"Bearer {token}"})
    nid = list_resp.json()[0]["id"]

    del_resp = await client.delete(
        f"/notifications/{nid}", headers={"Authorization": f"Bearer {token}"}
    )
    assert del_resp.status_code == 204

    after = await client.get("/notifications/", headers={"Authorization": f"Bearer {token}"})
    assert len(after.json()) == 0


@pytest.mark.asyncio
async def test_cannot_access_other_users_notification(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session, "owner-notif@test.com")
    other = await _make_user(db_session, "other-notif@test.com")
    await _seed_notifications(db_session, owner.id, count=1)

    other_token = await _token(client, other.email)
    owner_token = await _token(client, owner.email)

    list_resp = await client.get("/notifications/", headers={"Authorization": f"Bearer {owner_token}"})
    nid = list_resp.json()[0]["id"]

    # Other user tries to read it
    resp = await client.patch(
        f"/notifications/{nid}/read",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404
