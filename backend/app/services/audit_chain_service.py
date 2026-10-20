"""Checks the audit chains that models/audit_log.py seals.

`verify_chains` reads every record of every chain and reports, for each, the
first record whose seal does not match ("changed") or whose place is skipped
("missing"). Deleting a chain's newest records leaves a shorter chain that
still verifies, so the periodic check, `check_audit_chains`, also remembers
each chain's length from its last run in this process and reports a shorter
one as "truncated". It writes each chain's length and head to the log and the
metrics, outside the database, as anchors to compare with later, and raises
an alert for each break.

The alert is a detection like the rules in detection_service.py: it only
alerts, maps to a MITRE ATT&CK technique and uses the `detection` source. It
is the platform's, since the owner of the tables is who could break a chain.
"""

import itertools
import logging
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Literal

from sqlalchemy import Row, func, select, text
from sqlalchemy.orm import Session

from app.core.audit_seal import GENESIS, seal
from app.core.config import settings
from app.core.metrics import (
    AUDIT_CHAIN_INTACT,
    AUDIT_CHAIN_RECORDS,
    record_security_event,
)
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.security_event import (
    DETECTION_SOURCE,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)

logger = logging.getLogger(__name__)

Problem = Literal["changed", "missing", "truncated"]

# The advisory lock under which a process raises an alert ("AUDA"), so two
# processes checking at once raise it once.
ALERT_LOCK = 0x41554441


@dataclass(frozen=True)
class ChainCheck:
    """One chain: an organization's, or the platform's (None)."""

    organization_id: int | None
    # The chain's length: the place of its newest record.
    records: int
    # The seal of its newest record.
    head: str
    # The first place that does not verify, and why.
    broken_at: int | None = None
    problem: Problem | None = None

    @property
    def intact(self) -> bool:
        return self.problem is None

    @property
    def label(self) -> str:
        if self.organization_id is None:
            return "platform"
        return str(self.organization_id)


def verify_chains(db: Session) -> list[ChainCheck]:
    """Every chain that has records, the platform's first."""
    key = settings.audit_chain_key.get_secret_value().encode()
    records = db.execute(
        select(
            AuditLog.organization_id,
            AuditLog.chain_seq,
            AuditLog.chain_hash,
            AuditLog.event_type,
            AuditLog.user_id,
            AuditLog.target_user_id,
            AuditLog.email,
            AuditLog.ip_address,
            AuditLog.message,
            AuditLog.created_at,
        )
        .order_by(AuditLog.organization_id.asc().nulls_first(), AuditLog.chain_seq)
        .execution_options(yield_per=1000)
    )
    return [
        _verify_chain(key, organization_id, chain)
        for organization_id, chain in itertools.groupby(
            records, key=lambda record: record.organization_id
        )
    ]


def _verify_chain(
    key: bytes, organization_id: int | None, records: Iterable[Row]
) -> ChainCheck:
    previous, expected = GENESIS, 1
    broken_at: int | None = None
    problem: Problem | None = None
    for record in records:
        if problem is None:
            if record.chain_seq != expected:
                broken_at, problem = expected, "missing"
            elif record.chain_hash != seal(
                key,
                previous=previous,
                chain_seq=record.chain_seq,
                event_type=record.event_type.name,
                user_id=record.user_id,
                target_user_id=record.target_user_id,
                organization_id=organization_id,
                email=record.email,
                ip_address=record.ip_address,
                message=record.message,
                created_at=record.created_at,
            ):
                broken_at, problem = expected, "changed"
        previous, expected = record.chain_hash, record.chain_seq + 1
    return ChainCheck(organization_id, expected - 1, previous, broken_at, problem)


# Each chain's length at this process's last check.
_last_lengths: dict[int | None, int] = {}


def check_audit_chains(db: Session) -> list[ChainCheck]:
    """Verify every chain, compare its length with the last check's, write
    the results to the log and the metrics, and raise an alert for each
    break. Returns the checks."""
    checks = {check.organization_id: check for check in verify_chains(db)}
    for organization_id, length in _last_lengths.items():
        check = checks.get(organization_id, ChainCheck(organization_id, 0, GENESIS))
        if check.intact and check.records < length:
            checks[organization_id] = replace(
                check, broken_at=check.records + 1, problem="truncated"
            )
    _last_lengths.clear()
    _last_lengths.update(
        (organization_id, check.records) for organization_id, check in checks.items()
    )

    results = sorted(checks.values(), key=lambda check: check.organization_id or 0)
    for check in results:
        AUDIT_CHAIN_RECORDS.labels(chain=check.label).set(check.records)
        AUDIT_CHAIN_INTACT.labels(chain=check.label).set(1 if check.intact else 0)
        logger.log(
            logging.INFO if check.intact else logging.ERROR,
            "Audit chain checked",
            extra={
                "chain": check.label,
                "records": check.records,
                "head": check.head,
                "intact": check.intact,
                "problem": check.problem,
                "broken_at": check.broken_at,
            },
        )
        if not check.intact:
            alert_broken_chain(db, check)
    return results


def alert_broken_chain(db: Session, check: ChainCheck) -> SecurityEvent | None:
    """T1070: an audit chain that no longer verifies, as when someone who
    can change the database edits or deletes history to hide what they did.

    One alert per chain and first broken record: a later check that finds
    the same break raises none. The message names the chain and the record,
    never the record's contents.
    """
    if check.organization_id is None:
        place = "the platform"
    else:
        name = db.scalar(
            select(Organization.name).where(Organization.id == check.organization_id)
        )
        place = f"{name} (organization {check.organization_id})"
    message = (
        f"Audit history of {place} broken at record {check.broken_at}: {check.problem}"
    )

    db.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": ALERT_LOCK})
    raised = db.scalar(
        select(SecurityEvent.id)
        .where(
            SecurityEvent.event_type == SecurityEventType.AUDIT_CHAIN_BROKEN,
            SecurityEvent.message == message,
        )
        .limit(1)
    )
    if raised is not None:
        db.rollback()
        return None

    alert = SecurityEvent(
        event_type=SecurityEventType.AUDIT_CHAIN_BROKEN,
        severity=SecuritySeverity.INCIDENT,
        source=DETECTION_SOURCE,
        message=message,
        occurred_at=func.now(),
    )
    db.add(alert)
    db.commit()
    record_security_event(alert.event_type, alert.severity)
    return alert
