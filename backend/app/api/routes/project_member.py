from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.helpers.issue_helper import get_project_or_404
from app.api.helpers.project_helper import (
    ensure_can_manage_project_members,
    get_user_or_404,
    validate_project_member_candidate,
)
from app.db.session import get_db
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.project_member import ProjectMemberCreate, ProjectMemberRead

router = APIRouter(prefix="/project_members", tags=["project-members"])

@router.post(
    "/",
    response_model=ProjectMemberRead,
    status_code=status.HTTP_201_CREATED
)
async def add_project_member(
    payload: ProjectMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await get_project_or_404(
        project_id=payload.project_id,
        db=db,
    )

    ensure_can_manage_project_members(
        project=project,
        current_user=current_user,
    )

    member_user = await get_user_or_404(
        user_id=payload.user_id,
        db=db,
    )

    await validate_project_member_candidate(
        project=project,
        member_user=member_user,
        db=db,
    )

    member = ProjectMember(
        project_id=payload.project_id,
        user_id=payload.user_id,
    )

    db.add(member)

    await db.commit()
    await db.refresh(member)

    return member
