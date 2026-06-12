from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.audit_log import AuditEventType
from app.models.security_event import SecurityEventType, SecuritySeverity
from app.models.user import User, UserRole
from app.schemas.user import UserRead
from app.services.audit_service import create_audit_log
from app.services.security_event_service import create_security_event

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return current_user


@router.get("/admin-only")
def read_admin_only(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_role(UserRole.ADMIN, UserRole.OWNER))
    ],
) -> dict:
    create_audit_log(
        db=db,
        event_type=AuditEventType.ADMIN_ENDPOINT_ACCESSED,
        user=current_user,
        message=f"Admin endpoint accessed by user: {current_user.email}",
    )

    create_security_event(
        db=db,
        event_type=SecurityEventType.ADMIN_ACCESS,
        severity=SecuritySeverity.INFO,
        user=current_user,
        message=f"Admin endpoint accessed by user: {current_user.email}",
    )

    return {
        "message": "You have admin-level access.",
        "username": current_user.username,
        "role": current_user.role,
    }
