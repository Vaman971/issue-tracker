from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IssueAttachment(Base):
    __tablename__ = "issue_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    uploader_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)

    # Storage key: local relative path or S3 object key
    file_key: Mapped[str] = mapped_column(String(1024), nullable=False)

    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    issue = relationship("Issue", foreign_keys=[issue_id])
    uploader = relationship("User", foreign_keys=[uploader_id])
