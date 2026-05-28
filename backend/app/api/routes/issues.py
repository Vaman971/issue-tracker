from fastapi import APIRouter, BackgroundTasks, Depends, Query, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.issue import Issue, IssueStatus
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole
from app.schemas.issue import IssueRead, IssueCreate, IssueUpdate
from app.services.notifications import send_issue_created_notification

from app.api.helpers.issue_helper import (
    ensure_can_create_issue_in_project,
    ensure_status_only_update,
    get_issue_or_404,
    get_issue_update_scope,
    get_project_or_404,
    list_visible_issues,
    validate_issue_assignee,
)

router = APIRouter(
    prefix="/issues",
    tags=["issues"]
)

@router.get("/", response_model=list[IssueRead], status_code=status.HTTP_200_OK)
async def list_issues(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await list_visible_issues(
        current_user=current_user,
        db=db,
        skip=skip,
        limit=limit,
    )

@router.post("/", response_model=IssueRead, status_code=status.HTTP_201_CREATED)
async def create_issue(
    payload: IssueCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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

    await validate_issue_assignee(
        assignee_id=payload.assignee_id,
        project=project,
        db=db
    )

    issue = Issue(
        title = payload.title,
        description = payload.description,
        priority = payload.priority,
        project_id = payload.project_id,
        assignee_id = payload.assignee_id,
        creator_id = current_user.id
    )

    db.add(issue)

    await db.commit()
    await db.refresh(issue)

    # good for small background tasks, for large production grade applications we use Celery/RQ/Arq with redis
    background_tasks.add_task(
        send_issue_created_notification,
        issue.id,
        issue.title,
        current_user.email
    )

    return issue

@router.patch(
    "/{issue_id}",
    response_model=IssueRead,
    status_code=status.HTTP_200_OK
)
async def update_issue(
    issue_id: int,
    payload: IssueUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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

    if update_scope == "status_only":
        ensure_status_only_update(update_data)

    for field, value in update_data.items():
        setattr(issue, field, value)

    await db.commit()
    await db.refresh(issue)

    return issue
