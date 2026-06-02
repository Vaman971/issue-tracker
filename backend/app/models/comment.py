from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IssueComment(Base):
    __tablename__ = "issue_comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Null means top-level comment; set to parent comment id for replies
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("issue_comments.id", ondelete="CASCADE"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    issue = relationship("Issue", foreign_keys=[issue_id])
    author = relationship("User", foreign_keys=[author_id])
    replies = relationship(
        "IssueComment",
        foreign_keys=[parent_id],
        back_populates="parent",
    )
    parent = relationship(
        "IssueComment",
        foreign_keys=[parent_id],
        back_populates="replies",
        remote_side="IssueComment.id",
    )
