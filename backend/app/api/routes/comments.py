"""Issue comments — CRUD with threaded reply support."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.activity import ActivityAction, IssueActivity
from app.models.comment import IssueComment
from app.models.issue import Issue
from app.models.notification import Notification, NotificationType
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentRead, CommentUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/issues/{issue_id}/comments", tags=["comments"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _get_issue_or_404(issue_id: int, db: AsyncSession) -> Issue:
    result = await db.execute(
        select(Issue)
        .where(Issue.id == issue_id)
        .options(selectinload(Issue.assignees))
    )
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return issue


async def _can_access_issue(issue: Issue, user: User, db: AsyncSession) -> bool:
    """Return True if user has access to the project containing this issue."""
    from app.models.user import UserRole
    if user.role == UserRole.ADMIN:
        return True
    from app.models.project import Project
    project_result = await db.execute(select(Project).where(Project.id == issue.project_id))
    project = project_result.scalar_one_or_none()
    if project and project.leader_id == user.id:
        return True
    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == issue.project_id,
            ProjectMember.user_id == user.id,
        )
    )
    return member_result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[CommentRead])
async def list_comments(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = await _get_issue_or_404(issue_id, db)
    if not await _can_access_issue(issue, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(IssueComment)
        .where(IssueComment.issue_id == issue_id)
        .options(selectinload(IssueComment.author))
        .order_by(IssueComment.created_at)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post("/", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def create_comment(
    issue_id: int,
    payload: CommentCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = await _get_issue_or_404(issue_id, db)
    if not await _can_access_issue(issue, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Validate parent comment exists in same issue
    if payload.parent_id is not None:
        parent_result = await db.execute(
            select(IssueComment).where(
                IssueComment.id == payload.parent_id,
                IssueComment.issue_id == issue_id,
            )
        )
        if parent_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent comment not found")

    comment = IssueComment(
        issue_id=issue_id,
        author_id=current_user.id,
        content=payload.content,
        parent_id=payload.parent_id,
    )
    db.add(comment)

    # Activity log
    db.add(
        IssueActivity(
            issue_id=issue_id,
            actor_id=current_user.id,
            action=ActivityAction.COMMENT_ADDED,
            new_value=payload.content[:200],
        )
    )

    # In-app notifications for issue creator and all assignees
    recipients: set[int] = set()
    if issue.creator_id != current_user.id:
        recipients.add(issue.creator_id)
    for assignee in issue.assignees:
        if assignee.id != current_user.id:
            recipients.add(assignee.id)

    for uid in recipients:
        db.add(
            Notification(
                user_id=uid,
                type=NotificationType.ISSUE_COMMENTED,
                title=f"New comment on: {issue.title}",
                message=f"{current_user.full_name or current_user.email} commented: {payload.content[:100]}",
                meta=f'{{"issue_id": {issue.id}}}',
            )
        )

    await db.commit()
    await db.refresh(comment)

    # Load author for response
    result = await db.execute(
        select(IssueComment)
        .where(IssueComment.id == comment.id)
        .options(selectinload(IssueComment.author))
    )
    comment = result.scalar_one()

    # Queue email notifications via Celery (fire-and-forget)
    background_tasks.add_task(
        _dispatch_comment_emails, issue=issue, comment=comment, actor=current_user
    )

    return comment


def _dispatch_comment_emails(issue: Issue, comment: IssueComment, actor: User) -> None:
    """Send email notifications to issue participants via Celery (best-effort)."""
    try:
        from app.worker.tasks import notify_comment_added
        recipients: set[int] = set()
        if issue.creator_id != actor.id:
            recipients.add(issue.creator_id)
        for assignee in (issue.assignees or []):
            if assignee.id != actor.id:
                recipients.add(assignee.id)
        for uid in recipients:
            notify_comment_added.delay(  # type: ignore[attr-defined]
                to=str(uid),  # in production resolve email from user_id
                recipient_name=None,
                commenter_name=actor.full_name or actor.email,
                issue_title=issue.title,
                issue_id=issue.id,
                comment_preview=comment.content,
            )
    except Exception:
        logger.warning("Celery unavailable; skipping comment email notifications")


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@router.patch("/{comment_id}", response_model=CommentRead)
async def update_comment(
    issue_id: int,
    comment_id: int,
    payload: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(IssueComment)
        .where(IssueComment.id == comment_id, IssueComment.issue_id == issue_id)
        .options(selectinload(IssueComment.author))
    )
    comment = result.scalar_one_or_none()

    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    if comment.author_id != current_user.id:
        from app.models.user import UserRole
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only edit your own comments")

    comment.content = payload.content
    comment.updated_at = _utc_now()
    await db.commit()
    await db.refresh(comment)

    result = await db.execute(
        select(IssueComment)
        .where(IssueComment.id == comment.id)
        .options(selectinload(IssueComment.author))
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    issue_id: int,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(IssueComment).where(
            IssueComment.id == comment_id,
            IssueComment.issue_id == issue_id,
        )
    )
    comment = result.scalar_one_or_none()

    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    from app.models.user import UserRole
    if comment.author_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only delete your own comments")

    await db.delete(comment)
    await db.commit()
