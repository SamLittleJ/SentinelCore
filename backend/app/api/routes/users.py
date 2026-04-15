from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return current_user

@router.get("/admin-only")
def read_admin_only(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OWNER)),
) -> dict:
    return {
        "message" : "You have admin-level access.",
        "username" : current_user.username,
        "role": current_user.role,
    }