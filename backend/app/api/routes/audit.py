from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, require_role
from app.models.audit_log import AuditEventType
from app.models.user import User, UserRole
from app.schemas.audit_log import AuditLogFilters, AuditLogRead
from app.schemas.pagination import Page
from app.services.audit_service import create_audit_log, list_audit_logs

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs", response_model=Page[AuditLogRead])
def read_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(
            require_role(UserRole.ADMIN, UserRole.OWNER, UserRole.SECURITY_ANALYST)
        ),
    ],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    filters: Annotated[AuditLogFilters, Query()],
) -> Page[AuditLogRead]:
    audit_logs, next_cursor = list_audit_logs(db, filters)

    # Recorded after the query, so the response never contains its own record.
    create_audit_log(
        db=db,
        event_type=AuditEventType.AUDIT_LOGS_VIEWED,
        user=current_user,
        ip_address=client_ip,
        message=f"Viewed audit logs with {filters.describe()}",
    )

    return Page[AuditLogRead].model_validate(
        {"items": audit_logs, "next_cursor": next_cursor},
        from_attributes=True,
    )
