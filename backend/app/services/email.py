"""Async email service using aiosmtplib.

In development (EMAILS_ENABLED=False) every email is logged instead of sent,
so no SMTP server is required.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


async def _send(*, to: str, subject: str, html_body: str) -> None:
    """Low-level send; swaps between real SMTP and log-only depending on config."""
    if not settings.EMAILS_ENABLED:
        # In dev mode log the full body so developers can copy tokens/URLs from the terminal.
        logger.info(
            "[DEV EMAIL — not sent] to=%s | subject=%s | body=%s",
            to,
            subject,
            html_body,
        )
        return

    try:
        import aiosmtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME or None,
            password=settings.SMTP_PASSWORD or None,
            use_tls=settings.SMTP_USE_TLS,
        )
        logger.info("Email sent | to=%s | subject=%s", to, subject)
    except Exception:
        logger.exception("Failed to send email | to=%s | subject=%s", to, subject)
        raise


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

async def send_email_verification(*, to: str, token: str, full_name: str | None = None) -> None:
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    name = full_name or to
    html = f"""
    <h2>Verify your email address</h2>
    <p>Hi {name},</p>
    <p>Click the link below to verify your email address. This link expires in
       {settings.EMAIL_VERIFY_TOKEN_EXPIRES_HOURS} hour(s).</p>
    <p><a href="{verify_url}">{verify_url}</a></p>
    <p>If you did not create an account, you can ignore this email.</p>
    """
    await _send(to=to, subject="Verify your email address", html_body=html)


async def send_password_reset(*, to: str, token: str, full_name: str | None = None) -> None:
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    name = full_name or to
    html = f"""
    <h2>Reset your password</h2>
    <p>Hi {name},</p>
    <p>Click the link below to reset your password. This link expires in
       {settings.PASSWORD_RESET_TOKEN_EXPIRES_HOURS} hour(s).</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>If you did not request a password reset, you can ignore this email.</p>
    """
    await _send(to=to, subject="Reset your password", html_body=html)


async def send_issue_assigned_notification(
    *,
    to: str,
    assignee_name: str | None,
    issue_title: str,
    project_name: str,
    issue_id: int,
) -> None:
    issue_url = f"{settings.FRONTEND_URL}/issues/{issue_id}"
    name = assignee_name or to
    html = f"""
    <h2>Issue assigned to you</h2>
    <p>Hi {name},</p>
    <p>You have been assigned to issue <strong>{issue_title}</strong> in project
       <strong>{project_name}</strong>.</p>
    <p><a href="{issue_url}">View issue</a></p>
    """
    await _send(to=to, subject=f"Issue assigned: {issue_title}", html_body=html)


async def send_issue_comment_notification(
    *,
    to: str,
    recipient_name: str | None,
    commenter_name: str | None,
    issue_title: str,
    issue_id: int,
    comment_preview: str,
) -> None:
    issue_url = f"{settings.FRONTEND_URL}/issues/{issue_id}"
    name = recipient_name or to
    commenter = commenter_name or "Someone"
    preview = comment_preview[:200] + "..." if len(comment_preview) > 200 else comment_preview
    html = f"""
    <h2>New comment on issue</h2>
    <p>Hi {name},</p>
    <p><strong>{commenter}</strong> commented on issue
       <strong>{issue_title}</strong>:</p>
    <blockquote>{preview}</blockquote>
    <p><a href="{issue_url}">View issue</a></p>
    """
    await _send(to=to, subject=f"New comment on: {issue_title}", html_body=html)
