from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.db.base import Base

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True
    )

    description:Mapped[str] = mapped_column(
        String(1000),
        nullable=True
    )

    leader_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), # as every leader must be a valid user first
        nullable=False,
    )

    leader = relationship("User", foreign_keys=[leader_id]) # this helps in attcahing the user data alogside with project data

