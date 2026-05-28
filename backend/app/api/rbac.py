"""
rbac.py 

A centralized RBAC file 

Helps to keep the rules consistent, bugs not appear and security gaps are covered
"""

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User, UserRole

def require_roles(*allowed_roles: UserRole):
    # inner function knows which roles are passed so it creates a checker specific to the roles pased
    async def role_checker(
            current_user: User = Depends(get_current_user),
    )-> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource"
            )
        
        return current_user
    
    return role_checker