"""Issue activity log — read-only audit trail per issue."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.activity import IssueActivity
from app.models.issue import Issue
from app.models.project_member import ProjectMember
from app.models.project import Project
from app.models.user import User, UserRole
from app.schemas.activity import ActivityRead

router = APIRouter(prefix="/issues/{issue_id}/activity", tags=["activity"])


async def _can_access_issue(issue_id: int, user: User, db: AsyncSession) -> Issue:
    issue_result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = issue_result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    if user.role == UserRole.ADMIN:
        return issue

    project_result = await db.execute(select(Project).where(Project.id == issue.project_id))
    project = project_result.scalar_one_or_none()
    if project and project.leader_id == user.id:
        return issue

    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == issue.project_id,
            ProjectMember.user_id == user.id,
        )
    )
    if member_result.scalar_one_or_none() is not None:
        return issue

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


@router.get("/", response_model=list[ActivityRead])
async def get_issue_activity(
    issue_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _can_access_issue(issue_id, current_user, db)

    result = await db.execute(
        select(IssueActivity)
        .where(IssueActivity.issue_id == issue_id)
        .options(selectinload(IssueActivity.actor))
        .order_by(IssueActivity.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()
