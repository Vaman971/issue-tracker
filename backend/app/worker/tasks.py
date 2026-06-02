"""Celery background tasks.

All tasks that send emails call the async email service via asyncio.run()
because Celery workers are synchronous by default.
"""

import asyncio
import logging

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Email tasks
# ---------------------------------------------------------------------------

@celery_app.task(name="app.worker.tasks.send_verification_email", bind=True, max_retries=3)
def send_verification_email(self, *, to: str, token: str, full_name: str | None = None):
    """Send an email-verification link to the newly registered user."""
    from app.services.email import send_email_verification

    try:
        asyncio.run(send_email_verification(to=to, token=token, full_name=full_name))
    except Exception as exc:
        logger.exception("send_verification_email failed for %s", to)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.worker.tasks.send_password_reset_email", bind=True, max_retries=3)
def send_password_reset_email(self, *, to: str, token: str, full_name: str | None = None):
    """Send a password-reset link."""
    from app.services.email import send_password_reset

    try:
        asyncio.run(send_password_reset(to=to, token=token, full_name=full_name))
    except Exception as exc:
        logger.exception("send_password_reset_email failed for %s", to)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.worker.tasks.notify_issue_assigned", bind=True, max_retries=3)
def notify_issue_assigned(
    self,
    *,
    to: str,
    assignee_name: str | None,
    issue_title: str,
    project_name: str,
    issue_id: int,
):
    """Notify a user that an issue was assigned to them."""
    from app.services.email import send_issue_assigned_notification

    try:
        asyncio.run(
            send_issue_assigned_notification(
                to=to,
                assignee_name=assignee_name,
                issue_title=issue_title,
                project_name=project_name,
                issue_id=issue_id,
            )
        )
    except Exception as exc:
        logger.exception("notify_issue_assigned failed for %s", to)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.worker.tasks.notify_comment_added", bind=True, max_retries=3)
def notify_comment_added(
    self,
    *,
    to: str,
    recipient_name: str | None,
    commenter_name: str | None,
    issue_title: str,
    issue_id: int,
    comment_preview: str,
):
    """Notify issue participants when a comment is added."""
    from app.services.email import send_issue_comment_notification

    try:
        asyncio.run(
            send_issue_comment_notification(
                to=to,
                recipient_name=recipient_name,
                commenter_name=commenter_name,
                issue_title=issue_title,
                issue_id=issue_id,
                comment_preview=comment_preview,
            )
        )
    except Exception as exc:
        logger.exception("notify_comment_added failed for %s", to)
        raise self.retry(exc=exc, countdown=60)


# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------

@celery_app.task(name="app.worker.tasks.process_attachment")
def process_attachment(*, attachment_id: int, file_key: str, mime_type: str):
    """Post-upload processing: generate thumbnails for images, log for others."""
    if mime_type.startswith("image/"):
        logger.info(
            "process_attachment: generating thumbnail | attachment_id=%d | key=%s",
            attachment_id,
            file_key,
        )
        # Thumbnail generation would happen here using Pillow.
        # Skipped in the stub; production code would:
        #   1. Download file from storage
        #   2. Resize with PIL.Image
        #   3. Save thumbnail back to storage with a "_thumb" suffix key
    else:
        logger.info(
            "process_attachment: non-image, nothing to process | attachment_id=%d",
            attachment_id,
        )


# ---------------------------------------------------------------------------
# Periodic maintenance
# ---------------------------------------------------------------------------

@celery_app.task(name="app.worker.tasks.cleanup_expired_tokens")
def cleanup_expired_tokens():
    """Delete password-reset and email-verification tokens that have expired."""
    import asyncio
    from datetime import datetime, timezone

    from sqlalchemy import delete

    from app.db.session import AsyncSessionLocal
    from app.models.email_verification import EmailVerificationToken
    from app.models.password_reset import PasswordResetToken

    async def _run():
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(PasswordResetToken).where(PasswordResetToken.expires_at <= now)
            )
            await session.execute(
                delete(EmailVerificationToken).where(EmailVerificationToken.expires_at <= now)
            )
            await session.commit()
        logger.info("cleanup_expired_tokens: done")

    asyncio.run(_run())


@celery_app.task(name="app.worker.tasks.cleanup_old_notifications")
def cleanup_old_notifications():
    """Delete notifications older than 90 days that have been read."""
    import asyncio
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import delete

    from app.db.session import AsyncSessionLocal
    from app.models.notification import Notification

    async def _run():
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).replace(tzinfo=None)
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(Notification).where(
                    Notification.is_read == True,  # noqa: E712
                    Notification.created_at <= cutoff,
                )
            )
            await session.commit()
        logger.info("cleanup_old_notifications: done")

    asyncio.run(_run())
