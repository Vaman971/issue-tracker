from fastapi import APIRouter, Depends

from app.api.rbac import require_roles
from app.models.user import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])

# complete auth flow
"""
JWT verification
    ↓
User loading
    ↓
Role checking
    ↓
Business logic
"""

@router.get("/dashboard")
async def admin_dashboard(
    current_user:User = Depends(require_roles(UserRole.ADMIN)),
):
    return {
        "message": "Welcome to the admin dashboard",
        "user_email": current_user.email,
        "role": current_user.role.value
    }
