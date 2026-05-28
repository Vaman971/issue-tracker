from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class ProjectMember(Base):

    __tablename__ = "project_members"

    __table_args__ = (
        # Helps prevent the bug which makes an entry been added to a table more then once 
        UniqueConstraint(
            "project_id",
            "user_id",
            name="uq_project_member_project_user"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    project = relationship("Project")
    user = relationship("User")
