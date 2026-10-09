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
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    # Alerts raised by the detection rules (services/detection_service.py).
    # An event type, not a password.
    PASSWORD_SPRAY_DETECTED = "password_spray_detected"  # nosec B105
    DORMANT_ACCOUNT_LOGIN = "dormant_account_login"
    PRIVILEGED_ROLE_GRANTED = "privileged_role_granted"
    UNFAMILIAR_SIGN_IN = "unfamiliar_sign_in"


# The sources this application stamps on its own events. Ingested events
# carry their API key's source, which may not be one of these.
BACKEND_SOURCE = "backend"
DETECTION_SOURCE = "detection"
RESERVED_SOURCES = frozenset({BACKEND_SOURCE, DETECTION_SOURCE})

# The MITRE ATT&CK technique each detection stands for
# (https://attack.mitre.org/techniques/).
MITRE_TECHNIQUES: dict[SecurityEventType, str] = {
    # Brute Force: Password Guessing
    SecurityEventType.BRUTE_FORCE_DETECTED: "T1110.001",
    # Brute Force: Password Spraying
    SecurityEventType.PASSWORD_SPRAY_DETECTED: "T1110.003",
    # Valid Accounts
    SecurityEventType.DORMANT_ACCOUNT_LOGIN: "T1078",
    SecurityEventType.UNFAMILIAR_SIGN_IN: "T1078",
    # Account Manipulation
    SecurityEventType.PRIVILEGED_ROLE_GRANTED: "T1098",
}


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
        # Serves the newest-first listings and their cursor.
        Index("ix_security_events_created_at_id", "created_at", "id"),
        # Serves the per-address lookups of password spray detection.
        Index(
            "ix_security_events_ip_type_created",
            "ip_address",
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

    # The account an action was taken on, when it differs from the actor in
    # user_id; e.g. the user whose role an owner changed.
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # The client's User-Agent header, for sign-ins.
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # "backend" for this application's own events, "detection" for alerts, or
    # the source of the API key that sent an ingested event.
    source: Mapped[str] = mapped_column(
        String(100), nullable=False, default=BACKEND_SOURCE
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # For alerts, the time of the event that raised them, while created_at is
    # when they were raised: the two differ for events reported late through
    # ingestion. Empty for other events, whose created_at is their own time.
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def mitre_technique(self) -> str | None:
        """The ATT&CK technique this event detects, if it is a detection."""
        return MITRE_TECHNIQUES.get(self.event_type)
