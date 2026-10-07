from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, require_role
from app.models.audit_log import AuditEventType
from app.models.user import User, UserRole
from app.schemas.pagination import Page
from app.schemas.security_event import SecurityEventFilters, SecurityEventRead
from app.services.audit_service import create_audit_log
from app.services.security_event_service import list_security_events

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/events", response_model=Page[SecurityEventRead])
def read_security_events(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(
            require_role(UserRole.ADMIN, UserRole.OWNER, UserRole.SECURITY_ANALYST)
        ),
    ],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    filters: Annotated[SecurityEventFilters, Query()],
) -> Page[SecurityEventRead]:
    security_events, next_cursor = list_security_events(db, filters)

    # Viewing is an audit fact, not a security signal, so it is recorded only
    # in the audit log and does not add noise to the security event stream.
    create_audit_log(
        db=db,
        event_type=AuditEventType.SECURITY_EVENTS_VIEWED,
        user=current_user,
        ip_address=client_ip,
        message=f"Viewed security events with {filters.describe()}",
    )

    return Page[SecurityEventRead].model_validate(
        {"items": security_events, "next_cursor": next_cursor},
        from_attributes=True,
    )
