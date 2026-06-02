"""Celery application factory."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "issue_tracker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Periodic tasks (beat schedule)
    beat_schedule={
        "cleanup-expired-tokens-daily": {
            "task": "app.worker.tasks.cleanup_expired_tokens",
            "schedule": 86400,  # every 24 h
        },
        "cleanup-old-notifications-weekly": {
            "task": "app.worker.tasks.cleanup_old_notifications",
            "schedule": 604800,  # every 7 days
        },
    },
)
