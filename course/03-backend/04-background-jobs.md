# Module 03-04 — Celery, Redis Broker & Background Jobs

---

## Learning Objectives

After this module you will:
- Understand why background job processing exists
- Know how Celery and Redis work together as a task queue
- Understand Celery Beat for scheduled tasks
- See all the background tasks in this project

---

## Why Background Jobs?

Some operations are too slow or unreliable to run inline with an HTTP request:

```
WITHOUT background jobs:
  User creates issue
  → FastAPI sends email (SMTP connection, waits for server: 2-5 seconds)
  → User waits...
  → Response returned after 5 seconds

User experience: TERRIBLE. They wonder if the button worked.

WITH background jobs:
  User creates issue
  → FastAPI queues email task (Redis write: <1ms)
  → Response returned immediately (HTTP 201)
  
  (In background, 2-5 seconds later)
  → Celery Worker picks up task
  → Connects to SMTP server
  → Sends email

User experience: Button responds instantly. Email arrives shortly after.
```

Background jobs also handle:
- **Unreliable operations**: If email server is down, the task can retry automatically
- **Heavy computation**: Image processing, PDF generation, data exports
- **Scheduled maintenance**: Nightly cleanups, weekly reports, cache warming
- **Fan-out operations**: Sending notifications to 100 users (do it in background, not in request)

---

## How Celery Works — The Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                         SYSTEM OVERVIEW                           │
│                                                                   │
│   FastAPI (Producer)                                              │
│   ┌─────────────────────────────┐                                 │
│   │ create_issue()              │                                 │
│   │   ...                       │                                 │
│   │   notify_issue_assigned.delay(issue_id)  ─────────────┐      │
│   │   return response           │                         │      │
│   └─────────────────────────────┘                         │      │
│                                                            │      │
│                         ┌─────────────────────────────────▼──┐   │
│                         │           REDIS BROKER              │   │
│                         │  Queue: "notifications"             │   │
│                         │  [task1, task2, task3, ...]        │   │
│                         └─────────────────────────────────┬──┘   │
│                                                            │      │
│   Celery Worker (Consumer)                                 │      │
│   ┌─────────────────────────────┐                         │      │
│   │ while True:                 │                         │      │
│   │   task = queue.pop() ◄──────┼─────────────────────────┘      │
│   │   execute(task)             │                                 │
│   └─────────────────────────────┘                                 │
│                                                                   │
│   Celery Beat (Scheduler)                                         │
│   ┌─────────────────────────────┐                                 │
│   │ Every 24h:                  │                                 │
│   │   cleanup_tokens.delay() ──► Redis queue                     │
│   └─────────────────────────────┘                                 │
└───────────────────────────────────────────────────────────────────┘
```

---

## Celery Configuration

```python
# backend/app/worker/celery_app.py

from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "issue_tracker",
    broker=settings.CELERY_BROKER_URL,     # redis://redis:6379/1
    backend=settings.CELERY_RESULT_BACKEND, # redis://redis:6379/2
    include=["app.worker.tasks"],           # Where to find task functions
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task routing — different queues for different priorities
    task_routes={
        "app.worker.tasks.send_verification_email": {"queue": "email"},
        "app.worker.tasks.send_password_reset_email": {"queue": "email"},
        "app.worker.tasks.notify_issue_assigned": {"queue": "notifications"},
        "app.worker.tasks.notify_comment_added": {"queue": "notifications"},
        # Default queue for everything else
    },
    
    # Retry settings
    task_acks_late=True,         # Acknowledge task AFTER it runs (not before)
    worker_prefetch_multiplier=1, # One task at a time per worker (fair dispatch)
    
    # Scheduled tasks (Celery Beat)
    beat_schedule={
        "cleanup-expired-tokens": {
            "task": "app.worker.tasks.cleanup_expired_tokens",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM UTC
        },
        "cleanup-old-notifications": {
            "task": "app.worker.tasks.cleanup_old_notifications",
            "schedule": crontab(day_of_week=0, hour=3, minute=0),  # Weekly Sunday 3 AM
        },
    },
)
```

### Redis Database Slots

```
redis:6379/0 → Application cache (project lists, user data)
redis:6379/1 → Celery broker (task queue messages)
redis:6379/2 → Celery result backend (task results/status)
```

Separate databases prevent cache pollution of task queues.

---

## Celery Tasks

```python
# backend/app/worker/tasks.py

from app.worker.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.services.email import send_email
from app.models.user import User
from app.models.issue import Issue

@celery_app.task(
    bind=True,              # Pass task instance as first arg (for retries)
    max_retries=3,          # Retry up to 3 times on failure
    default_retry_delay=60, # Wait 60 seconds between retries
)
async def send_verification_email(self, user_id: int):
    """Send email verification link to new user."""
    try:
        async with AsyncSessionLocal() as db:
            user = await db.get(User, user_id)
            if not user:
                return  # User was deleted, skip
            
            token = await create_email_verification_token(db, user)
            
            verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
            
            await send_email(
                to=user.email,
                subject="Verify your email address",
                body=f"Click to verify: {verify_url}",
            )
    except Exception as exc:
        # Retry on failure
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
async def notify_issue_assigned(self, issue_id: int, assignee_ids: list[int]):
    """Create notifications for all newly assigned users."""
    try:
        async with AsyncSessionLocal() as db:
            issue = await db.get(Issue, issue_id)
            if not issue:
                return
            
            for assignee_id in assignee_ids:
                user = await db.get(User, assignee_id)
                if not user:
                    continue
                
                # Create in-app notification
                notification = Notification(
                    user_id=assignee_id,
                    notification_type=NotificationType.ISSUE_ASSIGNED,
                    title=f"You were assigned to: {issue.title}",
                    issue_id=issue_id,
                )
                db.add(notification)
                
                # Send email if enabled
                if settings.EMAILS_ENABLED:
                    await send_email(
                        to=user.email,
                        subject=f"Assigned to issue: {issue.title}",
                        body=f"You have been assigned to issue #{issue.id}",
                    )
            
            await db.commit()
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3)
async def notify_comment_added(self, comment_id: int):
    """Notify issue creator and assignees about a new comment."""
    try:
        async with AsyncSessionLocal() as db:
            comment = await db.get(IssueComment, comment_id)
            if not comment:
                return
            
            issue = await db.get(Issue, comment.issue_id)
            
            # Collect users to notify (creator + assignees, but not the commenter)
            users_to_notify = set()
            users_to_notify.add(issue.creator_id)
            for assignee in issue.assignees:
                users_to_notify.add(assignee.id)
            users_to_notify.discard(comment.author_id)  # Don't notify yourself
            
            for user_id in users_to_notify:
                notification = Notification(
                    user_id=user_id,
                    notification_type=NotificationType.COMMENT_ADDED,
                    title=f"New comment on: {issue.title}",
                    issue_id=issue.issue_id,
                )
                db.add(notification)
            
            await db.commit()
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task
async def cleanup_expired_tokens():
    """Nightly cleanup of expired tokens. No retry needed."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(RefreshToken).where(
                RefreshToken.expires_at < datetime.now(timezone.utc)
            )
        )
        await db.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.expires_at < datetime.now(timezone.utc)
            )
        )
        await db.commit()


@celery_app.task
async def cleanup_old_notifications():
    """Weekly cleanup of notifications older than 90 days."""
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        await db.execute(
            delete(Notification).where(
                Notification.created_at < cutoff,
                Notification.read == True  # Only delete read notifications
            )
        )
        await db.commit()
```

---

## Calling Tasks from FastAPI

```python
# In your FastAPI route handler:

@router.post("/issues", status_code=201)
async def create_issue(body: IssueCreate, db=Depends(get_db), current_user=Depends(...)):
    # ... create the issue ...
    
    # Queue task asynchronously (non-blocking, returns immediately)
    # .delay() is shorthand for .apply_async()
    notify_issue_assigned.delay(
        issue_id=new_issue.id,
        assignee_ids=[a.id for a in new_issue.assignees]
    )
    
    # This returns IMMEDIATELY — we don't wait for the task to run
    return IssueResponse.model_validate(new_issue)
```

The task arguments are serialized to JSON and pushed to Redis:
```json
{
  "task": "app.worker.tasks.notify_issue_assigned",
  "id": "task-uuid-abc123",
  "args": [],
  "kwargs": {"issue_id": 42, "assignee_ids": [1, 3, 7]},
  "expires": null
}
```

---

## Celery Beat — Scheduled Tasks

Celery Beat is a **singleton scheduler** — only one instance ever runs. It:
1. Maintains a schedule of when tasks should run
2. Pushes tasks to the Redis queue at the right times
3. Does NOT execute tasks itself (that's the Worker's job)

```
Celery Beat (1 pod - Recreate strategy):
┌────────────────────────────────────────┐
│ Internal clock running...              │
│                                        │
│ 2:00 AM UTC reached:                   │
│   push cleanup_expired_tokens → Redis  │
│                                        │
│ Sunday 3:00 AM UTC reached:            │
│   push cleanup_old_notifications→ Redis│
└────────────────────────────────────────┘
                  │
                  ▼ message in Redis queue
┌────────────────────────────────────────┐
│ Celery Worker picks up task            │
│ Executes cleanup_expired_tokens()      │
└────────────────────────────────────────┘
```

**Why Recreate strategy?** The Kubernetes deployment for Celery Beat uses `strategy: Recreate` instead of `RollingUpdate`:

```yaml
# infra/kubernetes/celery/beat-deployment.yaml
strategy:
  type: Recreate  # Kill old pod BEFORE starting new one
```

If you ran two Beat instances simultaneously, every scheduled task would fire twice (duplicate emails, double cleanup). `Recreate` ensures only one Beat pod runs at a time.

---

## Email Service

```python
# backend/app/services/email.py

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

async def send_email(to: str, subject: str, body: str, html_body: str = None):
    """Send an email via SMTP."""
    
    # In development: just log (no email sent)
    if not settings.EMAILS_ENABLED:
        logger.info(f"[DEV] Email to {to}: {subject}")
        return
    
    message = MIMEMultipart("alternative")
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = to
    message["Subject"] = subject
    
    message.attach(MIMEText(body, "plain"))
    if html_body:
        message.attach(MIMEText(html_body, "html"))
    
    # aiosmtplib is the async version of smtplib
    async with aiosmtplib.SMTP(
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        use_tls=True,
    ) as smtp:
        await smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        await smtp.send_message(message)
```

Email providers you can use:
- **Development**: Any SMTP server (Mailpit running in Docker works great for local testing)
- **Production**: AWS SES, SendGrid, Postmark, Mailgun

---

## Flower — Celery Monitoring Dashboard

Flower is a web UI for monitoring Celery:

```
http://localhost:5555 (development stack)

Shows:
  - Active workers and their status
  - Task queue lengths
  - Recent task history (success/failure/retry)
  - Task execution time
  - Worker resource usage (CPU, memory)
```

```yaml
# docker-compose.dev.yml
flower:
  image: mher/flower
  command: celery --broker=redis://redis:6379/1 flower --port=5555
  ports:
    - "5555:5555"
```

---

## Task Retry Strategy

```
Task fails (e.g. SMTP server down):
        │
        ▼
self.retry(exc=exc, countdown=60)
        │
        ▼ After 60 seconds...
Task runs again (attempt 2)
        │
        ▼ Fails again
Task scheduled for retry (attempt 3)
        │
        ▼ Fails again
Task scheduled for retry (attempt 4)
        │
        ▼ max_retries=3 reached
Task marked as FAILURE
(logged, available in Flower for inspection)
```

For critical tasks like email, you might want exponential backoff:
```python
@celery_app.task(bind=True, max_retries=5)
def send_email_task(self, ...):
    try:
        ...
    except Exception as exc:
        # Retry after 60s, then 120s, then 240s, then 480s, then 960s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

---

## Celery in Kubernetes

```yaml
# Two separate Kubernetes deployments:

# 1. Celery Worker (processes tasks)
# infra/kubernetes/celery/worker-deployment.yaml
containers:
  - name: celery-worker
    command: ["celery", "-A", "app.worker.celery_app", "worker",
              "--loglevel=info", "--concurrency=2",
              "-Q", "default,email,notifications"]
# HPA: 2-15 replicas based on CPU usage
# Scale up when backlog grows (CPU indicates workers are busy)

# 2. Celery Beat (scheduler - always exactly 1)
# infra/kubernetes/celery/beat-deployment.yaml
containers:
  - name: celery-beat
    command: ["celery", "-A", "app.worker.celery_app", "beat",
              "--loglevel=info"]
replicas: 1
strategy:
  type: Recreate  # NEVER run 2 Beat instances
```

---

## Further Reading & Videos

- **YouTube**: Search "Celery Python Tutorial" — Patrick Loeber has a clear tutorial
- **YouTube**: Search "Celery Beat scheduled tasks" — covers periodic tasks in detail
- **Official Docs**: [Celery documentation](https://docs.celeryq.dev)
- **Official Docs**: [Redis commands documentation](https://redis.io/commands) — understand what INCR, EXPIRE, etc. do

---

*Next: [Module 04-01 — PostgreSQL Internals & Schema Design](../04-database/01-postgresql-fundamentals.md)*
