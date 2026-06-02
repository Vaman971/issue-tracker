"""
Shared pytest setup.

Tests use an isolated in-memory SQLite database and a tiny in-memory Redis fake,
so API tests stay fast and deterministic.
"""

import fnmatch
import os
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# Must be set before importing app/config/db modules.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["JWT_SECRET_KEY"] = "test-access-secret"
os.environ["JWT_REFRESH_SECRET_KEY"] = "test-refresh-secret"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRES_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_EXPIRES_DAYS"] = "7"
os.environ["BACKEND_CORS_ORIGINS"] = "http://test"
os.environ["SQL_ECHO"] = "false"
os.environ["REDIS_DEFAULT_TTL_SECONDS"] = "300"
os.environ["REDIS_HEALTHCHECK_TIMEOUT_SECONDS"] = "3"
os.environ["AUTH_RATE_LIMIT_WINDOW_SECONDS"] = "60"
os.environ["AUTH_RATE_LIMIT_LOGIN_MAX_ATTEMPTS"] = "2"
os.environ["AUTH_RATE_LIMIT_REGISTER_MAX_ATTEMPTS"] = "2"
os.environ["AUTH_RATE_LIMIT_REFRESH_MAX_ATTEMPTS"] = "2"
os.environ["EMAILS_ENABLED"] = "false"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_UPLOAD_DIR"] = "/tmp/test_uploads"
os.environ["FRONTEND_URL"] = "http://test"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/1"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/2"

from app.core import redis as redis_module
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import *  # noqa: F402,F401 - registers models with Base.metadata
from app.services import cache as cache_service
from app.services import rate_limit as rate_limit_service


class FakeRedis:
    def __init__(self):
        self.store: dict[str, Any] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None):  # noqa: A002
        self.store[key] = value

    async def delete(self, *keys: str):
        for key in keys:
            self.store.pop(key, None)

    async def incr(self, key: str):
        value = int(self.store.get(key, 0)) + 1
        self.store[key] = value
        return value

    async def expire(self, _key: str, _seconds: int):
        return True

    async def ping(self):
        return True

    async def aclose(self):
        return None

    async def scan_iter(self, match: str):
        for key in list(self.store.keys()):
            if fnmatch.fnmatch(key, match):
                yield key


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch):
    fake = FakeRedis()
    monkeypatch.setattr(redis_module, "redis_client", fake)
    monkeypatch.setattr(redis_module, "get_redis_client", lambda: fake)
    monkeypatch.setattr(cache_service, "get_redis_client", lambda: fake)
    monkeypatch.setattr(rate_limit_service, "get_redis_client", lambda: fake)
    return fake


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, Any]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine):
    test_session_local = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with test_session_local() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine: AsyncEngine, fake_redis: FakeRedis):
    test_session_local = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with test_session_local() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Shared helper fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> str:
    """Register an admin user and return its access token."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    # Create admin directly in db via a fresh session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pass  # just need the client to be active

    # Use the client fixture's override — register then promote via db
    resp = await client.post("/auth/register", json={"email": "admin@test.com", "password": "Password123"})
    assert resp.status_code == 201

    # Promote to admin via direct DB manipulation
    from app.db.session import get_db as _get_db
    async for session in app.dependency_overrides[get_db]():
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.email == "admin@test.com"))
        user = result.scalar_one()
        user.role = UserRole.ADMIN
        await session.commit()
        break

    login = await client.post("/auth/login", json={"email": "admin@test.com", "password": "Password123"})
    return login.json()["access_token"]


@pytest_asyncio.fixture
async def user_token(client: AsyncClient) -> str:
    """Register a regular viewer user and return its access token."""
    await client.post("/auth/register", json={"email": "user@test.com", "password": "Password123"})
    login = await client.post("/auth/login", json={"email": "user@test.com", "password": "Password123"})
    return login.json()["access_token"]


@pytest_asyncio.fixture
async def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture
async def user_headers(user_token: str) -> dict:
    return {"Authorization": f"Bearer {user_token}"}
