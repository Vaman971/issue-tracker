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

# Every role may read from the RAG pipeline: it answers questions about issues,
# it does not act on them. Listed explicitly rather than accepting "any
# authenticated user" so that adding a future role is a deliberate grant.
RAG_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.PROJECT_LEADER,
    UserRole.DEVELOPER,
    UserRole.QA,
    UserRole.VIEWER,
)


async def require_rag_access(
    current_user: User = Depends(require_roles(*RAG_READ_ROLES)),
) -> User:
    """Authenticated, holding a role allowed to query RAG, and still active.

    get_current_user validates the token and loads the user but does not look
    at is_active, so a deactivated account keeps working until its token
    expires. Checked here so a disabled user cannot query the corpus.
    """

    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    return current_user
