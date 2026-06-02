from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete as sa_delete, insert as sa_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.helpers.issue_helper import (
    ensure_can_create_issue_in_project,
    ensure_status_only_update,
    get_issue_or_404,
    get_issue_update_scope,
    get_project_or_404,
    is_project_member,
    list_visible_issues,
    validate_issue_assignees,
)
from app.db.session import get_db
from app.models.issue import Issue
from app.models.issue_assignee import IssueAssignee  # used for raw SQL table reference
from app.models.user import User, UserRole
from app.schemas.issue import IssueCreate, IssueRead, IssueUpdate
from app.services.cache import cache_delete_pattern, cache_get_json, cache_set_json
from app.models.notification import NotificationType
from app.services.notifications import notify

router = APIRouter(
    prefix="/issues",
    tags=["issues"],
)


def _build_issues_cache_key(current_user: User, skip: int, limit: int, q: str | None = None) -> str:
    q_part = f":{q}" if q else ""
    return f"issues:list:{current_user.id}:{current_user.role.value}:{skip}:{limit}{q_part}"


@router.get("/", response_model=list[IssueRead], status_code=status.HTTP_200_OK)
async def list_issues(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cache_key = _build_issues_cache_key(current_user, skip, limit, q)
    cached_issues = await cache_get_json(cache_key)

    if cached_issues is not None:
        return cached_issues

    issues = await list_visible_issues(
        current_user=current_user,
        db=db,
        skip=skip,
        limit=limit,
        q=q,
    )
    serialized_issues = [
        IssueRead.model_validate(issue).model_dump(mode="json")
        for issue in issues
    ]

    await cache_set_json(cache_key, serialized_issues)

    return serialized_issues


@router.post("/", response_model=IssueRead, status_code=status.HTTP_201_CREATED)
async def create_issue(
    payload: IssueCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_or_404(
        project_id=payload.project_id,
        db=db,
    )

    await ensure_can_create_issue_in_project(
        current_user=current_user,
        project=project,
        db=db,
    )

    await validate_issue_assignees(
        assignee_ids=payload.assignee_ids,
        project=project,
        db=db,
    )

    issue = Issue(
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        project_id=payload.project_id,
        creator_id=current_user.id,
    )

    db.add(issue)
    await db.flush()  # get issue.id without full commit

    if payload.assignee_ids:
        await db.execute(
            sa_insert(IssueAssignee),
            [{"issue_id": issue.id, "user_id": uid} for uid in payload.assignee_ids],
        )

    actor_name = current_user.full_name or current_user.email
    for uid in (payload.assignee_ids or []):
        if uid != current_user.id:
            await notify(
                db=db,
                user_id=uid,
                type=NotificationType.ISSUE_ASSIGNED,
                title=f"Assigned to: {issue.title}",
                message=f"{actor_name} assigned you to this issue.",
                meta={"issue_id": issue.id, "project_id": issue.project_id},
            )
    if project.leader_id and project.leader_id != current_user.id:
        await notify(
            db=db,
            user_id=project.leader_id,
            type=NotificationType.ISSUE_CREATED,
            title=f"New issue: {issue.title}",
            message=f"{actor_name} created a new issue in {project.name}.",
            meta={"issue_id": issue.id, "project_id": issue.project_id},
        )

    await db.commit()
    issue_id = issue.id
    db.expunge_all()

    await cache_delete_pattern("issues:list:*")

    return await get_issue_or_404(issue_id=issue_id, db=db)


@router.patch(
    "/{issue_id}",
    response_model=IssueRead,
    status_code=status.HTTP_200_OK,
)
async def update_issue(
    issue_id: int,
    payload: IssueUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = await get_issue_or_404(
        issue_id=issue_id,
        db=db,
    )

    project = await get_project_or_404(
        project_id=issue.project_id,
        db=db,
    )

    update_scope = await get_issue_update_scope(
        current_user=current_user,
        project=project,
        db=db,
    )

    update_data = payload.model_dump(exclude_unset=True)

    # Pull out assignee_ids before the status-only check — it's not a column field
    assignee_ids = update_data.pop("assignee_ids", None)

    # Capture state before any mutations for notification diffing
    old_status = issue.status
    old_assignee_ids = {a.id for a in issue.assignees}

    if update_scope == "status_only":
        ensure_status_only_update(update_data)

    if assignee_ids is not None:
        if update_scope == "status_only":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project members can only update issue status"
            )
        await validate_issue_assignees(
            assignee_ids=assignee_ids,
            project=project,
            db=db,
        )

    for field, value in update_data.items():
        setattr(issue, field, value)

    if assignee_ids is not None:
        await db.execute(sa_delete(IssueAssignee).where(IssueAssignee.issue_id == issue_id))
        if assignee_ids:
            await db.execute(
                sa_insert(IssueAssignee),
                [{"issue_id": issue_id, "user_id": uid} for uid in assignee_ids],
            )

    actor_name = current_user.full_name or current_user.email

    if issue.status != old_status:
        status_label = issue.status.value.replace("_", " ").title()
        recipients: set[int] = set()
        if issue.creator_id != current_user.id:
            recipients.add(issue.creator_id)
        for a in issue.assignees:
            if a.id != current_user.id:
                recipients.add(a.id)
        for uid in recipients:
            await notify(
                db=db,
                user_id=uid,
                type=NotificationType.ISSUE_STATUS_CHANGED,
                title=f"Status updated: {issue.title}",
                message=f"{actor_name} changed the status to {status_label}.",
                meta={"issue_id": issue.id, "project_id": issue.project_id},
            )

    if assignee_ids is not None:
        for uid in set(assignee_ids) - old_assignee_ids:
            if uid != current_user.id:
                await notify(
                    db=db,
                    user_id=uid,
                    type=NotificationType.ISSUE_ASSIGNED,
                    title=f"Assigned to: {issue.title}",
                    message=f"{actor_name} assigned you to this issue.",
                    meta={"issue_id": issue.id, "project_id": issue.project_id},
                )

    await db.commit()
    db.expunge_all()
    await cache_delete_pattern("issues:list:*")

    return await get_issue_or_404(issue_id=issue_id, db=db)


@router.get(
    "/{issue_id}",
    response_model=IssueRead,
    status_code=status.HTTP_200_OK,
)
async def get_issue(
    issue_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = await get_issue_or_404(issue_id=issue_id, db=db)

    if current_user.role != UserRole.ADMIN:
        project = await get_project_or_404(project_id=issue.project_id, db=db)
        if project.leader_id != current_user.id:
            if not await is_project_member(project_id=project.id, user_id=current_user.id, db=db):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return issue


@router.delete(
    "/{issue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_issue(
    issue_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = await get_issue_or_404(issue_id=issue_id, db=db)
    project = await get_project_or_404(project_id=issue.project_id, db=db)

    can_delete = (
        current_user.role == UserRole.ADMIN
        or project.leader_id == current_user.id
        or issue.creator_id == current_user.id
    )
    if not can_delete:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot delete this issue")

    await db.delete(issue)
    await db.commit()

    await cache_delete_pattern("issues:list:*")
