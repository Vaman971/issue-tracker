from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Label(Base):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Hex color e.g. "#FF5733"
    color: Mapped[str] = mapped_column(String(7), default="#6B7280", nullable=False)

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_label_project_name"),)

    project = relationship("Project", foreign_keys=[project_id])


class IssueLabel(Base):
    """Many-to-many join table between Issue and Label."""

    __tablename__ = "issue_labels"

    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        primary_key=True,
    )

    label_id: Mapped[int] = mapped_column(
        ForeignKey("labels.id", ondelete="CASCADE"),
        primary_key=True,
    )

    issue = relationship("Issue", foreign_keys=[issue_id])
    label = relationship("Label", foreign_keys=[label_id])
