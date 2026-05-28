from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import logging
from app.core.logging import setup_logging

from app.core.config import settings

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.projects import router as project_router
from app.api.routes.project_member import router as project_member_router
from app.api.routes.issues import router as issue_router
from app.api.routes.users import router as user_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting Application")

    yield

    logger.info("Shutting down Application")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(project_router)
app.include_router(project_member_router)
app.include_router(issue_router)
app.include_router(user_router)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environemt": settings.APP_ENV,
    }
