from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Engine knows how to connect to db, which driver to use and connection pooling rules (database connection factory).
## using create_async_engine because FAstApi routes, redis and asyncpg all are async operations and can reduce concurrency
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO # it prints generated sql queries to the terminal (disable in production)
)

# session represents one unit of database interaction (conversation with the database)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# in the app each db request will have its own session, to prevent requests from interfering with each other.

# get_db is a fast api dependency, which when injected to any route (API), lets FastApi create session, injects it an clean it up automatically
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session