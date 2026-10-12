from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, read_scope, require_role
from app.models.audit_log import AuditEventType
from app.models.user import User, UserRole
from app.schemas.pagination import Page
from app.schemas.security_event import (
    SecurityEventFilters,
    SecurityEventRead,
    SecuritySummary,
)
from app.services.audit_service import audit_read
from app.services.security_event_service import (
    get_security_summary,
    list_security_events,
)

router = APIRouter(prefix="/security", tags=["security"])

ORGANIZATION_ROLES = (UserRole.ADMIN, UserRole.OWNER, UserRole.SECURITY_ANALYST)


@router.get("/events", response_model=Page[SecurityEventRead])
def read_security_events(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_role(*ORGANIZATION_ROLES)),
    ],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    filters: Annotated[SecurityEventFilters, Query()],
) -> Page[SecurityEventRead]:
    scope = read_scope(db, current_user, filters.organization_id)
    security_events, next_cursor = list_security_events(db, filters, scope)

    # Viewing is an audit fact, not a security signal, so it is recorded only
    # in the audit log and does not add noise to the security event stream.
    audit_read(
        db=db,
        event_type=AuditEventType.SECURITY_EVENTS_VIEWED,
        message=f"Viewed security events with {filters.describe()}",
        user=current_user,
        scope=scope,
        shown=(event.organization_id for event in security_events),
        ip_address=client_ip,
    )

    return Page[SecurityEventRead].model_validate(
        {"items": security_events, "next_cursor": next_cursor},
        from_attributes=True,
    )


@router.get("/summary", response_model=SecuritySummary)
def read_security_summary(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(*ORGANIZATION_ROLES))],
    organization_id: int | None = None,
) -> SecuritySummary:
    """Counts for the reader's organization; for the owner, for the whole
    platform or the organization named."""
    # Not audited: the overview loads it on every visit and it holds counts,
    # not records. Opening the events behind a count is audited as usual.
    return get_security_summary(db, read_scope(db, current_user, organization_id))
