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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SecurityEventType(StrEnum):
    USER_REGISTERED = "user_registered"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    ADMIN_ACCESS = "admin_access"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    BRUTE_FORCE_DETECTED = "brute_force_detected"
    LOGIN_BLOCKED = "login_blocked"
    USER_SESSIONS_REVOKED = "user_sessions_revoked"


class SecuritySeverity(StrEnum):
    INFO = "info"
    WARN = "warn"
    INCIDENT = "incident"


class SecurityEvent(Base):
    __tablename__ = "security_events"
    # Serves the per-email login history lookups used by brute-force detection.
    __table_args__ = (
        Index(
            "ix_security_events_email_type_created",
            "email",
            "event_type",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    event_type: Mapped[SecurityEventType] = mapped_column(
        Enum(SecurityEventType, name="security_event_types"),
        nullable=False,
        index=True,
    )

    severity: Mapped[SecuritySeverity] = mapped_column(
        Enum(SecuritySeverity, name="security_severities"),
        nullable=False,
        index=True,
    )

    # Indexed for the per-account activity view and the user_id filter.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    source: Mapped[str] = mapped_column(String(100), nullable=False, default="backend")

    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
