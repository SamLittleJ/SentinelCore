"""Falco's alerts from the platform's cluster, kept as security events of the
platform (phase E3). Falco itself decides what happened; this service keeps
only the rules in `RULES`, writes its own message and stores the same alert
once per window."""

from datetime import timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.metrics import RUNTIME_ALERTS, record_security_event
from app.models.security_event import (
    FALCO_SOURCE,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.schemas.runtime import RULES, FalcoAlert, FalcoFields

# A rule can fire many times a second for one action; the same alert within
# this window of an earlier one is counted, not stored again.
DUPLICATE_WINDOW = timedelta(minutes=10)

SEVERITIES = {
    SecurityEventType.CONTAINER_SHELL_DETECTED: SecuritySeverity.INCIDENT,
    SecurityEventType.SENSITIVE_FILE_READ: SecuritySeverity.INCIDENT,
    SecurityEventType.CONTAINER_NETWORK_TOOL: SecuritySeverity.WARN,
}

Outcome = Literal["stored", "ignored", "duplicate"]


def describe(event_type: SecurityEventType, fields: FalcoFields) -> str:
    where = (
        f"in container {fields.container} of pod {fields.pod} "
        f"(namespace {fields.namespace})"
    )
    if event_type == SecurityEventType.CONTAINER_SHELL_DETECTED:
        return f"Shell with a terminal {where}"
    if event_type == SecurityEventType.SENSITIVE_FILE_READ:
        return f"Sensitive file {fields.file} read {where}"
    return f"Shell input or output sent over the network {where}"


def store_runtime_alert(db: Session, alert: FalcoAlert) -> Outcome:
    """Store `alert` as a platform security event, unless its rule is not
    kept or the same alert was stored within the window around its time."""
    event_type = RULES.get(alert.rule)
    if event_type is None:
        RUNTIME_ALERTS.labels(outcome="ignored").inc()
        return "ignored"

    # The message holds the type's own words and where it happened, so the
    # same message is the same alert.
    message = describe(event_type, alert.output_fields)
    earlier = db.scalar(
        select(SecurityEvent.id)
        .where(
            SecurityEvent.event_type == event_type,
            SecurityEvent.source == FALCO_SOURCE,
            SecurityEvent.message == message,
            SecurityEvent.occurred_at > alert.time - DUPLICATE_WINDOW,
            SecurityEvent.occurred_at < alert.time + DUPLICATE_WINDOW,
        )
        .limit(1)
    )
    if earlier is not None:
        RUNTIME_ALERTS.labels(outcome="duplicate").inc()
        return "duplicate"

    severity = SEVERITIES[event_type]
    db.add(
        SecurityEvent(
            event_type=event_type,
            severity=severity,
            source=FALCO_SOURCE,
            message=message,
            occurred_at=alert.time,
        )
    )
    db.commit()
    record_security_event(event_type, severity)
    RUNTIME_ALERTS.labels(outcome="stored").inc()
    return "stored"
