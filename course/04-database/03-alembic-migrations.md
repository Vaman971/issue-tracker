# Module 04-03 — Alembic: Database Migrations & Version Control

---

## Learning Objectives

After this module you will:
- Understand why database migrations are necessary
- Know how Alembic tracks schema versions
- Be able to create and run migrations
- Understand how migrations run in production (Kubernetes Job)

---

## The Problem: Schema Evolution

Your database schema changes as your application evolves:

```
Week 1: Initial launch
  - users table (id, email, password, created_at)

Week 3: Add user profiles
  - ALTER TABLE users ADD COLUMN avatar_url VARCHAR(255);

Week 6: Add projects
  - CREATE TABLE projects (...)

Week 10: Multiple assignees per issue
  - CREATE TABLE issue_assignees (...)
  - DELETE FROM issues WHERE assignees is array column  ← breaking change!
  - ...

Question: How do you apply these changes to:
  - Your local development database?
  - Your teammate's database?
  - The staging environment?
  - The production database?
  
Without migrations: "It works on my machine" → schema inconsistency → bugs
With migrations: Every change is versioned, repeatable, reversible
```

---

## How Alembic Works

Alembic maintains a table in your database called `alembic_version` that tracks which migrations have been applied:

```
alembic_version table:
┌────────────────────────┐
│ version_num            │
├────────────────────────┤
│ 20260602_multiple_     │
│ assignees              │  ← current schema version
└────────────────────────┘
```

Migration files are Python scripts in `alembic/versions/`:
```
backend/alembic/versions/
├── 7b8c8e36d504_create_initial_tables.py
├── 20260527_add_refresh_tokens.py
├── 20260601_v2_feature_expansion.py
└── 20260602_multiple_assignees.py
```

Each file has a `revision` ID and points to the `down_revision` (previous migration):

```
None
  │ (initial migration)
  ▼
7b8c8e36d504_create_initial_tables
  │
  ▼
20260527_add_refresh_tokens
  │
  ▼
20260601_v2_feature_expansion
  │
  ▼
20260602_multiple_assignees   ← HEAD (latest)
```

`alembic upgrade head` runs all unapplied migrations in order.

---

## Migration File Structure

```python
# backend/alembic/versions/20260602_multiple_assignees.py

"""Add multiple assignees support

Revision ID: a1b2c3d4e5f6
Revises: prev_revision_id
Create Date: 2026-06-02 10:00:00
"""

from alembic import op
import sqlalchemy as sa

# Metadata about this migration
revision = "a1b2c3d4e5f6"
down_revision = "prev_revision_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration — make the schema changes."""
    
    # Create the new junction table
    op.create_table(
        "issue_assignees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["issue_id"], ["issues.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issue_id", "user_id"),
    )
    
    op.create_index(
        "ix_issue_assignees_issue_id",
        "issue_assignees",
        ["issue_id"]
    )
    
    # Migrate existing data: move old assignee_id column data
    # to the new junction table
    op.execute("""
        INSERT INTO issue_assignees (issue_id, user_id, assigned_at)
        SELECT id, assignee_id, created_at
        FROM issues
        WHERE assignee_id IS NOT NULL
    """)
    
    # Remove old single-assignee column (it's now in the junction table)
    op.drop_column("issues", "assignee_id")


def downgrade() -> None:
    """Reverse the migration — undo the schema changes."""
    
    # Add back the old single-assignee column
    op.add_column(
        "issues",
        sa.Column("assignee_id", sa.Integer(), nullable=True)
    )
    
    # Migrate data back (keep only the first assignee per issue)
    op.execute("""
        UPDATE issues i
        SET assignee_id = (
            SELECT user_id FROM issue_assignees
            WHERE issue_id = i.id
            ORDER BY assigned_at
            LIMIT 1
        )
    """)
    
    # Drop the junction table
    op.drop_index("ix_issue_assignees_issue_id")
    op.drop_table("issue_assignees")
```

---

## Alembic Configuration

```ini
# backend/alembic.ini

[alembic]
script_location = alembic
file_template = %%(year)d%(month).2d%(day).2d_%%(slug)s
sqlalchemy.url = driver://user:pass@host/dbname
; ^ This is overridden by env.py to use our settings
```

```python
# backend/alembic/env.py

from app.core.config import settings
from app.db.base import Base
# Import all models so Base.metadata knows about them
import app.models  # noqa

def run_migrations_online():
    """Run migrations against a live database."""
    
    connectable = create_engine(
        settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
        # Alembic uses sync engine (even in async apps)
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,  # Your SQLAlchemy model metadata
        )
        
        with context.begin_transaction():
            context.run_migrations()
```

---

## The Migration Script

```bash
# backend/scripts/migrate.sh

#!/bin/bash
set -e  # Exit immediately on error

echo "Running database migrations..."
alembic upgrade head

echo "Seeding initial data..."
python -m app.db.seed

echo "Migration complete."
```

---

## Migration Commands

```bash
# Apply all pending migrations (move forward to latest)
alembic upgrade head

# Apply one migration
alembic upgrade +1

# Roll back one migration
alembic downgrade -1

# Roll back to specific version
alembic downgrade 7b8c8e36d504

# Roll back everything
alembic downgrade base

# Show current version
alembic current

# Show migration history
alembic history --verbose

# Generate a new migration from model changes
alembic revision --autogenerate -m "add_avatar_url_to_users"
```

### Autogenerate — The Killer Feature

Alembic can detect changes in your SQLAlchemy models and generate migration SQL automatically:

```python
# You add a column to your User model:
avatar_url: Mapped[str | None] = mapped_column(String(255))

# Then run:
alembic revision --autogenerate -m "add avatar_url"

# Alembic compares your models to the current database schema
# and generates:
def upgrade():
    op.add_column('users', sa.Column('avatar_url', sa.String(255), nullable=True))

def downgrade():
    op.drop_column('users', 'avatar_url')
```

You should always **review autogenerated migrations** before applying them — Alembic can miss some changes (renaming columns, complex constraints).

---

## Migration in Production — Kubernetes Job

In production, migrations run as a **Kubernetes Job** — a one-time task that runs to completion and exits:

```yaml
# infra/kubernetes/jobs/migrate-job.yaml

apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate
  namespace: issue-tracker
spec:
  # Retry up to 3 times if migration fails
  backoffLimit: 3
  
  template:
    spec:
      # Don't restart the pod after it completes
      restartPolicy: OnFailure
      
      containers:
        - name: migrate
          image: ${ECR_REGISTRY}/issue-tracker-backend:${IMAGE_TAG}
          command: ["/bin/sh", "-c", "/app/scripts/migrate.sh"]
          
          # Use same environment variables as the backend
          envFrom:
            - configMapRef:
                name: app-config
            - secretRef:
                name: app-secrets
      
      # Must complete within 5 minutes
      activeDeadlineSeconds: 300
```

Deployment sequence:
```
GitHub Actions CI/CD:

1. Build new Docker image
2. Push to ECR
3. Apply Kubernetes Job (migrate-job.yaml)
4. Wait for Job to complete successfully
5. Update Deployment image tags
6. Rollout new pods (rolling update)

If migration fails → Job fails → Deployment stops
(Protects against deploying incompatible code with old schema)
```

---

## Migration Best Practices

### 1. Always Write Reversible Migrations

```python
# GOOD — reversible
def downgrade():
    op.drop_column('users', 'avatar_url')

# BAD — data loss, can't reverse
def downgrade():
    pass  # Nothing to do, column is gone
```

### 2. Separate Schema Changes from Data Migrations

```python
# WRONG — dangerous mix
def upgrade():
    op.add_column('issues', sa.Column('priority_level', sa.Integer()))
    op.execute("UPDATE issues SET priority_level = CASE priority WHEN 'LOW' THEN 1 ...")
    op.drop_column('issues', 'priority')  # Schema + data change in one step

# BETTER — separate migrations
# Migration 1: Add new column
# Migration 2: Copy data
# Migration 3: Drop old column (after verifying data is correct)
```

### 3. Zero-Downtime Migrations

Avoid migrations that lock tables for long periods (on large tables):

```python
# BAD for large tables (locks table during index creation)
op.create_index("idx_issues_status", "issues", ["status"])

# GOOD (CONCURRENTLY doesn't lock — but can't run in a transaction)
op.execute("CREATE INDEX CONCURRENTLY idx_issues_status ON issues(status)")
```

---

## Migration History in This Project

```
7b8c8e36d504_create_initial_tables.py
  - Creates: users, projects, project_members, issues
    issue_comments, issue_attachments, labels, issue_labels
    notifications, activities

20260527_add_refresh_tokens.py
  - Creates: refresh_tokens table
  - (Security improvement: store refresh tokens server-side)

20260601_v2_feature_expansion.py
  - Creates: email_verification_tokens
  - Creates: password_reset_tokens
  - Adds: email_verified column to users
  - Adds: avatar_url column to users
  - (V2 feature expansion sprint)

20260602_multiple_assignees.py
  - Creates: issue_assignees junction table
  - Migrates: existing assignee_id column data
  - Drops: old single assignee_id column from issues
  - (Changed from single assignee to multiple assignees)
```

---

## Further Reading & Videos

- **YouTube**: Search "Alembic Database Migrations Tutorial" — clear walkthrough of common commands
- **YouTube**: Search "Database Migration Zero Downtime" — covers production-safe strategies
- **Official Docs**: [Alembic documentation](https://alembic.sqlalchemy.org)
- **Patterns**: [Evolutionary Database Design by Martin Fowler](https://martinfowler.com/articles/evodb.html)

---

*Next: [Module 05-01 — Redis: Internals, Caching & Pub/Sub](../05-caching-storage/01-redis-caching.md)*
