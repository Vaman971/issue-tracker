from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.api.helpers.issue_helper import get_project_or_404
from app.api.helpers.project_helper import (
    ensure_can_manage_project_members,
    get_user_or_404,
    list_visible_projects,
    validate_project_leader,
    validate_project_member_candidate,
)
from app.api.rbac import require_roles
from app.db.session import get_db
from app.models.activity import IssueActivity
from app.models.attachment import IssueAttachment
from app.models.comment import IssueComment
from app.models.issue import Issue
from app.models.issue_assignee import IssueAssignee
from app.models.label import IssueLabel, Label
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole
from app.schemas.issue import IssueRead
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.project_member import ProjectMemberAddRequest, ProjectMemberWithUserRead
from app.schemas.user import UserRead
from app.services.cache import cache_delete_pattern, cache_get_json, cache_set_json
from app.services.storage import delete_file

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
)


def _build_projects_cache_key(
    current_user: User, q: str | None = None, skip: int = 0, limit: int = 12
) -> str:
    q_part = f":{q}" if q else ""
    return f"projects:list:{current_user.id}:{current_user.role.value}:{skip}:{limit}{q_part}"


async def _can_view_project(project: Project, user: User, db: AsyncSession) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    if project.leader_id == user.id:
        return True
    member = (await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id,
        )
    )).scalar_one_or_none()
    return member is not None


@router.post(
    "/",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await validate_project_leader(
        leader_id=payload.leader_id,
        db=db,
    )

    project = Project(
        name=payload.name,
        description=payload.description,
        leader_id=payload.leader_id,
    )

    db.add(project)
    await db.commit()

    await cache_delete_pattern("projects:list:*")

    return await get_project_or_404(project_id=project.id, db=db)


@router.get("/", response_model=list[ProjectRead])
async def list_projects(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=12, ge=1, le=100),
    q: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cache_key = _build_projects_cache_key(current_user, q, skip, limit)
    cached_projects = await cache_get_json(cache_key)

    if cached_projects is not None:
        return cached_projects

    projects = await list_visible_projects(
        current_user=current_user,
        db=db,
        q=q,
        skip=skip,
        limit=limit,
    )
    serialized_projects = [
        ProjectRead.model_validate(project).model_dump(mode="json")
        for project in projects
    ]

    await cache_set_json(cache_key, serialized_projects)

    return serialized_projects


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_or_404(project_id=project_id, db=db)

    if not await _can_view_project(project, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return project


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_or_404(project_id=project_id, db=db)

    update_data = payload.model_dump(exclude_unset=True)

    if "leader_id" in update_data:
        await validate_project_leader(leader_id=update_data["leader_id"], db=db)

    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()

    await cache_delete_pattern("projects:list:*")

    return await get_project_or_404(project_id=project_id, db=db)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_or_404(project_id=project_id, db=db)

    issue_ids_result = await db.execute(
        select(Issue.id).where(Issue.project_id == project_id)
    )
    issue_ids = [row[0] for row in issue_ids_result]

    if issue_ids:
        attachments = (await db.execute(
            select(IssueAttachment).where(IssueAttachment.issue_id.in_(issue_ids))
        )).scalars().all()
        for att in attachments:
            await delete_file(att.file_key)

        await db.execute(sa_delete(IssueAssignee).where(IssueAssignee.issue_id.in_(issue_ids)))
        await db.execute(sa_delete(IssueLabel).where(IssueLabel.issue_id.in_(issue_ids)))
        await db.execute(sa_delete(IssueAttachment).where(IssueAttachment.issue_id.in_(issue_ids)))
        await db.execute(sa_delete(IssueActivity).where(IssueActivity.issue_id.in_(issue_ids)))
        await db.execute(sa_delete(IssueComment).where(
            IssueComment.issue_id.in_(issue_ids),
            IssueComment.parent_id.isnot(None),
        ))
        await db.execute(sa_delete(IssueComment).where(IssueComment.issue_id.in_(issue_ids)))

    await db.execute(sa_delete(Label).where(Label.project_id == project_id))
    await db.execute(sa_delete(ProjectMember).where(ProjectMember.project_id == project_id))
    await db.execute(sa_delete(Issue).where(Issue.project_id == project_id))

    await db.delete(project)
    await db.commit()

    await cache_delete_pattern("projects:list:*")
    await cache_delete_pattern("issues:list:*")


# ---------------------------------------------------------------------------
# Project issues (nested)
# ---------------------------------------------------------------------------

@router.get("/{project_id}/issues/", response_model=list[IssueRead])
async def get_project_issues(
    project_id: int,
    filter_status: str | None = Query(default=None, alias="status"),
    filter_priority: str | None = Query(default=None, alias="priority"),
    search: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_or_404(project_id=project_id, db=db)

    if not await _can_view_project(project, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    query = (
        select(Issue)
        .where(Issue.project_id == project_id)
        .options(
            selectinload(Issue.labels),
            selectinload(Issue.assignees),
            selectinload(Issue.creator),
        )
        .order_by(Issue.id)
    )

    if filter_status:
        query = query.where(Issue.status == filter_status)
    if filter_priority:
        query = query.where(Issue.priority == filter_priority)
    if search:
        query = query.where(Issue.title.ilike(f"%{search}%"))

    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Issue assignee candidates for a project
# ---------------------------------------------------------------------------

@router.get("/{project_id}/issue-assignee-candidates", response_model=list[UserRead])
async def list_issue_assignee_candidates(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns all users who can be assigned to issues in this project:
    project members (any role), the project leader, and project leaders of other projects."""
    project = await get_project_or_404(project_id=project_id, db=db)

    if not await _can_view_project(project, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    member_ids_result = await db.execute(
        select(ProjectMember.user_id).where(ProjectMember.project_id == project_id)
    )
    in_project_ids = {row[0] for row in member_ids_result} | {project.leader_id}

    # Other active project_leader role users not already in this project
    other_leaders_result = await db.execute(
        select(User.id).where(
            User.role == UserRole.PROJECT_LEADER,
            User.is_active == True,
            User.id.notin_(in_project_ids),
        )
    )
    all_ids = in_project_ids | {row[0] for row in other_leaders_result}

    result = await db.execute(
        select(User)
        .where(User.id.in_(all_ids), User.is_active == True)
        .order_by(User.id)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Project members (nested under /projects/{project_id}/members/)
# ---------------------------------------------------------------------------

@router.get("/{project_id}/members/candidates", response_model=list[UserRead])
async def list_member_candidates(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns active users who are not yet members of the project (and not the leader).
    Only the project leader or an admin can call this endpoint."""
    project = await get_project_or_404(project_id=project_id, db=db)

    is_admin = current_user.role == UserRole.ADMIN
    is_leader = project.leader_id == current_user.id
    if not is_admin and not is_leader:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    existing_ids_result = await db.execute(
        select(ProjectMember.user_id).where(ProjectMember.project_id == project_id)
    )
    exclude_ids = {row[0] for row in existing_ids_result} | {project.leader_id}

    stmt = select(User).where(User.is_active == True)
    if exclude_ids:
        stmt = stmt.where(User.id.notin_(exclude_ids))
    result = await db.execute(stmt.order_by(User.id))
    return result.scalars().all()


@router.get("/{project_id}/members/", response_model=list[ProjectMemberWithUserRead])
async def list_project_members(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_or_404(project_id=project_id, db=db)

    if not await _can_view_project(project, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .options(selectinload(ProjectMember.user))
        .order_by(ProjectMember.id)
    )
    return result.scalars().all()


@router.post(
    "/{project_id}/members/",
    response_model=ProjectMemberWithUserRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_member(
    project_id: int,
    payload: ProjectMemberAddRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_or_404(project_id=project_id, db=db)

    ensure_can_manage_project_members(project=project, current_user=current_user)

    member_user = await get_user_or_404(user_id=payload.user_id, db=db)

    await validate_project_member_candidate(project=project, member_user=member_user, db=db)

    member = ProjectMember(project_id=project_id, user_id=payload.user_id)
    db.add(member)

    await db.commit()
    await db.refresh(member)

    result = await db.execute(
        select(ProjectMember)
        .where(ProjectMember.id == member.id)
        .options(selectinload(ProjectMember.user))
    )
    member = result.scalar_one()

    await cache_delete_pattern("projects:list:*")
    await cache_delete_pattern("issues:list:*")

    return member


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_member(
    project_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_or_404(project_id=project_id, db=db)

    ensure_can_manage_project_members(project=project, current_user=current_user)

    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in this project")

    await db.delete(member)
    await db.commit()

    await cache_delete_pattern("projects:list:*")
    await cache_delete_pattern("issues:list:*")
