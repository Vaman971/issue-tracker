from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rbac import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserRead

router = APIRouter(
    prefix="/users",tags=["users"]
)

@router.get(
    "/",
    response_model=list[UserRead]
)
async def list_users(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User))
    return result.scalars().all()

@router.patch(
    "/{user_id}/role",
    response_model=UserRead
)
async def updated_user_role(
    user_id: int,
    role: UserRole,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    user_result = await db.execute(select(User).where(User.id == user_id))

    user = user_result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.role = role

    await db.commit()
    await db.refresh(user)

    return user
