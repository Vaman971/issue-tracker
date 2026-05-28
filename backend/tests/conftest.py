"""
conftest.py

shared pytest setip.

This file created an isolated in-memory SQLite database for API tests and overrides FastAPI's get_db dependency so routes use the test database instead of the development/production database
"""

import os
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.pool import StaticPool
from typing import Any, AsyncGenerator

# Must be set before importing app/config/db modules
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["JWT_SECRET_KEY"] = "test-access-secret"
os.environ["JWT_REFRESH_SECRET_KEY"] = "test-refresh-secret"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRES_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_EXPIRES_DAYS"] = "7"
os.environ["BACKEND_CORS_ORIGINS"] = "http://test"
os.environ["SQL_ECHO"] = "false"

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import * # noqa: F402,F401 - registers models with Base.metadata

@pytest_asyncio.fixture
async def db_engine()-> AsyncGenerator[AsyncEngine, Any]:
    """
    Create a fresh in-memory SQLite database for each test.

    StaticPool keeps the same in-memory database connection alive
    during the test, instead of creating a new empty database per connection
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_key=ON")) # for sqlite foreign_key flag needs to be set
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine):
    """
    Create a direct database session for tests that need setup data.

    This uses the same isolated test engine as the API client,
    so  it does not touch development or production databases
    """

    TestSessionLocal = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with TestSessionLocal() as session:
        yield session

@pytest_asyncio.fixture
async def client(db_engine: AsyncEngine):
    """
    Create an async HTTP client that sends request to the FastAPI app.

    The app's get_db is overriddden so every route uses the isolated test database for this test.
    """
    TestSessionLocal = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session
    
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()