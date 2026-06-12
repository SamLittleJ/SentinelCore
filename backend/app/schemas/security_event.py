from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.security_event import SecurityEventType, SecuritySeverity


class SecurityEventRead(BaseModel):
    id: int
    event_type: SecurityEventType
    severity: SecuritySeverity
    user_id: int | None
    email: str | None
    source: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
