import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.routes.activity import router as activity_router
from app.api.routes.admin import router as admin_router
from app.api.routes.attachments import router as attachments_router
from app.api.routes.auth import router as auth_router
from app.api.routes.comments import router as comments_router
from app.api.routes.issues import router as issue_router
from app.api.routes.labels import router as labels_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.project_member import router as project_member_router
from app.api.routes.projects import router as project_router
from app.api.routes.search import router as search_router
from app.api.routes.stats import router as stats_router
from app.api.routes.users import router as user_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import close_redis_client, ping_redis
from app.core.request_context import request_id_context
from app.db.session import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    logger.info("Starting application")

    # Ensure local uploads directory exists
    if settings.STORAGE_BACKEND == "local":
        Path(settings.LOCAL_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    yield

    await close_redis_client()
    logger.info("Shutting down application")


app = FastAPI(
    title=settings.APP_NAME,
    description="Feature-rich issue tracker API — auth, RBAC, comments, attachments, labels, notifications, Celery tasks, file storage",
    version="2.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    token = request_id_context.set(request_id)

    logger.info(
        "Request started | method=%s | path=%s",
        request.method,
        request.url.path,
    )

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Request failed | method=%s | path=%s",
            request.method,
            request.url.path,
        )
        request_id_context.reset(token)
        raise

    response.headers["X-Request-ID"] = request_id

    logger.info(
        "Request completed | method=%s | path=%s | status_code=%s",
        request.method,
        request.url.path,
        response.status_code,
    )

    request_id_context.reset(token)
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(project_router)
app.include_router(project_member_router)
app.include_router(issue_router)
app.include_router(user_router)
app.include_router(comments_router)
app.include_router(attachments_router)
app.include_router(labels_router)
app.include_router(notifications_router)
app.include_router(activity_router)
app.include_router(search_router)
app.include_router(stats_router)

# Serve locally stored uploads at /files/<key>
if settings.STORAGE_BACKEND == "local":
    upload_dir = Path(settings.LOCAL_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=str(upload_dir)), name="uploads")


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

@app.get("/health/live", tags=["health"])
async def liveness_check():
    return {"status": "alive", "environment": settings.APP_ENV}


@app.get("/health/ready", tags=["health"])
async def readiness_check():
    database_ok = True
    database_error = None

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("Readiness check failed: database unavailable")
        database_ok = False
        database_error = str(exc)

    redis_ok = await ping_redis()

    if not database_ok or not redis_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unready",
                "environment": settings.APP_ENV,
                "database": "up" if database_ok else "down",
                "redis": "up" if redis_ok else "down",
                "database_error": database_error,
            },
        )

    return {
        "status": "ready",
        "environment": settings.APP_ENV,
        "database": "up",
        "redis": "up",
    }
