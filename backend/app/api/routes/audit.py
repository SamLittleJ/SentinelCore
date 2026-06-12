from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.schemas.audit_log import AuditLogRead
from app.services.audit_service import list_audit_logs

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs", response_model=list[AuditLogRead])
def read_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(
            require_role(UserRole.ADMIN, UserRole.OWNER, UserRole.SECURITY_ANALYST)
        ),
    ],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AuditLog]:
    return list_audit_logs(db, limit)
