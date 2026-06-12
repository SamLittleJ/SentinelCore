from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.audit_log import AuditEventType


class AuditLogRead(BaseModel):
    id: int
    event_type: AuditEventType
    user_id: int | None
    email: str | None
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
