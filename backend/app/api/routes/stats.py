"""Stats & analytics — project-level and system-wide dashboards."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.rbac import require_roles
from app.db.session import get_db
from app.models.issue import Issue, IssueStatus
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole

router = APIRouter(tags=["stats"])


@router.get("/projects/{project_id}/stats")
async def project_stats(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Access check
    can_view = current_user.role == UserRole.ADMIN or project.leader_id == current_user.id
    if not can_view:
        member = (await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
            )
        )).scalar_one_or_none()
        can_view = member is not None

    if not can_view:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Issue counts by status
    status_counts: dict[str, int] = {s.value: 0 for s in IssueStatus}
    rows = await db.execute(
        select(Issue.status, func.count())
        .where(Issue.project_id == project_id)
        .group_by(Issue.status)
    )
    for row_status, count in rows:
        status_counts[row_status.value] = count

    # Member count
    member_count_result = await db.execute(
        select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == project_id)
    )
    member_count = member_count_result.scalar_one()

    # Total issues
    total_result = await db.execute(
        select(func.count()).select_from(Issue).where(Issue.project_id == project_id)
    )
    total_issues = total_result.scalar_one()

    return {
        "project_id": project_id,
        "project_name": project.name,
        "total_issues": total_issues,
        "issues_by_status": status_counts,
        "member_count": member_count,
        "completion_rate": round(status_counts.get("done", 0) / total_issues * 100, 1) if total_issues else 0,
    }


@router.get("/admin/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    total_projects = (await db.execute(select(func.count()).select_from(Project))).scalar_one()
    total_issues = (await db.execute(select(func.count()).select_from(Issue))).scalar_one()

    # Issues by status across all projects
    status_counts: dict[str, int] = {s.value: 0 for s in IssueStatus}
    rows = await db.execute(select(Issue.status, func.count()).group_by(Issue.status))
    for row_status, count in rows:
        status_counts[row_status.value] = count

    # Users by role
    role_counts: dict[str, int] = {}
    role_rows = await db.execute(select(User.role, func.count()).group_by(User.role))
    for row_role, count in role_rows:
        role_counts[row_role.value] = count

    return {
        "total_users": total_users,
        "total_projects": total_projects,
        "total_issues": total_issues,
        "issues_by_status": status_counts,
        "users_by_role": role_counts,
        "completion_rate": round(
            status_counts.get("done", 0) / total_issues * 100, 1
        ) if total_issues else 0,
    }
