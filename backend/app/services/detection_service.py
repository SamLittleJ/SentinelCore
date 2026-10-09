"""Detection rules over the security event stream.

Each rule watches some event types. When such an event is recorded, the rule
looks back over the events before it and may raise an alert: a security event
of its own type, from the "detection" source, mapped to the MITRE ATT&CK
technique it detects (models/security_event.py). Alerts are not watched by
any rule, so detection cannot loop.

Rules only alert. Responding stays with the operators, through containment,
so a false positive never locks anyone out. Brute-force protection is the
exception: it blocks the email, and lives in login_protection_service.py.

Windows are measured back from the triggering event's own time, so an event
that arrives late is judged against the events around it. Alerts keep that
time in `occurred_at`, and rules that look at earlier alerts compare it, never
`created_at`, which is when an alert was raised.
"""

import ipaddress
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import record_security_event
from app.models.security_event import (
    DETECTION_SOURCE,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Alert:
    severity: SecuritySeverity
    message: str
    user_id: int | None = None
    target_user_id: int | None = None
    email: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class Rule:
    alert_type: SecurityEventType
    triggers: frozenset[SecurityEventType]
    evaluate: Callable[[Session, SecurityEvent], Alert | None]


def detect_password_spray(db: Session, event: SecurityEvent) -> Alert | None:
    """T1110.003: one address failing sign-ins for many different emails.

    Counts the emails that failed from the event's address within the window,
    after the latest spray alert for that address up to the event, so a
    continuing attack raises a new alert only once enough new emails have been
    tried, and a log delivered twice raises none. Alerts are compared by the
    time of the failure that raised them: one raised just now about an older
    spray does not hide a later spray reported late.
    """
    if event.ip_address is None:
        return None

    window = timedelta(minutes=settings.detection_spray_window_minutes)
    since = event.created_at - window
    latest_alert = db.scalar(
        select(func.max(SecurityEvent.occurred_at)).where(
            SecurityEvent.event_type == SecurityEventType.PASSWORD_SPRAY_DETECTED,
            SecurityEvent.ip_address == event.ip_address,
            SecurityEvent.occurred_at <= event.created_at,
        )
    )
    if latest_alert is not None and latest_alert > since:
        since = latest_alert

    accounts = db.scalar(
        select(func.count(func.distinct(SecurityEvent.email))).where(
            SecurityEvent.ip_address == event.ip_address,
            SecurityEvent.event_type == SecurityEventType.LOGIN_FAILED,
            SecurityEvent.created_at > since,
            SecurityEvent.created_at <= event.created_at,
        )
    )
    if accounts is None or accounts < settings.detection_spray_min_accounts:
        return None

    return Alert(
        severity=SecuritySeverity.INCIDENT,
        ip_address=event.ip_address,
        message=(
            f"Password spray from {event.ip_address}: failed sign-ins for "
            f"{accounts} different emails within "
            f"{settings.detection_spray_window_minutes} minutes"
        ),
    )


def detect_dormant_account_login(db: Session, event: SecurityEvent) -> Alert | None:
    """T1078: a sign-in to an account that had none for a long time.

    An account that never signed in before counts from its creation, so an
    old account used for the first time is flagged too.
    """
    if event.user_id is None:
        return None
    user = db.get(User, event.user_id)
    if user is None:
        return None

    previous = db.scalar(
        select(func.max(SecurityEvent.created_at)).where(
            SecurityEvent.user_id == user.id,
            SecurityEvent.event_type == SecurityEventType.LOGIN_SUCCESS,
            SecurityEvent.created_at < event.created_at,
        )
    )
    last_seen = previous if previous is not None else user.created_at
    idle = event.created_at - last_seen
    if idle < timedelta(days=settings.detection_dormant_days):
        return None

    activity = "the previous one" if previous is not None else "the account's creation"
    return Alert(
        severity=SecuritySeverity.WARN,
        user_id=user.id,
        email=user.email,
        ip_address=event.ip_address,
        message=(f"Sign-in to user_id={user.id} {idle.days} days after {activity}"),
    )


# Addresses in the same /24 (IPv4) or /64 (IPv6) count as one network: a home
# or office router hands out addresses from one such block.
NETWORK_PREFIXES = {4: 24, 6: 64}
# Version numbers, such as "143.0" or "10_15_7", change with every update.
VERSION_NUMBER = re.compile(r"\d+(?:[._]\d+)*")


def network_of(ip_address: str) -> str | None:
    try:
        address = ipaddress.ip_address(ip_address)
    except ValueError:
        return None
    prefix = NETWORK_PREFIXES[address.version]
    return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False))


def device_of(user_agent: str) -> str:
    """The browser and system a user agent names, without their versions, so
    an update does not make a known device look new."""
    return VERSION_NUMBER.sub("", user_agent)


def detect_unfamiliar_sign_in(db: Session, event: SecurityEvent) -> Alert | None:
    """T1078: a sign-in from a network and a device the account has not used.

    Each alone is common (a trip, a new laptop), so only both together alert.
    The account's habits are its sign-ins of the lookback period that recorded
    both an address and a user agent; with fewer than the minimum, it is still
    learning and is not judged. A sign-in that is flagged becomes a habit, so
    repeated sign-ins from the same place alert once.
    """
    if event.user_id is None or event.ip_address is None or not event.user_agent:
        return None
    network = network_of(event.ip_address)
    if network is None:
        return None

    since = event.created_at - timedelta(
        days=settings.detection_unfamiliar_lookback_days
    )
    habits = db.execute(
        select(
            SecurityEvent.ip_address,
            SecurityEvent.user_agent,
            func.count(),
        )
        .where(
            SecurityEvent.user_id == event.user_id,
            SecurityEvent.event_type == SecurityEventType.LOGIN_SUCCESS,
            SecurityEvent.created_at >= since,
            SecurityEvent.created_at < event.created_at,
            SecurityEvent.ip_address.is_not(None),
            SecurityEvent.user_agent.is_not(None),
        )
        .group_by(SecurityEvent.ip_address, SecurityEvent.user_agent)
    ).all()
    if sum(count for _, _, count in habits) < (
        settings.detection_unfamiliar_min_sign_ins
    ):
        return None

    networks = {network_of(ip) for ip, _, _ in habits}
    devices = {device_of(user_agent) for _, user_agent, _ in habits}
    if network in networks or device_of(event.user_agent) in devices:
        return None

    return Alert(
        severity=SecuritySeverity.WARN,
        user_id=event.user_id,
        email=event.email,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        message=(
            f"Sign-in to user_id={event.user_id} from an unfamiliar network "
            f"({network}) and device"
        ),
    )


# Roles that see or change every account in the organization.
PRIVILEGED_ROLES = frozenset({UserRole.ADMIN, UserRole.SECURITY_ANALYST})


def detect_privileged_role_granted(db: Session, event: SecurityEvent) -> Alert | None:
    """T1098: an account given a role that reaches every other account, by a
    role change or by accepting an invitation with that role.

    The role is read from the account, which the change has already updated.
    """
    if event.target_user_id is None:
        return None
    target = db.get(User, event.target_user_id)
    if target is None or target.role not in PRIVILEGED_ROLES:
        return None

    return Alert(
        severity=SecuritySeverity.WARN,
        user_id=event.user_id,
        target_user_id=target.id,
        email=event.email,
        ip_address=event.ip_address,
        message=f"user_id={target.id} was granted the {target.role.value} role",
    )


RULES: tuple[Rule, ...] = (
    Rule(
        alert_type=SecurityEventType.PASSWORD_SPRAY_DETECTED,
        triggers=frozenset({SecurityEventType.LOGIN_FAILED}),
        evaluate=detect_password_spray,
    ),
    Rule(
        alert_type=SecurityEventType.DORMANT_ACCOUNT_LOGIN,
        triggers=frozenset({SecurityEventType.LOGIN_SUCCESS}),
        evaluate=detect_dormant_account_login,
    ),
    Rule(
        alert_type=SecurityEventType.UNFAMILIAR_SIGN_IN,
        triggers=frozenset({SecurityEventType.LOGIN_SUCCESS}),
        evaluate=detect_unfamiliar_sign_in,
    ),
    Rule(
        alert_type=SecurityEventType.PRIVILEGED_ROLE_GRANTED,
        triggers=frozenset(
            {SecurityEventType.USER_ROLE_CHANGED, SecurityEventType.USER_REGISTERED}
        ),
        evaluate=detect_privileged_role_granted,
    ),
)


def run_detection(db: Session, event: SecurityEvent) -> list[SecurityEvent]:
    """Run the rules that watch `event`, which must already be committed, and
    store the alerts they raise.

    A failing rule is logged and its alerts dropped: detection never undoes or
    fails the action that triggered it.
    """
    rules = [rule for rule in RULES if event.event_type in rule.triggers]
    if not rules:
        return []

    alerts = []
    try:
        for rule in rules:
            alert = rule.evaluate(db, event)
            if alert is not None:
                alerts.append(
                    SecurityEvent(
                        event_type=rule.alert_type,
                        severity=alert.severity,
                        user_id=alert.user_id,
                        target_user_id=alert.target_user_id,
                        email=alert.email,
                        ip_address=alert.ip_address,
                        user_agent=alert.user_agent,
                        source=DETECTION_SOURCE,
                        message=alert.message,
                        occurred_at=event.created_at,
                    )
                )
        if not alerts:
            return []
        db.add_all(alerts)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Detection failed",
            extra={"event_id": event.id, "event_type": event.event_type.value},
        )
        return []

    for alert in alerts:
        record_security_event(alert.event_type, alert.severity)
    return alerts
