import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.rbac import require_roles
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserRead, UserRoleUpdate, UserUpdateProfile
from app.services.cache import cache_delete_pattern, cache_get_json, cache_set_json
from app.services.storage import get_download_url, upload_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])

_CACHE_TTL = settings.REDIS_DEFAULT_TTL_SECONDS


# ---------------------------------------------------------------------------
# Admin: list all users
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[UserRead])
async def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=15, ge=1, le=100),
    q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    q_part = f":{q}" if q else ""
    cache_key = f"users:list:{current_user.id}:{current_user.role.value}:{skip}:{limit}{q_part}"
    cached = await cache_get_json(cache_key)
    if cached is not None:
        return cached

    stmt = select(User)
    if q:
        term = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.email).like(term),
                func.lower(User.full_name).like(term),
            )
        )
    result = await db.execute(stmt.order_by(User.id).offset(skip).limit(limit))
    users = result.scalars().all()
    data = [UserRead.model_validate(u).model_dump(mode="json") for u in users]
    await cache_set_json(cache_key, data, _CACHE_TTL)
    return data


@router.get("/leaders", response_model=list[UserRead])
async def list_project_leaders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Returns active users eligible to be set as project leaders (role: project_leader or admin)."""
    result = await db.execute(
        select(User)
        .where(
            User.role.in_([UserRole.PROJECT_LEADER, UserRole.ADMIN]),
            User.is_active == True,
        )
        .order_by(User.id)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Admin: update user role
# ---------------------------------------------------------------------------

@router.patch("/{user_id}/role", response_model=UserRead)
async def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Enforce admin cap when promoting someone to admin
    if payload.role == UserRole.ADMIN and user.role != UserRole.ADMIN:
        admin_count = (await db.execute(
            select(func.count()).where(User.role == UserRole.ADMIN)
        )).scalar_one()
        if admin_count >= settings.MAX_ADMINS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum of {settings.MAX_ADMINS} admin(s) allowed. "
                       "Update MAX_ADMINS in config to increase the limit."
            )

    user.role = payload.role
    await db.commit()
    await db.refresh(user)

    await cache_delete_pattern("users:list:*")
    await cache_delete_pattern("projects:list:*")
    await cache_delete_pattern("issues:list:*")

    return user


# ---------------------------------------------------------------------------
# Admin: activate / deactivate user
# ---------------------------------------------------------------------------

@router.patch("/{user_id}/activate", response_model=UserRead)
async def activate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    await cache_delete_pattern("users:list:*")
    return user


@router.patch("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    await cache_delete_pattern("users:list:*")
    return user


# ---------------------------------------------------------------------------
# Own profile management
# ---------------------------------------------------------------------------

@router.patch("/me", response_model=UserRead)
async def update_my_profile(
    payload: UserUpdateProfile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/me/avatar", response_model=UserRead)
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    try:
        key = await upload_file(data=data, original_filename=file.filename or "avatar", mime_type=mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    current_user.avatar_key = key
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/me/avatar-url")
async def get_avatar_url(current_user: User = Depends(get_current_user)):
    if not current_user.avatar_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No avatar uploaded")
    return {"url": get_download_url(current_user.avatar_key)}
