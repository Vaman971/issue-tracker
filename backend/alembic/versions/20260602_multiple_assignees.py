"""multiple assignees: replace single assignee_id with issue_assignees join table

Revision ID: 20260602_assignees
Revises: 20260601_v2
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "20260602_assignees"
down_revision = "20260601_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "issue_assignees",
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("issue_id", "user_id"),
    )
    op.create_index("ix_issue_assignees_issue_id", "issue_assignees", ["issue_id"])
    op.create_index("ix_issue_assignees_user_id", "issue_assignees", ["user_id"])

    # Migrate existing single-assignee data into the new join table
    op.execute(
        "INSERT INTO issue_assignees (issue_id, user_id) "
        "SELECT id, assignee_id FROM issues WHERE assignee_id IS NOT NULL"
    )

    # Drop the now-redundant column
    op.drop_column("issues", "assignee_id")


def downgrade() -> None:
    op.add_column("issues", sa.Column("assignee_id", sa.Integer(), nullable=True))

    # Restore first assignee per issue (best-effort)
    op.execute(
        "UPDATE issues SET assignee_id = ("
        "  SELECT user_id FROM issue_assignees"
        "  WHERE issue_assignees.issue_id = issues.id"
        "  LIMIT 1"
        ")"
    )

    op.drop_index("ix_issue_assignees_user_id", table_name="issue_assignees")
    op.drop_index("ix_issue_assignees_issue_id", table_name="issue_assignees")
    op.drop_table("issue_assignees")
