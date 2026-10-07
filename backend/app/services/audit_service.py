from sqlalchemy.orm import Session

from app.models.audit_log import AuditEventType, AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogFilters
from app.services.event_query import event_filter_conditions, fetch_event_page


def create_audit_log(
    db: Session,
    event_type: AuditEventType,
    message: str,
    user: User | None = None,
    email: str | None = None,
    ip_address: str | None = None,
    target_user: User | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        event_type=event_type,
        user_id=user.id if user else None,
        target_user_id=target_user.id if target_user else None,
        email=email if email else (user.email if user else None),
        ip_address=ip_address,
        message=message,
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log


def list_audit_logs(
    db: Session,
    filters: AuditLogFilters,
) -> tuple[list[AuditLog], int | None]:
    conditions = event_filter_conditions(AuditLog, filters)
    if filters.event_type:
        conditions.append(AuditLog.event_type.in_(filters.event_type))

    return fetch_event_page(db, AuditLog, filters, *conditions)
