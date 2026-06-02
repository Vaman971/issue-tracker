from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from collections.abc import Sequence

from app.models.issue import Issue
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole

async def get_project_or_404(
    project_id: int,
    db: AsyncSession,
) -> Project:
    project_result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.leader))
    )

    project = project_result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return project

async def get_issue_or_404(
    issue_id: int,
    db: AsyncSession,
) -> Issue:
    issue_result = await db.execute(
        select(Issue)
        .where(Issue.id == issue_id)
        .options(
            selectinload(Issue.labels),
            selectinload(Issue.assignees),
            selectinload(Issue.creator),
        )
    )

    issue = issue_result.scalar_one_or_none()

    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )

    return issue


async def is_project_member(
    project_id: int,
    user_id: int,
    db: AsyncSession,
) -> bool:
    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )

    return member_result.scalar_one_or_none() is not None

async def list_visible_issues(
    current_user: User,
    db: AsyncSession,
    skip: int,
    limit: int,
    q: str | None = None,
) -> Sequence[Issue]:
    _eager = [
        selectinload(Issue.labels),
        selectinload(Issue.assignees),
        selectinload(Issue.creator),
    ]

    if current_user.role == UserRole.ADMIN:
        stmt = select(Issue).options(*_eager)
    elif current_user.role == UserRole.PROJECT_LEADER:
        stmt = (
            select(Issue)
            .join(Project, Issue.project_id == Project.id)
            .where(Project.leader_id == current_user.id)
            .options(*_eager)
        )
    else:
        stmt = (
            select(Issue)
            .join(ProjectMember, Issue.project_id == ProjectMember.project_id)
            .where(ProjectMember.user_id == current_user.id)
            .options(*_eager)
        )

    if q:
        term = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Issue.title).like(term),
                func.lower(Issue.description).like(term),
            )
        )

    result = await db.execute(stmt.order_by(Issue.id).offset(skip).limit(limit))
    return result.scalars().all()

async def ensure_can_create_issue_in_project(
    current_user: User,
    project: Project,
    db: AsyncSession,
) -> None:
    is_admin = current_user.role == UserRole.ADMIN
    is_project_leader = (
        current_user.role == UserRole.PROJECT_LEADER
        and project.leader_id == current_user.id
    )

    is_member = await is_project_member(
        project_id=project.id,
        user_id=current_user.id,
        db=db,
    )

    can_create_as_member = (
        current_user.role in {UserRole.DEVELOPER, UserRole.QA}
        and is_member
    )

    if not is_admin and not is_project_leader and not can_create_as_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create issues in this project"
        )

async def get_issue_update_scope(
    current_user: User,
    project: Project,
    db: AsyncSession,
) -> str:
    is_admin = current_user.role == UserRole.ADMIN
    is_project_leader = (
        current_user.role == UserRole.PROJECT_LEADER
        and project.leader_id == current_user.id
    )

    if is_admin or is_project_leader:
        return "full"

    is_member = await is_project_member(
        project_id=project.id,
        user_id=current_user.id,
        db=db,
    )

    can_update_as_member = (
        current_user.role in {UserRole.DEVELOPER, UserRole.QA}
        and is_member
    )

    if can_update_as_member:
        return "status_only"

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You cannot update this issue"
    )


def ensure_status_only_update(update_data: dict) -> None:
    forbidden_fields = set(update_data) - {"status"}

    if forbidden_fields:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project members can only update issue status"
        )


async def validate_issue_assignees(
    assignee_ids: list[int],
    project: Project,
    db: AsyncSession,
) -> None:
    for assignee_id in assignee_ids:
        await _validate_single_assignee(assignee_id, project, db)


async def _validate_single_assignee(
    assignee_id: int,
    project: Project,
    db: AsyncSession,
) -> None:
    user_result = await db.execute(select(User).where(User.id == assignee_id))
    assignee = user_result.scalar_one_or_none()

    if assignee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignee {assignee_id} not found"
        )

    if not assignee.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Assignee {assignee_id} is not active"
        )

    # Admins can always be assigned
    if assignee.role == UserRole.ADMIN:
        return

    # The project's own leader is always valid
    if project.leader_id == assignee.id:
        return

    # Any active project member (any role, including viewer) is valid
    if await is_project_member(project_id=project.id, user_id=assignee.id, db=db):
        return

    # Project leaders of OTHER projects can be cross-assigned
    if assignee.role == UserRole.PROJECT_LEADER:
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"User {assignee_id} cannot be assigned: must be a project member, "
            "admin, or project leader"
        )
    )
