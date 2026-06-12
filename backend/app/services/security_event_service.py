from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User


def create_security_event(
    db: Session,
    event_type: SecurityEventType,
    severity: SecuritySeverity,
    message: str,
    user: User | None = None,
    email: str | None = None,
    source: str = "backend",
) -> SecurityEvent:
    security_event = SecurityEvent(
        event_type=event_type,
        severity=severity,
        user_id=user.id if user else None,
        email=email if email else (user.email if user else None),
        source=source,
        message=message,
    )
    db.add(security_event)
    db.commit()
    db.refresh(security_event)
    return security_event


def list_security_events(db: Session, limit: int = 50) -> list[SecurityEvent]:
    statement = (
        select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit)
    )

    return list(db.scalars(statement).all())
