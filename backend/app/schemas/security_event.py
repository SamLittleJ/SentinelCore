from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict

from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User
from app.schemas.event_filters import EventFilters, EventPageFilters


class SecurityEventRead(BaseModel):
    id: int
    event_type: SecurityEventType
    severity: SecuritySeverity
    user_id: int | None
    target_user_id: int | None
    email: str | None
    ip_address: str | None
    source: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecurityEventFilters(EventFilters):
    event_type: list[SecurityEventType] = []
    severity: list[SecuritySeverity] = []


class MyActivityRead(BaseModel):
    """A security event about the reader's own account.

    The free-text message is left out: it is written for operators and may
    name other accounts. Clients describe events by their type.

    `as_target` marks actions someone else took on the reader's account, such
    as an owner changing their role. The IP address of those is the actor's,
    so it is left out as well.
    """

    id: int
    event_type: SecurityEventType
    severity: SecuritySeverity
    ip_address: str | None
    created_at: datetime
    as_target: bool

    @classmethod
    def for_reader(cls, event: SecurityEvent, reader: User) -> Self:
        as_target = event.target_user_id == reader.id and event.user_id != reader.id
        return cls(
            id=event.id,
            event_type=event.event_type,
            severity=event.severity,
            ip_address=None if as_target else event.ip_address,
            created_at=event.created_at,
            as_target=as_target,
        )


class AccountActivityFilters(EventPageFilters):
    event_type: list[SecurityEventType] = []
    severity: list[SecuritySeverity] = []


class SeverityCounts(BaseModel):
    info: int = 0
    warn: int = 0
    incident: int = 0


class FailedLoginSource(BaseModel):
    ip_address: str
    failed_logins: int


class SecuritySummary(BaseModel):
    """Aggregates for the organization overview, measured back from
    `generated_at` on the database clock."""

    generated_at: datetime
    last_24h: SeverityCounts
    last_7d: SeverityCounts
    failed_logins_24h: int
    # Emails whose logins are locked right now by brute-force protection.
    locked_logins: int
    # The addresses with the most failed logins in the last 24 hours.
    top_failed_login_sources: list[FailedLoginSource]
    users_total: int
    users_inactive: int
    # Accounts an operator has locked, and whose lock has not expired.
    accounts_locked: int
