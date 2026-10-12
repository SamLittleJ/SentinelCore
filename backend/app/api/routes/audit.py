from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, read_scope, require_role
from app.models.audit_log import AuditEventType
from app.models.user import User, UserRole
from app.schemas.audit_log import AuditLogFilters, AuditLogRead
from app.schemas.pagination import Page
from app.services.audit_service import audit_read, list_audit_logs

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
    scope = read_scope(db, current_user, filters.organization_id)
    audit_logs, next_cursor = list_audit_logs(db, filters, scope)

    # Recorded after the query, so the response never contains its own record.
    audit_read(
        db=db,
        event_type=AuditEventType.AUDIT_LOGS_VIEWED,
        message=f"Viewed audit logs with {filters.describe()}",
        user=current_user,
        scope=scope,
        shown=(log.organization_id for log in audit_logs),
        ip_address=client_ip,
    )

    return Page[AuditLogRead].model_validate(
        {"items": audit_logs, "next_cursor": next_cursor},
        from_attributes=True,
    )
