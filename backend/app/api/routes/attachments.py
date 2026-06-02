"""Issue attachments — upload, list, download URL, delete."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.activity import ActivityAction, IssueActivity
from app.models.attachment import IssueAttachment
from app.models.issue import Issue
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole
from app.schemas.attachment import AttachmentRead, AttachmentWithURL
from app.services.storage import delete_file, get_download_url, upload_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/issues/{issue_id}/attachments", tags=["attachments"])


async def _get_issue_or_404(issue_id: int, db: AsyncSession) -> Issue:
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return issue


async def _can_access(issue: Issue, user: User, db: AsyncSession) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    from app.models.project import Project
    project = (await db.execute(select(Project).where(Project.id == issue.project_id))).scalar_one_or_none()
    if project and project.leader_id == user.id:
        return True
    member = (await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == issue.project_id,
            ProjectMember.user_id == user.id,
        )
    )).scalar_one_or_none()
    return member is not None


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[AttachmentRead])
async def list_attachments(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = await _get_issue_or_404(issue_id, db)
    if not await _can_access(issue, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(IssueAttachment)
        .where(IssueAttachment.issue_id == issue_id)
        .options(selectinload(IssueAttachment.uploader))
        .order_by(IssueAttachment.created_at)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    issue_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = await _get_issue_or_404(issue_id, db)
    if not await _can_access(issue, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    data = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    original_filename = file.filename or "attachment"

    try:
        file_key = await upload_file(data=data, original_filename=original_filename, mime_type=mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    attachment = IssueAttachment(
        issue_id=issue_id,
        uploader_id=current_user.id,
        original_filename=original_filename,
        file_key=file_key,
        file_size_bytes=len(data),
        mime_type=mime_type,
    )
    db.add(attachment)

    db.add(
        IssueActivity(
            issue_id=issue_id,
            actor_id=current_user.id,
            action=ActivityAction.ATTACHMENT_ADDED,
            new_value=original_filename,
        )
    )

    await db.commit()
    await db.refresh(attachment)

    # Dispatch post-processing (thumbnail etc.) via Celery
    try:
        from app.worker.tasks import process_attachment
        process_attachment.delay(  # type: ignore[attr-defined]
            attachment_id=attachment.id,
            file_key=file_key,
            mime_type=mime_type,
        )
    except Exception:
        logger.warning("Celery unavailable; skipping post-upload processing")

    result = await db.execute(
        select(IssueAttachment)
        .where(IssueAttachment.id == attachment.id)
        .options(selectinload(IssueAttachment.uploader))
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Download URL
# ---------------------------------------------------------------------------

@router.get("/{attachment_id}/url", response_model=AttachmentWithURL)
async def get_attachment_url(
    issue_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = await _get_issue_or_404(issue_id, db)
    if not await _can_access(issue, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(IssueAttachment)
        .where(IssueAttachment.id == attachment_id, IssueAttachment.issue_id == issue_id)
        .options(selectinload(IssueAttachment.uploader))
    )
    attachment = result.scalar_one_or_none()
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    base = AttachmentRead.model_validate(attachment)
    return AttachmentWithURL(**base.model_dump(), download_url=get_download_url(attachment.file_key))


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    issue_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = await _get_issue_or_404(issue_id, db)

    result = await db.execute(
        select(IssueAttachment).where(
            IssueAttachment.id == attachment_id,
            IssueAttachment.issue_id == issue_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    # Only uploader, project leader, or admin can delete
    can_delete = (
        current_user.role == UserRole.ADMIN
        or attachment.uploader_id == current_user.id
        or await _can_access(issue, current_user, db)
    )
    if not can_delete:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    await delete_file(attachment.file_key)

    db.add(
        IssueActivity(
            issue_id=issue_id,
            actor_id=current_user.id,
            action=ActivityAction.ATTACHMENT_REMOVED,
            old_value=attachment.original_filename,
        )
    )

    await db.delete(attachment)
    await db.commit()
