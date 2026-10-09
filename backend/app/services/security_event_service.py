from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import database_now
from app.core.metrics import record_security_event
from app.models.security_event import (
    DETECTION_SOURCE,
    MITRE_TECHNIQUES,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User
from app.schemas.security_event import (
    AccountActivityFilters,
    FailedLoginSource,
    LatestDetection,
    SecurityEventFilters,
    SecuritySummary,
    SeverityBucket,
    SeverityCounts,
    TechniqueCount,
    ThreatLevel,
)
from app.services.detection_service import run_detection
from app.services.event_query import event_filter_conditions, fetch_event_page
from app.services.session_service import USER_AGENT_MAX_LENGTH


def create_security_event(
    db: Session,
    event_type: SecurityEventType,
    severity: SecuritySeverity,
    message: str,
    user: User | None = None,
    email: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    source: str = "backend",
) -> SecurityEvent:
    security_event = SecurityEvent(
        event_type=event_type,
        severity=severity,
        user_id=user.id if user else None,
        email=email if email else (user.email if user else None),
        ip_address=ip_address,
        user_agent=user_agent[:USER_AGENT_MAX_LENGTH] if user_agent else None,
        source=source,
        message=message,
    )
    db.add(security_event)
    db.commit()
    db.refresh(security_event)
    record_security_event(event_type, severity)
    run_detection(db, security_event)
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
    filters: AccountActivityFilters,
) -> tuple[list[SecurityEvent], int | None]:
    """Security events about `user`'s account.

    These are the events the account took part in, as the actor or as the
    target of someone else's action. They also include failed and blocked
    logins that only name its email, since a wrong password does not link the
    attempt to a user. Those are limited to the account's lifetime, so attempts
    made against the email before it was registered stay hidden.
    """
    conditions = [
        or_(
            SecurityEvent.user_id == user.id,
            SecurityEvent.target_user_id == user.id,
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


TOP_FAILED_LOGIN_SOURCES = 5


def _severity_buckets(
    db: Session, now: datetime, width: timedelta, count: int
) -> list[SeverityBucket]:
    """Events per severity in `count` windows of `width`, measured back from
    `now`, oldest first."""
    since = now - width * count
    # 0 for the window that ends now, 1 for the one before it, and so on.
    age = func.floor(
        func.extract("epoch", now - SecurityEvent.created_at) / width.total_seconds()
    ).label("age")
    rows = db.execute(
        select(age, SecurityEvent.severity, func.count())
        .where(SecurityEvent.created_at >= since)
        .group_by(age, SecurityEvent.severity)
    ).all()
    counts: list[dict[str, int]] = [{} for _ in range(count)]
    for bucket_age, severity, events in rows:
        # Clamped: an event stamped exactly at `since` belongs to the oldest
        # window, as in the totals, and one stamped after `now` to the newest.
        index = count - 1 - max(0, min(int(bucket_age), count - 1))
        counts[index][severity.value] = events
    return [
        SeverityBucket(
            start=since + width * index,
            counts=SeverityCounts.model_validate(bucket),
        )
        for index, bucket in enumerate(counts)
    ]


def _techniques(db: Session, since: datetime) -> list[TechniqueCount]:
    rows = db.execute(
        select(SecurityEvent.event_type, func.count())
        .where(
            SecurityEvent.event_type.in_(MITRE_TECHNIQUES),
            SecurityEvent.created_at >= since,
        )
        .group_by(SecurityEvent.event_type)
    ).all()
    alerts: dict[str, int] = {}
    for event_type, events in rows:
        technique = MITRE_TECHNIQUES[event_type]
        alerts[technique] = alerts.get(technique, 0) + events
    return [
        TechniqueCount(
            technique=technique,
            alerts=total,
            event_types=[
                event_type
                for event_type, mapped in MITRE_TECHNIQUES.items()
                if mapped == technique
            ],
        )
        for technique, total in sorted(
            alerts.items(), key=lambda item: (-item[1], item[0])
        )
    ]


def _threat_level(db: Session, since: datetime, incidents: int) -> ThreatLevel:
    if incidents:
        return "incident"
    detection = db.scalar(
        select(SecurityEvent.id)
        .where(
            SecurityEvent.source == DETECTION_SOURCE,
            SecurityEvent.created_at >= since,
        )
        .limit(1)
    )
    return "warn" if detection is not None else "calm"


def _latest_detection(db: Session, since: datetime) -> LatestDetection | None:
    latest = db.execute(
        select(SecurityEvent.event_type, SecurityEvent.created_at)
        .where(
            SecurityEvent.event_type.in_(MITRE_TECHNIQUES),
            SecurityEvent.created_at >= since,
        )
        .order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc())
        .limit(1)
    ).first()
    if latest is None:
        return None
    event_type, created_at = latest
    return LatestDetection(
        technique=MITRE_TECHNIQUES[event_type], created_at=created_at
    )


def get_security_summary(db: Session) -> SecuritySummary:
    """Aggregate recent security activity for the organization overview.

    Windows are measured on the database clock, the one that stamps
    `created_at`.
    """
    now = database_now(db)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    severity_rows = db.execute(
        select(
            SecurityEvent.severity,
            func.count().filter(SecurityEvent.created_at >= day_ago),
            func.count(),
        )
        .where(SecurityEvent.created_at >= week_ago)
        .group_by(SecurityEvent.severity)
    ).all()
    last_24h = SeverityCounts.model_validate(
        {severity.value: day_count for severity, day_count, _ in severity_rows}
    )
    last_7d = SeverityCounts.model_validate(
        {severity.value: week_count for severity, _, week_count in severity_rows}
    )

    recent_failures = and_(
        SecurityEvent.event_type == SecurityEventType.LOGIN_FAILED,
        SecurityEvent.created_at >= day_ago,
    )
    failed_logins = db.execute(
        select(func.count()).select_from(SecurityEvent).where(recent_failures)
    ).scalar_one()

    failure_count = func.count().label("failed_logins")
    source_rows = db.execute(
        select(SecurityEvent.ip_address, failure_count)
        .where(recent_failures, SecurityEvent.ip_address.is_not(None))
        .group_by(SecurityEvent.ip_address)
        .order_by(failure_count.desc(), SecurityEvent.ip_address)
        .limit(TOP_FAILED_LOGIN_SOURCES)
    ).all()

    # A login stays locked for the lockout period after its latest
    # brute-force event, as in login_protection_service.
    locked_logins = db.execute(
        select(func.count(func.distinct(SecurityEvent.email))).where(
            SecurityEvent.event_type == SecurityEventType.BRUTE_FORCE_DETECTED,
            SecurityEvent.created_at
            > now - timedelta(minutes=settings.login_lockout_minutes),
        )
    ).scalar_one()

    users_total, users_inactive, accounts_locked = db.execute(
        select(
            func.count(),
            func.count().filter(User.is_active.is_not(True)),
            func.count().filter(User.locked_until > now),
        ).select_from(User)
    ).one()

    return SecuritySummary(
        generated_at=now,
        last_24h=last_24h,
        last_7d=last_7d,
        failed_logins_24h=failed_logins,
        locked_logins=locked_logins,
        top_failed_login_sources=[
            FailedLoginSource(ip_address=ip_address, failed_logins=count)
            for ip_address, count in source_rows
        ],
        users_total=users_total,
        users_inactive=users_inactive,
        accounts_locked=accounts_locked,
        threat_level=_threat_level(db, day_ago, last_24h.incident),
        latest_detection=_latest_detection(db, day_ago),
        hourly=_severity_buckets(db, now, timedelta(hours=1), 24),
        daily=_severity_buckets(db, now, timedelta(days=1), 7),
        techniques_7d=_techniques(db, week_ago),
    )
