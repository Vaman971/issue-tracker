# Module 04-02 — SQLAlchemy Async ORM: Models, Queries & Relationships

---

## Learning Objectives

After this module you will:
- Understand what an ORM is and why we use it
- Know how SQLAlchemy models map to database tables
- Write async queries using SQLAlchemy 2.0 style
- Understand lazy loading vs eager loading for relationships

---

## What Is an ORM?

ORM (Object-Relational Mapper) lets you work with database records as Python objects instead of writing raw SQL:

```python
# WITHOUT ORM (raw SQL):
cursor.execute(
    "SELECT id, title, status FROM issues WHERE project_id = %s AND status = %s",
    (project_id, "IN_PROGRESS")
)
rows = cursor.fetchall()
# rows is a list of tuples: [(1, "Fix bug", "IN_PROGRESS"), ...]
# You must manually map columns to your code

# WITH SQLAlchemy ORM:
result = await db.execute(
    select(Issue)
    .where(Issue.project_id == project_id)
    .where(Issue.status == IssueStatus.IN_PROGRESS)
)
issues = result.scalars().all()
# issues is a list of Issue objects with attributes:
# issues[0].id, issues[0].title, issues[0].status
```

Benefits:
- Work with Python objects (not raw tuples)
- Type checking and IDE autocomplete
- Database-agnostic (same code works on SQLite, PostgreSQL, MySQL)
- Relationship loading (access `issue.assignees` like a list)

---

## SQLAlchemy Architecture

```
Your Code
    │
    ▼
SQLAlchemy ORM (high-level, object interface)
    │
    ▼
SQLAlchemy Core (SQL expression language)
    │
    ▼
DBAPI driver (asyncpg for PostgreSQL)
    │
    ▼
PostgreSQL server
```

This project uses **SQLAlchemy 2.0+** with the modern **mapped_column** style and full async support.

---

## Model Definition

```python
# backend/app/models/user.py

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Enum as SQLEnum, ForeignKey, DateTime
from datetime import datetime, timezone
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    PROJECT_LEADER = "PROJECT_LEADER"
    DEVELOPER = "DEVELOPER"
    QA = "QA"
    VIEWER = "VIEWER"

class User(Base):
    __tablename__ = "users"
    
    # Mapped[type] = mapped_column() is SQLAlchemy 2.0 style
    # Type annotation handles NOT NULL (no Optional = NOT NULL)
    
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        default=UserRole.DEVELOPER,
        nullable=False
    )
    avatar_url: Mapped[str | None] = mapped_column(String(255))  # Optional
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)  # Auto-update on change
    )
    
    # Relationships (not columns — define how to traverse foreign keys)
    projects_as_leader: Mapped[list["Project"]] = relationship(
        back_populates="leader"
    )
    project_memberships: Mapped[list["ProjectMember"]] = relationship(
        back_populates="user"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
```

```python
# backend/app/models/issue.py

class Issue(Base):
    __tablename__ = "issues"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[IssueStatus] = mapped_column(
        SQLEnum(IssueStatus),
        default=IssueStatus.TODO,
        index=True
    )
    priority: Mapped[IssuePriority] = mapped_column(
        SQLEnum(IssuePriority),
        default=IssuePriority.MEDIUM,
        index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),  # Delete issues when project deleted
        nullable=False,
        index=True
    )
    creator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(...)
    updated_at: Mapped[datetime] = mapped_column(...)
    
    # Relationships
    project: Mapped["Project"] = relationship(back_populates="issues")
    creator: Mapped["User"] = relationship(foreign_keys=[creator_id])
    
    # Many-to-many: an issue can have multiple assignees
    assignees: Mapped[list["User"]] = relationship(
        secondary="issue_assignees",  # Junction table name
        lazy="selectin"  # Always load assignees with the issue
    )
    
    comments: Mapped[list["IssueComment"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
        order_by="IssueComment.created_at"
    )
    
    attachments: Mapped[list["IssueAttachment"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan"
    )
    
    labels: Mapped[list["Label"]] = relationship(
        secondary="issue_labels"
    )
    
    __table_args__ = (
        Index("idx_issues_project_status", "project_id", "status"),
    )
```

---

## The Database Session

```python
# backend/app/db/session.py

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from app.core.config import settings

# Create the async engine
# pool_size: max persistent connections
# max_overflow: extra connections during spikes
# pool_timeout: wait max 30s for a connection
engine = create_async_engine(
    settings.DATABASE_URL,  # "postgresql+asyncpg://user:pass@host:5432/db"
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_pre_ping=True,  # Test connections before use (detects stale connections)
    echo=settings.APP_ENV == "development",  # Log SQL in development
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
    autocommit=False,
    autoflush=False,
)
```

### Connection Pool — How It Works

```
Application starts
        │
        ▼
SQLAlchemy creates connection pool
Pool maintains: [conn1, conn2, ..., conn10] (idle, ready to use)
        │
Request arrives
        ▼
get_db() borrows a connection from the pool
        │ (if all 10 are busy, wait up to 30s for one to free up)
        ▼
Handler runs SQL queries using the connection
        │
Request ends → connection returned to pool
        │
Pool: [conn1, conn2, ..., conn10] (available again)
```

This avoids the overhead of creating a new TCP connection for every request (which takes ~100ms).

---

## Async Queries — SQLAlchemy 2.0 Style

```python
# backend/app/api/routes/issues.py

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# GET a single record by primary key (fastest lookup)
issue = await db.get(Issue, issue_id)
if not issue:
    raise HTTPException(404, "Issue not found")

# SELECT with WHERE clause
stmt = select(Issue).where(
    Issue.project_id == project_id,
    Issue.status == IssueStatus.IN_PROGRESS
)
result = await db.execute(stmt)
issues = result.scalars().all()  # List of Issue objects

# SELECT with ORDER BY and LIMIT
stmt = (
    select(Issue)
    .where(Issue.project_id == project_id)
    .order_by(Issue.created_at.desc())
    .limit(20)
    .offset(40)  # page 3 (0-indexed, 20 per page)
)
result = await db.execute(stmt)
issues = result.scalars().all()

# COUNT
count_stmt = select(func.count()).select_from(Issue).where(
    Issue.project_id == project_id
)
total = await db.scalar(count_stmt)

# INSERT
new_issue = Issue(
    title="Fix login bug",
    project_id=1,
    creator_id=current_user.id,
    status=IssueStatus.TODO,
    priority=IssuePriority.HIGH,
)
db.add(new_issue)
await db.flush()   # Write to DB but don't commit yet (gets the auto-generated id)
print(new_issue.id)  # Now has the ID from DB

# UPDATE
stmt = (
    update(Issue)
    .where(Issue.id == issue_id)
    .values(status=IssueStatus.IN_PROGRESS, updated_at=datetime.now())
)
await db.execute(stmt)

# Or update via ORM object:
issue.status = IssueStatus.IN_PROGRESS
await db.flush()

# DELETE
stmt = delete(Issue).where(Issue.id == issue_id)
await db.execute(stmt)

# Always commit at the end (the dependency handles this)
await db.commit()
```

---

## Eager Loading Relationships

One of the most common performance mistakes is the **N+1 query problem**:

```python
# BAD — N+1 queries:
issues = (await db.execute(select(Issue))).scalars().all()
# 1 query to get issues

for issue in issues:
    print(issue.assignees)  # 1 query per issue to load assignees!
    # 100 issues = 101 queries total!
```

SQLAlchemy with async requires **explicit eager loading**:

```python
# GOOD — 2 queries total (or 1 with JOIN):

# Option 1: selectinload (2 queries — efficient for collections)
stmt = (
    select(Issue)
    .options(selectinload(Issue.assignees))
    .options(selectinload(Issue.comments))
    .where(Issue.project_id == project_id)
)
# Query 1: SELECT * FROM issues WHERE project_id = 1
# Query 2: SELECT * FROM users JOIN issue_assignees WHERE issue_id IN (1,2,3,...)
result = await db.execute(stmt)
issues = result.scalars().all()
# issues[0].assignees is already populated — no extra queries!

# Option 2: joinedload (1 query — efficient for single items)
stmt = (
    select(Issue)
    .options(joinedload(Issue.creator))  # JOIN to users table
    .where(Issue.id == issue_id)
)
# Query: SELECT issues.*, users.* FROM issues JOIN users ON issues.creator_id = users.id
```

### The `lazy="selectin"` Model Setting

In this project, assignees are declared with `lazy="selectin"`:

```python
# backend/app/models/issue.py
assignees: Mapped[list["User"]] = relationship(
    secondary="issue_assignees",
    lazy="selectin"  # Always load with selectin strategy
)
```

This means every time you load an `Issue`, SQLAlchemy automatically runs a second query to load the assignees. Since almost every view of an issue shows assignees, this is a good default.

---

## Transactions in Practice

```python
# backend/app/api/deps.py

async def get_db():
    """Dependency: provides a session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session           # Handler runs here
            await session.commit()  # Commit all changes if no error
        except Exception:
            await session.rollback()  # Rollback on any error
            raise
        finally:
            await session.close()

# This means: in a route handler, you can do multiple operations
# and they're all in one atomic transaction:

@router.post("/issues")
async def create_issue(body: IssueCreate, db=Depends(get_db), ...):
    # All of these are in one transaction:
    new_issue = Issue(...)
    db.add(new_issue)
    
    activity = IssueActivity(issue_id=new_issue.id, ...)
    db.add(activity)
    
    # If anything above fails, BOTH are rolled back
    # get_db()'s except block calls db.rollback()
```

---

## Database Seeding

```python
# backend/app/db/seed.py
# Creates the initial admin user on startup

async def seed_admin():
    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        result = await db.execute(
            select(User).where(User.email == settings.SEED_ADMIN_EMAIL)
        )
        if result.scalar():
            return  # Admin already seeded
        
        admin = User(
            email=settings.SEED_ADMIN_EMAIL,
            hashed_password=hash_password(settings.SEED_ADMIN_PASSWORD),
            name="Admin",
            role=UserRole.ADMIN,
            email_verified=True,  # Admin doesn't need email verification
        )
        db.add(admin)
        await db.commit()
        print(f"Admin user seeded: {settings.SEED_ADMIN_EMAIL}")
```

This runs during app startup (in the lifespan function) and during the Kubernetes migration Job.

---

## The Declarative Base

All models inherit from `Base`:

```python
# backend/app/db/base.py

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """All SQLAlchemy models must inherit from this."""
    pass
```

When you run `alembic upgrade head`, Alembic:
1. Imports all model modules (they register themselves with Base)
2. Reads `Base.metadata` (all table definitions)
3. Compares to current database schema
4. Generates and runs the necessary `CREATE TABLE` / `ALTER TABLE` SQL

---

## Full-Text Search with PostgreSQL

```python
# backend/app/api/routes/search.py

from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import TSVECTOR

@router.get("/")
async def search(q: str = Query(..., min_length=2), db=Depends(get_db), ...):
    
    # PostgreSQL full-text search:
    # to_tsvector: converts text to searchable token vector
    # to_tsquery: converts search string to query
    # @@: "matches" operator
    
    search_vector = func.to_tsvector(
        "english",
        func.coalesce(Issue.title, '') + ' ' + func.coalesce(Issue.description, '')
    )
    search_query = func.to_tsquery("english", q.replace(" ", " & "))
    
    stmt = (
        select(Issue)
        .where(search_vector.op("@@")(search_query))
        # Order by relevance (how well the issue matches)
        .order_by(
            func.ts_rank(search_vector, search_query).desc()
        )
        .limit(50)
    )
    
    result = await db.execute(stmt)
    return result.scalars().all()
```

---

## Common Patterns

### Check Before Insert (avoid duplicates)

```python
# Check email is unique before creating user
existing = await db.scalar(
    select(User).where(User.email == body.email)
)
if existing:
    raise HTTPException(409, "Email already registered")
```

### Upsert (insert or update)

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Insert issue_assignee, ignore if already exists
stmt = pg_insert(IssueAssignee).values(
    issue_id=issue_id,
    user_id=user_id
).on_conflict_do_nothing(
    index_elements=["issue_id", "user_id"]
)
await db.execute(stmt)
```

### Bulk Delete

```python
# Remove all assignees for an issue before re-assigning
await db.execute(
    delete(IssueAssignee).where(IssueAssignee.issue_id == issue_id)
)
# Then add new assignees
for user_id in new_assignee_ids:
    db.add(IssueAssignee(issue_id=issue_id, user_id=user_id))
```

---

## Further Reading & Videos

- **YouTube**: Search "SQLAlchemy 2.0 Tutorial" — covers the modern mapped_column style
- **YouTube**: Search "SQLAlchemy async Python" — for async-specific patterns
- **Official Docs**: [SQLAlchemy 2.0 documentation](https://docs.sqlalchemy.org/en/20/)
- **Official Docs**: [SQLAlchemy ORM quick start](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)

---

*Next: [Module 04-03 — Alembic Database Migrations](./03-alembic-migrations.md)*
