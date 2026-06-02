import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ActivityAction(str, enum.Enum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    PRIORITY_CHANGED = "priority_changed"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    TITLE_CHANGED = "title_changed"
    DESCRIPTION_CHANGED = "description_changed"
    LABEL_ADDED = "label_added"
    LABEL_REMOVED = "label_removed"
    COMMENT_ADDED = "comment_added"
    ATTACHMENT_ADDED = "attachment_added"
    ATTACHMENT_REMOVED = "attachment_removed"


class IssueActivity(Base):
    __tablename__ = "issue_activities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    action: Mapped[ActivityAction] = mapped_column(
        Enum(ActivityAction, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    issue = relationship("Issue", foreign_keys=[issue_id])
    actor = relationship("User", foreign_keys=[actor_id])
