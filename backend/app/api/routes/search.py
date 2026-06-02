"""Search — full-text keyword search across projects and issues."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.issue import Issue
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole
from app.schemas.issue import IssueRead
from app.schemas.project import ProjectRead

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/")
async def search(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    term = f"%{q}%"

    # Determine which project IDs the user can see
    if current_user.role == UserRole.ADMIN:
        visible_project_ids = None  # all
    else:
        led = (await db.execute(
            select(Project.id).where(Project.leader_id == current_user.id)
        )).scalars().all()

        memberships = (await db.execute(
            select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id)
        )).scalars().all()

        visible_project_ids = list(set(list(led) + list(memberships)))

    # Search projects
    proj_q = (
        select(Project)
        .where(or_(Project.name.ilike(term), Project.description.ilike(term)))
        .options(selectinload(Project.leader))
    )
    if visible_project_ids is not None:
        proj_q = proj_q.where(Project.id.in_(visible_project_ids))

    projects_result = await db.execute(proj_q.offset(skip).limit(limit))
    projects = projects_result.scalars().all()

    # Search issues
    issue_q = (
        select(Issue)
        .where(or_(Issue.title.ilike(term), Issue.description.ilike(term)))
        .options(
            selectinload(Issue.labels),
            selectinload(Issue.assignees),
            selectinload(Issue.creator),
        )
    )
    if visible_project_ids is not None:
        issue_q = issue_q.where(Issue.project_id.in_(visible_project_ids))

    issues_result = await db.execute(issue_q.offset(skip).limit(limit))
    issues = issues_result.scalars().all()

    return {
        "query": q,
        "projects": [ProjectRead.model_validate(p) for p in projects],
        "issues": [IssueRead.model_validate(i) for i in issues],
    }
