from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.metrics import record_security_event
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User
from app.schemas.security_event import MyActivityFilters, SecurityEventFilters
from app.services.event_query import event_filter_conditions, fetch_event_page


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
    record_security_event(event_type, severity)
    return security_event


def list_security_events(
    db: Session,
    filters: SecurityEventFilters,
) -> tuple[list[SecurityEvent], int | None]:
    conditions = event_filter_conditions(SecurityEvent, filters)
    if filters.event_type:
        conditions.append(SecurityEvent.event_type.in_(filters.event_type))
    if filters.severity:
        conditions.append(SecurityEvent.severity.in_(filters.severity))

    return fetch_event_page(db, SecurityEvent, filters, *conditions)


def list_user_activity(
    db: Session,
    user: User,
    filters: MyActivityFilters,
) -> tuple[list[SecurityEvent], int | None]:
    """Security events about `user`'s own account.

    Besides events linked to the account, this includes failed and blocked
    logins that only name its email, since a wrong password does not link the
    attempt to a user. Those are limited to the account's lifetime, so attempts
    made against the email before it was registered stay hidden.
    """
    conditions = [
        or_(
            SecurityEvent.user_id == user.id,
            and_(
                SecurityEvent.user_id.is_(None),
                SecurityEvent.email == user.email,
                SecurityEvent.created_at >= user.created_at,
            ),
        )
    ]
    if filters.event_type:
        conditions.append(SecurityEvent.event_type.in_(filters.event_type))
    if filters.severity:
        conditions.append(SecurityEvent.severity.in_(filters.severity))

    return fetch_event_page(db, SecurityEvent, filters, *conditions)
