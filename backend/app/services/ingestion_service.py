"""Security events reported by other systems through an API key.

Ingested events are stored like the application's own, with the key's source,
and go through the same detection rules. They are kept at the time they
happened, so the rules judge each against the events around it.

Each key has a rate limit, kept as a token bucket on its row: the bucket
holds up to INGEST_BURST_EVENTS tokens and refills at INGEST_EVENTS_PER_MINUTE.
Every event takes a token, and a batch that does not fit is refused whole.
The state lives in the database, so every API process shares one bucket per
key, and its time is the database clock.
"""

import logging
import math

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import database_now
from app.core.metrics import (
    INGEST_REFUSED_EVENTS,
    INGESTED_EVENTS,
    record_security_event,
)
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

logger = logging.getLogger(__name__)


def take_tokens(db: Session, api_key: ApiKey, count: int) -> int:
    """Take `count` tokens from `api_key`'s bucket, if it holds them, and
    return 0. Otherwise take none and return the whole seconds until it will.

    The key's row stays locked until the transaction ends, so requests with
    the same key take their tokens one after another and never spend the same
    ones twice.
    """
    db.refresh(api_key, with_for_update=True)
    now = database_now(db)
    capacity = settings.ingest_burst_events
    per_second = settings.ingest_events_per_minute / 60

    if api_key.rate_tokens is None or api_key.rate_refilled_at is None:
        available = float(capacity)
    else:
        # A request that waited for the lock may have started before the one
        # that held it; time never runs backwards for the bucket.
        elapsed = max(0.0, (now - api_key.rate_refilled_at).total_seconds())
        available = min(capacity, api_key.rate_tokens + elapsed * per_second)
        now = max(now, api_key.rate_refilled_at)

    api_key.rate_refilled_at = now
    if available >= count:
        api_key.rate_tokens = available - count
        return 0
    api_key.rate_tokens = available
    return math.ceil((count - available) / per_second)


def refuse_events(db: Session, api_key: ApiKey, count: int) -> None:
    """Record that `api_key` sent `count` events over its rate limit.

    Only a metric and a log line: a security event for every refusal would let
    a flood fill the event table it is kept out of.
    """
    prefix, source = api_key.prefix, api_key.source
    # The key was used, even if its events were not taken.
    api_key.last_used_at = func.now()
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    INGEST_REFUSED_EVENTS.labels(source=source).inc(count)
    logger.warning(
        "Ingestion rate limit reached",
        extra={"api_key_prefix": prefix, "source": source, "events": count},
    )


def ingest_events(db: Session, api_key: ApiKey, events: list[IngestedEvent]) -> int:
    """Store `events` from `api_key`'s source, run the detection rules on each
    in the order they happened, and return how many were stored."""
    # Successful sign-ins name the account they opened; a failed one names
    # only an email, as for the application's own sign-ins.
    # Only the key's own organization's accounts: a key never links an event
    # to another organization's account.
    emails = {event.email for event in events if event.event_type == "login_success"}
    user_ids: dict[str, int] = {}
    if emails:
        rows = db.execute(
            select(User.email, User.id).where(
                User.email.in_(emails),
                User.organization_id == api_key.organization_id,
            )
        )
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
                organization_id=api_key.organization_id,
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
