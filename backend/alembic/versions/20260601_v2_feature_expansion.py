"""v2 feature expansion: user profile fields, comments, attachments, labels, notifications, activity, password reset, email verification

Revision ID: 20260601_v2
Revises: 20260527_add_refresh_tokens
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa

revision = "20260601_v2"
down_revision = "20260527_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users: add new columns
    # ------------------------------------------------------------------
    op.add_column("users", sa.Column("full_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("avatar_key", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"))
    op.add_column("users", sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="0"))

    # ------------------------------------------------------------------
    # issue_comments
    # ------------------------------------------------------------------
    op.create_table(
        "issue_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["issue_comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_issue_comments_id", "issue_comments", ["id"])
    op.create_index("ix_issue_comments_issue_id", "issue_comments", ["issue_id"])

    # ------------------------------------------------------------------
    # issue_attachments
    # ------------------------------------------------------------------
    op.create_table(
        "issue_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("uploader_id", sa.Integer(), nullable=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("file_key", sa.String(1024), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_issue_attachments_id", "issue_attachments", ["id"])
    op.create_index("ix_issue_attachments_issue_id", "issue_attachments", ["issue_id"])

    # ------------------------------------------------------------------
    # labels
    # ------------------------------------------------------------------
    op.create_table(
        "labels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(7), nullable=False, server_default="#6B7280"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_label_project_name"),
    )
    op.create_index("ix_labels_id", "labels", ["id"])
    op.create_index("ix_labels_project_id", "labels", ["project_id"])

    # ------------------------------------------------------------------
    # issue_labels (M2M join)
    # ------------------------------------------------------------------
    op.create_table(
        "issue_labels",
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["label_id"], ["labels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("issue_id", "label_id"),
    )

    # ------------------------------------------------------------------
    # notifications
    # ------------------------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "issue_created",
                "issue_assigned",
                "issue_status_changed",
                "issue_commented",
                "issue_updated",
                "project_member_added",
                "password_reset",
                "email_verified",
                name="notificationtype",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("meta", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    # ------------------------------------------------------------------
    # issue_activities
    # ------------------------------------------------------------------
    op.create_table(
        "issue_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
                "created",
                "status_changed",
                "priority_changed",
                "assigned",
                "unassigned",
                "title_changed",
                "description_changed",
                "label_added",
                "label_removed",
                "comment_added",
                "attachment_added",
                "attachment_removed",
                name="activityaction",
            ),
            nullable=False,
        ),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_issue_activities_id", "issue_activities", ["id"])
    op.create_index("ix_issue_activities_issue_id", "issue_activities", ["issue_id"])

    # ------------------------------------------------------------------
    # password_reset_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_password_reset_tokens_id", "password_reset_tokens", ["id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    # ------------------------------------------------------------------
    # email_verification_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_verification_tokens_id", "email_verification_tokens", ["id"])
    op.create_index("ix_email_verification_tokens_token_hash", "email_verification_tokens", ["token_hash"], unique=True)
    op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_table("email_verification_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_table("issue_activities")
    op.drop_table("notifications")
    op.drop_table("issue_labels")
    op.drop_table("labels")
    op.drop_table("issue_attachments")
    op.drop_table("issue_comments")

    op.drop_column("users", "is_email_verified")
    op.drop_column("users", "is_active")
    op.drop_column("users", "avatar_key")
    op.drop_column("users", "full_name")
