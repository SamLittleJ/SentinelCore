from datetime import timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import record_security_event
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User
from app.schemas.security_event import (
    AccountActivityFilters,
    FailedLoginSource,
    SecurityEventFilters,
    SecuritySummary,
    SeverityCounts,
)
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


def get_security_summary(db: Session) -> SecuritySummary:
    """Aggregate recent security activity for the organization overview.

    Windows are measured on the database clock, the one that stamps
    `created_at`.
    """
    now = db.execute(select(func.now())).scalar_one()
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

    users_total, users_inactive = db.execute(
        select(
            func.count(), func.count().filter(User.is_active.is_not(True))
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
    )
