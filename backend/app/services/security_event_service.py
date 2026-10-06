from sqlalchemy.orm import Session

from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User
from app.schemas.security_event import SecurityEventFilters
from app.services.event_query import fetch_event_page


def create_security_event(
    db: Session,
    event_type: SecurityEventType,
    severity: SecuritySeverity,
    message: str,
    user: User | None = None,
    email: str | None = None,
    ip_address: str | None = None,
    source: str = "backend",
) -> SecurityEvent:
    security_event = SecurityEvent(
        event_type=event_type,
        severity=severity,
        user_id=user.id if user else None,
        email=email if email else (user.email if user else None),
        ip_address=ip_address,
        source=source,
        message=message,
    )
    db.add(security_event)
    db.commit()
    db.refresh(security_event)
    return security_event


def list_security_events(
    db: Session,
    filters: SecurityEventFilters,
) -> tuple[list[SecurityEvent], int | None]:
    conditions = []
    if filters.event_type:
        conditions.append(SecurityEvent.event_type.in_(filters.event_type))
    if filters.severity:
        conditions.append(SecurityEvent.severity.in_(filters.severity))

    return fetch_event_page(db, SecurityEvent, filters, *conditions)
