"""The audit history, and the seal on each of its records.

Each organization's records form a chain, and the platform's (no
organization) one more: every record carries its place in its chain and a
seal over its fields and the seal before it (core/audit_seal.py). The seal is
set here, on flush, for every new record whichever code adds it, so no writer
can forget it. services/audit_chain_service.py checks the chains.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    select,
    text,
)
from sqlalchemy.orm import Mapped, Session, UOWTransaction, mapped_column

from app.core.audit_seal import GENESIS, seal
from app.core.config import settings
from app.core.database import Base, database_now

# The first key of each chain's advisory lock ("AUDT"); the second is the
# organization's id, or 0 for the platform, since ids start at 1.
CHAIN_LOCK = 0x41554454


class AuditEventType(StrEnum):
    USER_REGISTERED = "user_registered"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    ADMIN_ENDPOINT_ACCESSED = "admin_endpoint_accessed"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    LOGIN_LOCKED = "login_locked"
    LOGIN_BLOCKED = "login_blocked"
    AUDIT_LOGS_VIEWED = "audit_logs_viewed"
    SECURITY_EVENTS_VIEWED = "security_events_viewed"
    SESSION_REVOKED = "session_revoked"
    ALL_SESSIONS_REVOKED = "all_sessions_revoked"
    OTHER_SESSIONS_REVOKED = "other_sessions_revoked"
    USERS_VIEWED = "users_viewed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    API_KEYS_VIEWED = "api_keys_viewed"
    INVITATION_CREATED = "invitation_created"
    INVITATION_REVOKED = "invitation_revoked"
    INVITATIONS_VIEWED = "invitations_viewed"
    ORGANIZATION_CREATED = "organization_created"
    ORGANIZATION_RENAMED = "organization_renamed"
    ORGANIZATION_SUSPENDED = "organization_suspended"
    ORGANIZATION_REACTIVATED = "organization_reactivated"
    ORGANIZATIONS_VIEWED = "organizations_viewed"
    LOGIN_ADDRESS_LIMITED = "login_address_limited"


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        # Serves the newest-first listing and its cursor.
        Index("ix_audit_logs_created_at_id", "created_at", "id"),
        # One record per place in each chain; the platform's chain, whose
        # organization is empty, too. Serves the lookup of a chain's head.
        UniqueConstraint(
            "organization_id",
            "chain_seq",
            name="uq_audit_logs_chain",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, name="audit_event_types"),
        nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    # The account an action was taken on, as in SecurityEvent.target_user_id.
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    # The organization the record belongs to; empty for the platform's own,
    # such as the owner signing in. See services/tenancy.py.
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    # The record's place in its chain, from 1, and its seal.
    chain_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    chain_hash: Mapped[str] = mapped_column(String(64), nullable=False)


def in_chain(organization_id: int | None):
    """The condition for the records of `organization_id`'s chain."""
    if organization_id is None:
        return AuditLog.organization_id.is_(None)
    return AuditLog.organization_id == organization_id


@event.listens_for(Session, "before_flush")
def _seal_new_records(
    session: Session, flush_context: UOWTransaction, instances: object
) -> None:
    """Give each new record the next place in its chain and its seal.

    The chain's advisory lock is held until the transaction ends, so a
    concurrent writer waits and then reads the head this one wrote. The locks
    are taken in one order, so two writers to the same chains cannot deadlock.
    """
    chains: dict[int | None, list[AuditLog]] = {}
    for record in session.new:
        if isinstance(record, AuditLog):
            chains.setdefault(record.organization_id, []).append(record)
    if not chains:
        return

    key = settings.audit_chain_key.get_secret_value().encode()
    now = None
    for organization_id in sorted(chains, key=lambda org: org or 0):
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock, :chain)"),
            {"lock": CHAIN_LOCK, "chain": organization_id or 0},
        )
        head = session.execute(
            select(AuditLog.chain_seq, AuditLog.chain_hash)
            .where(in_chain(organization_id))
            .order_by(AuditLog.chain_seq.desc())
            .limit(1)
        ).one_or_none()
        chain_seq, previous = (
            (head.chain_seq, head.chain_hash) if head else (0, GENESIS)
        )
        for record in chains[organization_id]:
            if record.created_at is None:
                # The time the database would have stamped, known before
                # the insert so that the seal covers it.
                now = now or database_now(session)
                record.created_at = now
            chain_seq += 1
            record.chain_seq = chain_seq
            record.chain_hash = previous = seal(
                key,
                previous=previous,
                chain_seq=chain_seq,
                event_type=record.event_type.name,
                user_id=record.user_id,
                target_user_id=record.target_user_id,
                organization_id=record.organization_id,
                email=record.email,
                ip_address=record.ip_address,
                message=record.message,
                created_at=record.created_at,
            )
