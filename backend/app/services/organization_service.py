"""Organizations: created, renamed, suspended and reactivated by the
platform owner only. None is ever deleted, so its audit trail stays.

Suspending one closes every member's sessions; while it lasts, members are
refused at sign-in as deactivated accounts are, and its API keys as unknown
keys are.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import database_now
from app.core.metrics import record_security_event
from app.models.audit_log import AuditEventType, AuditLog
from app.models.organization import Organization
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationRead,
    OrganizationRename,
)
from app.services.session_service import stage_revoke_all_sessions


def _commit_organization_change(
    db: Session,
    organization: Organization,
    actor: User,
    audit_event_type: AuditEventType,
    security_event_type: SecurityEventType,
    message: str,
    ip_address: str | None,
    severity: SecuritySeverity = SecuritySeverity.INFO,
) -> None:
    """Commit a staged change to `organization` with its audit and security
    events, which belong to it, so its members see what the platform did."""
    try:
        db.flush()  # Gives a new organization its id; a taken name fails here.
    except Exception:
        db.rollback()
        raise
    db.add_all(
        [
            AuditLog(
                event_type=audit_event_type,
                user_id=actor.id,
                organization_id=organization.id,
                email=actor.email,
                ip_address=ip_address,
                message=message,
            ),
            SecurityEvent(
                event_type=security_event_type,
                severity=severity,
                user_id=actor.id,
                organization_id=organization.id,
                email=actor.email,
                ip_address=ip_address,
                message=message,
            ),
        ]
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    record_security_event(security_event_type, severity)
    db.refresh(organization)


def to_read(db: Session, organization: Organization) -> OrganizationRead:
    members = db.scalar(
        select(func.count(User.id)).where(User.organization_id == organization.id)
    )
    return OrganizationRead(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        created_at=organization.created_at,
        suspended_at=organization.suspended_at,
        members=members or 0,
    )


def list_organizations(db: Session) -> list[OrganizationRead]:
    members = (
        select(User.organization_id, func.count(User.id).label("members"))
        .group_by(User.organization_id)
        .subquery()
    )
    rows = db.execute(
        select(Organization, func.coalesce(members.c.members, 0))
        .outerjoin(members, members.c.organization_id == Organization.id)
        .order_by(Organization.name)
    ).all()
    return [
        OrganizationRead(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            created_at=organization.created_at,
            suspended_at=organization.suspended_at,
            members=count,
        )
        for organization, count in rows
    ]


def get_organization(db: Session, organization_id: int) -> Organization | None:
    return db.get(Organization, organization_id)


def is_suspended(db: Session, organization_id: int | None) -> bool:
    """Whether `organization_id` names a suspended organization. The
    platform, with no organization, is never suspended."""
    if organization_id is None:
        return False
    organization = db.get(Organization, organization_id)
    return organization is not None and organization.suspended_at is not None


def create_organization(
    db: Session,
    data: OrganizationCreate,
    actor: User,
    ip_address: str | None = None,
) -> Organization:
    """Create an organization. A name or slug already taken raises
    IntegrityError, from the unique indexes."""
    organization = Organization(name=data.name, slug=data.slug)
    db.add(organization)
    _commit_organization_change(
        db,
        organization,
        actor,
        AuditEventType.ORGANIZATION_CREATED,
        SecurityEventType.ORGANIZATION_CREATED,
        f"Owner created organization {data.slug} ({data.name})",
        ip_address,
    )
    return organization


def rename_organization(
    db: Session,
    organization: Organization,
    data: OrganizationRename,
    actor: User,
    ip_address: str | None = None,
) -> Organization:
    if organization.name == data.name:
        return organization  # No change needed
    old_name = organization.name
    organization.name = data.name
    _commit_organization_change(
        db,
        organization,
        actor,
        AuditEventType.ORGANIZATION_RENAMED,
        SecurityEventType.ORGANIZATION_RENAMED,
        f"Owner renamed organization {organization.slug} from {old_name} "
        f"to {data.name}",
        ip_address,
    )
    return organization


def suspend_organization(
    db: Session,
    organization: Organization,
    actor: User,
    ip_address: str | None = None,
) -> Organization:
    """Suspend `organization` and close every member's sessions at once."""
    if organization.suspended_at is not None:
        return organization  # No change needed
    organization.suspended_at = database_now(db)
    member_ids = db.scalars(
        select(User.id).where(User.organization_id == organization.id)
    ).all()
    revoked = sum(stage_revoke_all_sessions(db, member_id) for member_id in member_ids)
    _commit_organization_change(
        db,
        organization,
        actor,
        AuditEventType.ORGANIZATION_SUSPENDED,
        SecurityEventType.ORGANIZATION_SUSPENDED,
        f"Owner suspended organization {organization.slug}; closed {revoked} "
        "session(s)",
        ip_address,
        severity=SecuritySeverity.WARN,
    )
    return organization


def reactivate_organization(
    db: Session,
    organization: Organization,
    actor: User,
    ip_address: str | None = None,
) -> Organization:
    if organization.suspended_at is None:
        return organization  # No change needed
    organization.suspended_at = None
    _commit_organization_change(
        db,
        organization,
        actor,
        AuditEventType.ORGANIZATION_REACTIVATED,
        SecurityEventType.ORGANIZATION_REACTIVATED,
        f"Owner reactivated organization {organization.slug}",
        ip_address,
    )
    return organization
