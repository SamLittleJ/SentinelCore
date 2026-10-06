from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.security_event import SecurityEventType, SecuritySeverity
from app.schemas.event_filters import EventFilters


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
