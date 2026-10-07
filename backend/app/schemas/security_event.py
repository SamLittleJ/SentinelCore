from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.security_event import SecurityEventType, SecuritySeverity
from app.schemas.event_filters import EventFilters, EventPageFilters


class SecurityEventRead(BaseModel):
    id: int
    event_type: SecurityEventType
    severity: SecuritySeverity
    user_id: int | None
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
    """

    id: int
    event_type: SecurityEventType
    severity: SecuritySeverity
    ip_address: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MyActivityFilters(EventPageFilters):
    event_type: list[SecurityEventType] = []
    severity: list[SecuritySeverity] = []
