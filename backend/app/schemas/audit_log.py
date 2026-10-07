from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.audit_log import AuditEventType
from app.schemas.event_filters import EventFilters


class AuditLogRead(BaseModel):
    id: int
    event_type: AuditEventType
    user_id: int | None
    target_user_id: int | None
    email: str | None
    ip_address: str | None
    message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogFilters(EventFilters):
    event_type: list[AuditEventType] = []
