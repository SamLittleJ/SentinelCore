"""Brute-force protection for login.

Lockout state is derived from recorded security events rather than stored
separately. Times come from the database clock, the same one that stamps
`created_at`, so comparisons never mix application and database time.

Only this application's own sign-ins count. Sign-ins other systems report
through ingestion reach the detection rules, but never lock anyone out of
this application.
"""

import math
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import database_now
from app.core.metrics import record_security_event
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    BACKEND_SOURCE,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User


def _latest_event_time(
    db: Session,
    email: str,
    event_type: SecurityEventType,
) -> datetime | None:
    statement = select(func.max(SecurityEvent.created_at)).where(
        SecurityEvent.email == email,
        SecurityEvent.event_type == event_type,
        SecurityEvent.source == BACKEND_SOURCE,
    )
    return db.scalar(statement)


def get_lockout_seconds_remaining(db: Session, email: str) -> int:
    """Return how many seconds logins for `email` stay locked, or 0."""
    locked_at = _latest_event_time(db, email, SecurityEventType.BRUTE_FORCE_DETECTED)
    if locked_at is None:
        return 0

    locked_until = locked_at + timedelta(minutes=settings.login_lockout_minutes)
    remaining = locked_until - database_now(db)
    return max(0, math.ceil(remaining.total_seconds()))


def count_recent_failed_logins(db: Session, email: str) -> int:
    """Count failed logins for `email` inside the failure window.

    Failures before the latest successful login or the latest lockout are
    ignored, so a success resets the count and an expired lockout does not
    immediately trigger another one.
    """
    since = database_now(db) - timedelta(minutes=settings.login_failure_window_minutes)

    for event_type in (
        SecurityEventType.LOGIN_SUCCESS,
        SecurityEventType.BRUTE_FORCE_DETECTED,
    ):
        event_time = _latest_event_time(db, email, event_type)
        if event_time is not None and event_time > since:
            since = event_time

    statement = select(func.count(SecurityEvent.id)).where(
        SecurityEvent.email == email,
        SecurityEvent.event_type == SecurityEventType.LOGIN_FAILED,
        SecurityEvent.source == BACKEND_SOURCE,
        SecurityEvent.created_at > since,
    )
    return db.execute(statement).scalar_one()


def lock_login(
    db: Session,
    email: str,
    user: User | None,
    ip_address: str | None,
) -> int:
    """Record a lockout for `email` and return its duration in seconds.

    The events are linked to the targeted account when it exists, even if the
    failed attempts did not authenticate it.
    """
    message = (
        f"Login locked for email: {email} for {settings.login_lockout_minutes} "
        f"minutes after {settings.login_max_failed_attempts} failed attempts"
    )
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
    user_id = user.id if user else None

    db.add_all(
        [
            AuditLog(
                event_type=AuditEventType.LOGIN_LOCKED,
                user_id=user_id,
                email=email,
                ip_address=ip_address,
                message=message,
            ),
            SecurityEvent(
                event_type=SecurityEventType.BRUTE_FORCE_DETECTED,
                severity=SecuritySeverity.INCIDENT,
                user_id=user_id,
                email=email,
                ip_address=ip_address,
                source=BACKEND_SOURCE,
                message=message,
                # Raised by this application's own sign-in, as it happens.
                occurred_at=func.now(),
            ),
        ]
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    record_security_event(
        SecurityEventType.BRUTE_FORCE_DETECTED, SecuritySeverity.INCIDENT
    )
    return settings.login_lockout_minutes * 60
