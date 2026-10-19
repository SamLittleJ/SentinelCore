"""A limit on failed sign-ins per address, of any email.

The lockout (services/login_protection_service.py) counts failures per email,
so one address could still try a common password on every account (a spray),
or lock a victim out again each time the lock ends. Each address has a token
bucket: every attempt takes a token before the password is checked, and only
a successful sign-in gives it back. An address with no token left is refused
before anything else is checked.

The buckets live in the database, so every API process shares them, and
their times come from the database clock.
"""

import ipaddress
import logging
import math
from datetime import timedelta
from typing import NamedTuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import database_now
from app.core.metrics import LOGIN_REFUSED, record_security_event
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    BACKEND_SOURCE,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.sign_in_address_limit import SignInAddressLimit

logger = logging.getLogger(__name__)

# Requests whose address is not known share one bucket: not knowing an
# address must not be a way around the limit.
UNKNOWN_ADDRESS = "unknown"
# A provider gives one IPv6 customer a whole /64 network, whose addresses its
# owner may change at will.
IPV6_NETWORK_PREFIX = 64


class Attempt(NamedTuple):
    # Seconds until the address may try again; 0 when the attempt may go on.
    retry_after: int
    # The attempt took the address's last token: if it fails, the address is
    # limited from now on.
    took_last: bool


def address_key(client_ip: str | None) -> str:
    """The bucket `client_ip` counts in: the IPv4 address itself, the /64
    network of an IPv6 address, or UNKNOWN_ADDRESS."""
    if client_ip is None:
        return UNKNOWN_ADDRESS
    address = ipaddress.ip_address(client_ip)
    if isinstance(address, ipaddress.IPv6Address):
        # An IPv4 client of an IPv6 socket.
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        network = f"{address}/{IPV6_NETWORK_PREFIX}"
        return str(ipaddress.ip_network(network, strict=False))
    return str(address)


def _per_second() -> float:
    return settings.login_address_failures_per_hour / 3600


def take_attempt(db: Session, address: str) -> Attempt:
    """Take a token from `address`'s bucket, if it holds one, and commit.

    The row stays locked until the commit, so attempts from one address take
    their tokens one after another and never spend the same one twice. The
    commit comes before the password is checked, so the lock is not held
    while it is.
    """
    capacity = settings.login_address_burst
    db.execute(
        insert(SignInAddressLimit)
        .values(address=address, tokens=capacity, refilled_at=func.now())
        .on_conflict_do_nothing(index_elements=[SignInAddressLimit.address])
    )
    bucket = db.scalars(
        select(SignInAddressLimit)
        .where(SignInAddressLimit.address == address)
        .with_for_update()
        # The row may be in the session from an earlier request.
        .execution_options(populate_existing=True)
    ).one()
    now = database_now(db)
    # An attempt that waited for the lock may have started before the one that
    # held it; time never runs backwards for the bucket.
    elapsed = max(0.0, (now - bucket.refilled_at).total_seconds())
    available = min(capacity, bucket.tokens + elapsed * _per_second())
    bucket.refilled_at = max(now, bucket.refilled_at)

    if available >= 1:
        bucket.tokens = available - 1
        attempt = Attempt(retry_after=0, took_last=bucket.tokens < 1)
    else:
        bucket.tokens = available
        attempt = Attempt(
            retry_after=math.ceil((1 - available) / _per_second()), took_last=False
        )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return attempt


def give_back(db: Session, address: str) -> None:
    """Return the token a successful sign-in took from `address`'s bucket."""
    db.execute(
        update(SignInAddressLimit)
        .where(SignInAddressLimit.address == address)
        .values(
            tokens=func.least(
                SignInAddressLimit.tokens + 1, settings.login_address_burst
            )
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def refuse_attempt(address: str) -> None:
    """Count an attempt refused because `address` is over its limit.

    Only a metric and a log line: a security event for every refusal would let
    one address fill the event table.
    """
    LOGIN_REFUSED.inc()
    logger.warning("Sign-in address limit reached", extra={"address": address})


def limit_address(db: Session, address: str, client_ip: str | None) -> None:
    """Record that `address` spent its last failed attempt.

    Once per bucket emptied, by the failure that took the last token. The
    records belong to the platform: an address is no organization's.
    """
    message = (
        f"Sign-in attempts limited for address {address} after too many failed "
        f"attempts: at most {settings.login_address_burst} at once, then "
        f"{settings.login_address_failures_per_hour} an hour"
    )
    db.add_all(
        [
            AuditLog(
                event_type=AuditEventType.LOGIN_ADDRESS_LIMITED,
                ip_address=client_ip,
                message=message,
            ),
            SecurityEvent(
                event_type=SecurityEventType.LOGIN_ADDRESS_LIMITED,
                severity=SecuritySeverity.WARN,
                ip_address=client_ip,
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
        SecurityEventType.LOGIN_ADDRESS_LIMITED, SecuritySeverity.WARN
    )


def delete_full_buckets(db: Session) -> int:
    """Delete the buckets that have filled up again, which mean the same as
    none. Returns how many were deleted."""
    full_after = timedelta(
        hours=settings.login_address_burst / settings.login_address_failures_per_hour
    )
    deleted = db.scalars(
        delete(SignInAddressLimit)
        .where(SignInAddressLimit.refilled_at <= func.now() - full_after)
        .returning(SignInAddressLimit.address)
    ).all()
    db.commit()
    return len(deleted)
