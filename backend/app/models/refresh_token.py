from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class RefreshToken(Base):

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # JWT id, a unique id inside each refresh token
    jti: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    # the time at which this token was cancelled
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    # tells us which new token replaced the old one
    replaced_by_jti: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True
    )

    user = relationship("User")