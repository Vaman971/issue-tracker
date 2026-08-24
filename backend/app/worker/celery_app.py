"""Celery application factory."""

from celery import Celery
from celery.signals import worker_process_init

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
        "refresh-rag-embeddings": {
            "task": "app.worker.tasks.refresh_embeddings",
            "schedule": 300, # Every 5 mins
        }
    },
)


@worker_process_init.connect
def _reset_db_pool(**_kwargs) -> None:
    """Drop connections inherited from the parent process.

    The async engine is created at import time, so the prefork parent opens
    the pool and every forked child inherits the same sockets. Two children
    using one connection produces:

        InterfaceError: cannot perform operation: another operation is in progress

    close=False matters: the sockets still belong to the parent, so the child
    must forget them rather than close them.
    """

    from app.db.session import engine

    engine.sync_engine.dispose(close=False)
