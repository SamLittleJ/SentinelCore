from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_role, get_db
from app.models.user import User, UserRole
from app.schemas.user import UserRead
from app.models.audit_log import AuditEventType
from app.services.audit_service import create_audit_log
from sqlalchemy.orm import Session

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return current_user

@router.get("/admin-only")
def read_admin_only(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OWNER)),
) -> dict:
    create_audit_log(
        db=db,
        event_type=AuditEventType.ADMIN_ENDPOINT_ACCESSED,
        user=current_user,
        message=f"Admin endpoint accessed by user: {current_user.email}",
    )
    
    return {
        "message" : "You have admin-level access.",
        "username" : current_user.username,
        "role": current_user.role,
    }