from fastapi import HTTPException, status
from sqlalchemy import select
from collections.abc import Sequence
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole


async def get_user_or_404(
    user_id: int,
    db: AsyncSession,
) -> User:
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )

    user = user_result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


async def validate_project_leader(
    leader_id: int,
    db: AsyncSession,
) -> User:
    leader = await get_user_or_404(
        user_id=leader_id,
        db=db,
    )

    if leader.role not in [UserRole.PROJECT_LEADER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project leader must have project_leader or admin role"
        )

    return leader


def ensure_can_manage_project_members(
    project: Project,
    current_user: User,
) -> None:
    is_admin = current_user.role == UserRole.ADMIN
    is_project_leader = (
        current_user.role == UserRole.PROJECT_LEADER
        and project.leader_id == current_user.id
    )

    if not is_admin and not is_project_leader:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can not manage members for this project"
        )


async def validate_project_member_candidate(
    project: Project,
    member_user: User,
    db: AsyncSession,
) -> None:
    if member_user.id == project.leader_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project leader is already assigned to this project"
        )

    existing_member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == member_user.id,
        )
    )

    existing_member = existing_member_result.scalar_one_or_none()

    if existing_member is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this project"
        )


async def list_visible_projects(
    current_user: User,
    db: AsyncSession,
) -> Sequence[Project]:
    if current_user.role == UserRole.ADMIN:
        result = await db.execute(
            select(Project).order_by(Project.id)
        )
        return result.scalars().all()

    if current_user.role == UserRole.PROJECT_LEADER:
        result = await db.execute(
            select(Project)
            .where(Project.leader_id == current_user.id)
            .order_by(Project.id)
        )
        return result.scalars().all()

    result = await db.execute(
        select(Project)
        .join(ProjectMember, Project.id == ProjectMember.project_id)
        .where(ProjectMember.user_id == current_user.id)
        .order_by(Project.id)
    )

    return result.scalars().all()