import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)


async def notify(
    db: AsyncSession,
    user_id: int,
    type: NotificationType,
    title: str,
    message: str,
    meta: dict | None = None,
) -> None:
    """Add a Notification row to the current session. Caller is responsible for commit."""
    db.add(Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        meta=json.dumps(meta) if meta else None,
    ))
