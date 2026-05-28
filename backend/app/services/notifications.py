import logging

logger = logging.getLogger(__name__)

# later this could become emial sending, redis queue, celery worker, slack notification etc
def send_issue_created_notification(
        issue_id: int,
        issue_title: str,
        creator_email: str
) -> None:
    logger.info(
        "Issue created notification queued | issue_id=%s | ttile=%s | creator=%s",
        issue_id,
        issue_title,
        creator_email
    )