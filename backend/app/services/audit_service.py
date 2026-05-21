from sqlalchemy.orm import Session

from app.models.audit_log import AuditEventType, AuditLog
from app.models.user import User


def create_audit_log(
    db: Session,
    event_type: AuditEventType,
    message: str,
    user: User | None = None,
    email: str | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        event_type=event_type,
        user_id=user.id if user else None,
        email=email if email else (user.email if user else None),
        message=message,
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log