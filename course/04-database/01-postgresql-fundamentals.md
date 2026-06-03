# Module 04-01 — PostgreSQL: Internals, Schema Design & ACID

---

## Learning Objectives

After this module you will:
- Understand what a relational database is and why we use it
- Know PostgreSQL's internal architecture
- Understand ACID properties and why they matter
- See the complete schema design for this project

---

## What Is a Relational Database?

A relational database organizes data into **tables** (also called relations) with rows and columns. Tables are connected by **foreign keys**.

```
Think of it like a set of Excel spreadsheets that are linked together:

users table:
┌────┬───────────────────┬──────────────────────────────┐
│ id │ email             │ hashed_password              │
├────┼───────────────────┼──────────────────────────────┤
│  1 │ alice@example.com │ $2b$12$...                   │
│  2 │ bob@example.com   │ $2b$12$...                   │
└────┴───────────────────┴──────────────────────────────┘

projects table:
┌────┬──────────────────┬────────────┐
│ id │ name             │ leader_id  │  ← foreign key to users.id
├────┼──────────────────┼────────────┤
│  1 │ Website Redesign │     1      │  (Alice is leader)
│  2 │ Mobile App       │     2      │  (Bob is leader)
└────┴──────────────────┴────────────┘

issues table:
┌────┬─────────────────┬────────────┬────────────────┐
│ id │ title           │ project_id │ status         │
├────┼─────────────────┼────────────┼────────────────┤
│  1 │ Fix login bug   │     1      │ IN_PROGRESS    │
│  2 │ Add dark mode   │     1      │ TODO           │
│  3 │ Push notification│    2      │ DONE           │
└────┴─────────────────┴────────────┴────────────────┘
```

**Why relational?** Because our data is **structured** and **related**. An issue belongs to a project. A project has a leader who is a user. This web of relationships is natural to model in a relational database.

---

## PostgreSQL Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Server Process                     │
│                                                                 │
│  ┌─────────────┐    ┌────────────────────────────────────────┐  │
│  │  Postmaster │    │           Shared Memory                │  │
│  │  (listener) │    │                                        │  │
│  │  Accepts    │    │  ┌──────────────────────────────────┐  │  │
│  │  connections│    │  │    Shared Buffer Pool (cache)    │  │  │
│  └──────┬──────┘    │  │    (default: 128MB, tunable)     │  │  │
│         │           │  │    Hot pages cached here         │  │  │
│         ▼           │  └──────────────────────────────────┘  │  │
│  ┌──────────────┐   │                                        │  │
│  │  Backend     │   │  ┌──────────────────────────────────┐  │  │
│  │  Process     │◄──►  │    WAL Buffer (write-ahead log)  │  │  │
│  │  (one per    │   │  │    Changes written here first    │  │  │
│  │   connection)│   │  └──────────────────────────────────┘  │  │
│  └──────────────┘   └────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Disk Storage                          │   │
│  │                                                         │   │
│  │  ┌──────────────┐  ┌────────────────┐  ┌────────────┐  │   │
│  │  │  Data Files  │  │  WAL Files     │  │  Indexes   │  │   │
│  │  │  (heap files)│  │  (transaction  │  │  (B-trees) │  │   │
│  │  │  Table data  │  │   log)         │  │            │  │   │
│  │  └──────────────┘  └────────────────┘  └────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

**Shared Buffer Pool**: PostgreSQL caches frequently accessed data pages in RAM. If you read the `users` table 1000 times, after the first read it's served from memory (microseconds) instead of disk (milliseconds).

**WAL (Write-Ahead Log)**: Before changing data on disk, PostgreSQL writes the change to the WAL (a sequential append-only log). This is why PostgreSQL can recover from crashes — it replays the WAL after restart.

**MVCC (Multi-Version Concurrency Control)**: Instead of locking rows when they're read, PostgreSQL keeps multiple versions of each row. Readers never block writers. Writers never block readers.

---

## ACID Properties — The Foundation of Reliability

ACID stands for **Atomicity, Consistency, Isolation, Durability**. These properties guarantee that database transactions are processed reliably.

### Atomicity — All or Nothing

```
EXAMPLE: Transfer $100 from Alice to Bob

UPDATE accounts SET balance = balance - 100 WHERE id = 1;  -- Alice -$100
UPDATE accounts SET balance = balance + 100 WHERE id = 2;  -- Bob +$100

PROBLEM: What if the server crashes between these two statements?
  Alice loses $100, Bob gets nothing!

ATOMICITY solution: Wrap in a transaction
BEGIN;
  UPDATE accounts SET balance = balance - 100 WHERE id = 1;
  UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;

If anything fails → entire transaction ROLLS BACK
Both updates happen, or neither happens. Never just one.
```

### Consistency — Rules Are Always Enforced

```
Tables have constraints:
- NOT NULL: issue.title cannot be null
- UNIQUE: user.email must be unique
- FOREIGN KEY: issue.project_id must reference an existing project
- CHECK: issue.priority must be in ('LOW','MEDIUM','HIGH','CRITICAL')

Any transaction that would violate these is rejected.
Database is always in a valid state.
```

### Isolation — Concurrent Transactions Don't Interfere

```
Isolation Level: READ COMMITTED (default in PostgreSQL)

Transaction A is slowly reading 1000 users...
Transaction B updates user #500 and commits...
Transaction A rereads user #500 — sees the updated value!

This is called a "non-repeatable read". For most applications this is fine.

For financial applications you'd use SERIALIZABLE isolation:
Transactions execute as if they ran one at a time (no anomalies).
```

### Durability — Committed Data Survives Crashes

```
Transaction commits
        │
        ▼
PostgreSQL writes to WAL on disk (before saying "committed")
        │
        ▼ Server crashes immediately after
        │
        ▼ Server restarts
        │
        ▼ PostgreSQL reads WAL
        │
        ▼ Replays any committed transactions not yet in data files
        │
        ▼ Data is fully restored as of the last commit
```

---

## The Database Schema — All 14 Tables

### Core Tables

```sql
-- Users
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    name        VARCHAR(100) NOT NULL,
    role        VARCHAR(20) NOT NULL DEFAULT 'DEVELOPER',
                -- CHECK constraint: must be valid role
    avatar_url  VARCHAR(255),
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Projects
CREATE TABLE projects (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    leader_id   INTEGER NOT NULL REFERENCES users(id),
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Project membership (many-to-many: users ↔ projects)
CREATE TABLE project_members (
    id         SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       VARCHAR(20) NOT NULL DEFAULT 'DEVELOPER',
    joined_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, user_id)  -- Can't be a member twice
);
```

```sql
-- Issues
CREATE TABLE issues (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    description TEXT,
    status      VARCHAR(20) NOT NULL DEFAULT 'TODO',
                -- Values: TODO, IN_PROGRESS, IN_REVIEW, DONE
    priority    VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
                -- Values: LOW, MEDIUM, HIGH, CRITICAL
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    creator_id  INTEGER NOT NULL REFERENCES users(id),
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Issue assignments (many-to-many: users ↔ issues)
CREATE TABLE issue_assignees (
    id       SERIAL PRIMARY KEY,
    issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(issue_id, user_id)
);
```

```sql
-- Comments (self-referential for nested replies)
CREATE TABLE issue_comments (
    id         SERIAL PRIMARY KEY,
    issue_id   INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    author_id  INTEGER NOT NULL REFERENCES users(id),
    content    TEXT NOT NULL,
    parent_id  INTEGER REFERENCES issue_comments(id),
                -- NULL = top-level comment
                -- NOT NULL = reply to another comment
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- File attachments
CREATE TABLE issue_attachments (
    id           SERIAL PRIMARY KEY,
    issue_id     INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    uploader_id  INTEGER NOT NULL REFERENCES users(id),
    filename     VARCHAR(255) NOT NULL,
    storage_path VARCHAR(1000) NOT NULL,  -- S3 path or local path
    file_size    INTEGER NOT NULL,         -- bytes
    content_type VARCHAR(100) NOT NULL,   -- MIME type
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

```sql
-- Labels (many-to-many with issues)
CREATE TABLE labels (
    id         SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name       VARCHAR(50) NOT NULL,
    color      VARCHAR(7) NOT NULL DEFAULT '#808080',  -- HEX color
    UNIQUE(project_id, name)
);

CREATE TABLE issue_labels (
    id       SERIAL PRIMARY KEY,
    issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    label_id INTEGER NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
    UNIQUE(issue_id, label_id)
);
```

```sql
-- Notifications
CREATE TABLE notifications (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type VARCHAR(50) NOT NULL,
    title             VARCHAR(255) NOT NULL,
    body              TEXT,
    issue_id          INTEGER REFERENCES issues(id),
    read              BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Activity feed
CREATE TABLE activities (
    id            SERIAL PRIMARY KEY,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    issue_id      INTEGER REFERENCES issues(id),
    user_id       INTEGER NOT NULL REFERENCES users(id),
    activity_type VARCHAR(50) NOT NULL,
    old_value     TEXT,
    new_value     TEXT,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

```sql
-- Auth tokens
CREATE TABLE refresh_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(64) NOT NULL UNIQUE,
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    user_agent  VARCHAR(500),
    ip_address  VARCHAR(45),
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE email_verification_tokens (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE password_reset_tokens (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

---

## Entity Relationship Diagram

```
users ──────────────────────────────────┐
  │ id                                  │
  │                                     │
  ├── [leader_id] ──► projects          │
  │                     │ id            │
  │                     │              │
  │   project_members ◄─┘              │
  │       │ project_id                 │
  │       │ user_id ──────────────────►┤
  │                                    │
  ├── [creator_id] ──► issues          │
  │                     │ id           │
  │                     │             │
  │   issue_assignees ◄─┘             │
  │       │ issue_id                  │
  │       │ user_id ─────────────────►┤
  │                                   │
  │   issue_comments ◄─────────────── │
  │       │ author_id ───────────────►┤
  │       │ parent_id → issue_comments │(self-ref)
  │                                   │
  │   issue_attachments ◄─────────── │
  │       │ uploader_id ────────────►┤
  │                                  │
  │   notifications ◄──────────────  │
  │       │ user_id ───────────────►┘
  │
  └── refresh_tokens
      email_verification_tokens
      password_reset_tokens
```

---

## Indexes — Making Queries Fast

Without indexes, every query scans the entire table (O(n)). Indexes allow O(log n) lookups.

```sql
-- PostgreSQL creates indexes automatically for:
-- - PRIMARY KEY (always indexed)
-- - UNIQUE constraints

-- But we also need indexes for frequently queried foreign keys:

-- "Give me all issues in project 42"
CREATE INDEX idx_issues_project_id ON issues(project_id);

-- "Give me all unread notifications for user 1"
CREATE INDEX idx_notifications_user_read ON notifications(user_id, read);

-- "Give me all project members for project 42"
CREATE INDEX idx_project_members_project_id ON project_members(project_id);

-- "Find refresh token by hash"
-- (Already covered by UNIQUE constraint on token_hash)
```

B-Tree index structure (the default):
```
                    [50]
                   /    \
              [25]        [75]
             /    \      /    \
          [10]   [35] [60]   [90]
         /   \
        [5] [15]

Query: "Find all issues with project_id = 25"
  1. Start at root [50]: 25 < 50, go left
  2. At [25]: found! Follow pointer to data
  O(log n) instead of scanning every row
```

---

## Indexes in SQLAlchemy Models

In this project, indexes are defined in the SQLAlchemy models:

```python
# backend/app/models/issue.py

class Issue(Base):
    __tablename__ = "issues"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[IssueStatus] = mapped_column(
        SQLAlchemyEnum(IssueStatus),
        default=IssueStatus.TODO,
        index=True  # Creates idx_issues_status
    )
    priority: Mapped[IssuePriority] = mapped_column(
        SQLAlchemyEnum(IssuePriority),
        default=IssuePriority.MEDIUM,
        index=True  # Creates idx_issues_priority
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True  # Creates idx_issues_project_id
    )
    
    __table_args__ = (
        # Composite index for common filter combination
        Index("idx_issues_project_status", "project_id", "status"),
    )
```

---

## PostgreSQL vs Other Databases

| Feature | PostgreSQL | MySQL | MongoDB | SQLite |
|---------|-----------|-------|---------|--------|
| ACID | Full | Full (InnoDB) | Partial | Full |
| JSON support | Excellent | Good | Native | Limited |
| Full-text search | Built-in | Built-in | Built-in | Limited |
| Concurrent reads | MVCC | MVCC | Lock-based | Lock-based |
| Async Python | asyncpg (fast) | aiomysql | motor | aiosqlite |
| AWS managed | RDS | RDS | DocumentDB | - |
| Use when | Complex relations | Simple apps | Documents/schema-less | Local/testing |

PostgreSQL is the right choice here because:
- Our data is structured and highly relational
- We need ACID guarantees (data integrity)
- We use complex queries with joins
- Full-text search for issue search
- Excellent async Python support via asyncpg

---

## RDS Tuning Parameters

In production (AWS RDS), we tune PostgreSQL:

```
max_connections = 500
  (How many concurrent DB connections)
  With HPA: max 30 backend pods × 5 connections each = 150 connections
  Workers: max 15 × 2 = 30 connections
  Buffer: 500 gives headroom

work_mem = 4096KB (4MB)
  Memory per sort/hash operation
  With 30 connections: up to 120MB for sort operations
  Tuned for our query complexity

maintenance_work_mem = 131072KB (128MB)
  Memory for VACUUM, CREATE INDEX, etc.
  Higher = faster index creation

log_min_duration_statement = 500ms
  Log queries taking longer than 500ms
  Helps identify slow queries for optimization
```

---

## Query Execution Plan

Use `EXPLAIN ANALYZE` to see how PostgreSQL executes a query:

```sql
EXPLAIN ANALYZE
SELECT i.*, u.name as assignee_name
FROM issues i
JOIN issue_assignees ia ON i.id = ia.issue_id
JOIN users u ON ia.user_id = u.id
WHERE i.project_id = 1
  AND i.status = 'IN_PROGRESS';

-- Output:
Nested Loop  (cost=0.42..45.67 rows=12 width=285) (actual time=0.051..0.234 rows=8 loops=1)
  -> Index Scan using idx_issues_project_status on issues i
       (actual time=0.032..0.089 rows=8 loops=1)
       Index Cond: ((project_id = 1) AND (status = 'IN_PROGRESS'))
  -> Index Scan using issue_assignees_pkey on issue_assignees ia
       (actual time=0.012..0.018 rows=1 loops=8)
  -> Index Scan using users_pkey on users u
       (actual time=0.008..0.009 rows=1 loops=8)
Planning Time: 0.248 ms
Execution Time: 0.312 ms
```

This shows our composite index `idx_issues_project_status` is being used — no table scans.

---

## Further Reading & Videos

- **YouTube**: Search "PostgreSQL Tutorial for Beginners" — Tech With Tim
- **YouTube**: Search "PostgreSQL Internals" — Hussein Nasser covers MVCC, WAL deeply
- **YouTube**: Search "Database Indexing Explained" — Computerphile or Hussein Nasser
- **Official Docs**: [PostgreSQL documentation](https://www.postgresql.org/docs/) — extremely comprehensive
- **Interactive**: [pgexercises.com](https://pgexercises.com) — practice SQL with PostgreSQL

---

*Next: [Module 04-02 — SQLAlchemy Async ORM](./02-sqlalchemy-orm.md)*
