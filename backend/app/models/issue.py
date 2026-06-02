import enum

from sqlalchemy import Enum, String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IssueStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"

class IssuePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Issue(Base):

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus),
        default=IssueStatus.TODO,
        nullable=False,
    )

    priority: Mapped[IssuePriority] = mapped_column(
        Enum(IssuePriority),
        default=IssuePriority.MEDIUM,
        nullable=False
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False
    )

    creator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    # its a good practie to keep the forein_keys variable assigned, as if a table points to the same table twice with differenct foreign keys, then sqlalchemy will get confused
    project = relationship("Project", foreign_keys=[project_id])
    creator = relationship("User", foreign_keys=[creator_id])
    labels = relationship("Label", secondary="issue_labels", viewonly=True)
    assignees = relationship("User", secondary="issue_assignees", viewonly=True)
