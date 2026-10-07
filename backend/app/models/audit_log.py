from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


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


class AuditLog(Base):
    __tablename__ = "audit_logs"
    # Serves the newest-first listing and its cursor.
    __table_args__ = (Index("ix_audit_logs_created_at_id", "created_at", "id"),)

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
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
