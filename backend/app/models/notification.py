import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NotificationType(str, enum.Enum):
    ISSUE_CREATED = "issue_created"
    ISSUE_ASSIGNED = "issue_assigned"
    ISSUE_STATUS_CHANGED = "issue_status_changed"
    ISSUE_COMMENTED = "issue_commented"
    ISSUE_UPDATED = "issue_updated"
    PROJECT_MEMBER_ADDED = "project_member_added"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFIED = "email_verified"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, values_callable=lambda x: [e.value for e in x]),  nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # JSON-serialised extra data (issue_id, project_id, etc.)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", foreign_keys=[user_id])
