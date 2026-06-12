from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.audit_log import AuditEventType
from app.models.security_event import SecurityEventType, SecuritySeverity
from app.models.user import User, UserRole
from app.schemas.user import UserRead
from app.services.audit_service import create_audit_log
from app.services.security_event_service import create_security_event
from app.services.user_service import list_users

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=list[UserRead])
def read_users(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN, UserRole.OWNER)),
    ],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[User]:
    create_audit_log(
        db=db,
        user=current_user,
        event_type=AuditEventType.ADMIN_ENDPOINT_ACCESSED,
        message="Admin listed users",
    )

    create_security_event(
        db=db,
        user=current_user,
        event_type=SecurityEventType.ADMIN_ACCESS,
        severity=SecuritySeverity.INFO,
        message="Admin listed users",
    )

    return list_users(db, limit=limit, offset=offset)
