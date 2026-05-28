from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.helpers.project_helper import (
    list_visible_projects,
    validate_project_leader,
)

from app.api.deps import get_current_user
from app.api.rbac import require_roles
from app.db.session import get_db
from app.models.project import Project
from app.models.user import UserRole, User
from app.models.project_member import ProjectMember
from app.schemas.project import ProjectCreate, ProjectRead

router = APIRouter(
    prefix="/projects",
    tags=["/projects"]
)

@router.post(
    "/",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED
)
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    await validate_project_leader(
        leader_id=payload.leader_id,
        db=db,
    )

    project = Project(
        name=payload.name,
        description=payload.description,
        leader_id=payload.leader_id,
    )

    db.add(project)

    await db.commit()
    await db.refresh(project)

    return project

@router.get("/", response_model=list[ProjectRead])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await list_visible_projects(
        current_user=current_user,
        db=db,
    )
