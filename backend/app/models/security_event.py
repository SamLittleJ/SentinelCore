import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class SecurityEventType(str, enum.Enum):
    USER_REGISTERED = "user_registered"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    ADMIN_ACCESS = "admin_access"
    
class SecuritySeverity(str, enum.Enum):
    INFO = "info"
    WARN = "warn"
    INCIDENT = "incident"
    
class SecurityEvent(Base):
    __tablename__ ="security_events"
    
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
    
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="backend")
    
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )