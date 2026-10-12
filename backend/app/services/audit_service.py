from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models.audit_log import AuditEventType, AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogFilters
from app.services.event_query import event_filter_conditions, fetch_event_page
from app.services.tenancy import Scope, organization_of


def create_audit_log(
    db: Session,
    event_type: AuditEventType,
    message: str,
    user: User | None = None,
    email: str | None = None,
    ip_address: str | None = None,
    target_user: User | None = None,
    organization_id: int | None = None,
) -> AuditLog:
    """Record `event_type`. The organization is `organization_id` when the
    record is about something an organization owns, otherwise the one
    services/tenancy.py works out."""
    audit_log = AuditLog(
        event_type=event_type,
        user_id=user.id if user else None,
        target_user_id=target_user.id if target_user else None,
        organization_id=(
            organization_id
            if organization_id is not None
            else organization_of(db, user, target_user, email)
        ),
        email=email if email else (user.email if user else None),
        ip_address=ip_address,
        message=message,
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log


def audit_read(
    db: Session,
    event_type: AuditEventType,
    message: str,
    user: User,
    scope: Scope,
    shown: Iterable[int | None],
    ip_address: str | None = None,
) -> None:
    """Record that `user` listed records of the organizations in `shown`.

    A read inside one organization is recorded there. The owner's read of
    everything is recorded in each organization whose records it returned,
    so every organization sees when the owner saw its data, and on the
    platform when it returned the platform's own records, or none at all.
    """
    if scope.everything:
        organizations = set(shown) or {None}
    else:
        organizations = {scope.organization_id}
    db.add_all(
        AuditLog(
            event_type=event_type,
            user_id=user.id,
            organization_id=organization_id,
            email=user.email,
            ip_address=ip_address,
            message=message,
        )
        # The platform's record first, then by organization.
        for organization_id in sorted(
            organizations, key=lambda org: (org is not None, org or 0)
        )
    )
    db.commit()


def list_audit_logs(
    db: Session,
    filters: AuditLogFilters,
    scope: Scope,
) -> tuple[list[AuditLog], int | None]:
    conditions = event_filter_conditions(AuditLog, filters)
    conditions += scope.conditions(AuditLog.organization_id)
    if filters.event_type:
        conditions.append(AuditLog.event_type.in_(filters.event_type))

    return fetch_event_page(db, AuditLog, filters, *conditions)
