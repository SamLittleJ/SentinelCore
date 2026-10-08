"""Security events reported by other systems through an API key.

Ingested events are stored like the application's own, with the key's source,
and go through the same detection rules. They are kept at the time they
happened, so the rules judge each against the events around it.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.metrics import INGESTED_EVENTS, record_security_event
from app.models.api_key import ApiKey
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User
from app.schemas.ingest import IngestedEvent
from app.services.detection_service import run_detection

# The sender reports what happened; the server decides how much it matters.
SEVERITIES = {
    SecurityEventType.LOGIN_SUCCESS: SecuritySeverity.INFO,
    SecurityEventType.LOGIN_FAILED: SecuritySeverity.WARN,
}
OUTCOMES = {
    SecurityEventType.LOGIN_SUCCESS: "Successful",
    SecurityEventType.LOGIN_FAILED: "Failed",
}


def ingest_events(db: Session, api_key: ApiKey, events: list[IngestedEvent]) -> int:
    """Store `events` from `api_key`'s source, run the detection rules on each
    in the order they happened, and return how many were stored."""
    # Successful sign-ins name the account they opened; a failed one names
    # only an email, as for the application's own sign-ins.
    emails = {event.email for event in events if event.event_type == "login_success"}
    user_ids: dict[str, int] = {}
    if emails:
        rows = db.execute(select(User.email, User.id).where(User.email.in_(emails)))
        user_ids = {email: user_id for email, user_id in rows}

    stored = []
    for event in sorted(events, key=lambda item: item.occurred_at):
        event_type = SecurityEventType(event.event_type)
        stored.append(
            SecurityEvent(
                event_type=event_type,
                severity=SEVERITIES[event_type],
                user_id=(
                    user_ids.get(event.email)
                    if event_type == SecurityEventType.LOGIN_SUCCESS
                    else None
                ),
                email=event.email,
                ip_address=str(event.ip_address) if event.ip_address else None,
                user_agent=event.user_agent,
                source=api_key.source,
                message=(
                    f"{OUTCOMES[event_type]} sign-in for {event.email}, "
                    f"reported by {api_key.source}"
                ),
                created_at=event.occurred_at,
            )
        )

    api_key.last_used_at = func.now()
    db.add_all(stored)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    INGESTED_EVENTS.labels(source=api_key.source).inc(len(stored))
    for security_event in stored:
        record_security_event(security_event.event_type, security_event.severity)
        run_detection(db, security_event)
    return len(stored)
