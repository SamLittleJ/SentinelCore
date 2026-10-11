from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, require_role
from app.models.audit_log import AuditEventType
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationRead,
    OrganizationRename,
)
from app.services.audit_service import create_audit_log
from app.services.organization_service import (
    create_organization,
    get_organization,
    list_organizations,
    reactivate_organization,
    rename_organization,
    suspend_organization,
    to_read,
)

# The platform owner's alone: organizations are the platform's tenants.
router = APIRouter(prefix="/admin/organizations", tags=["organizations"])
OwnerOnly = Annotated[User, Depends(require_role(UserRole.OWNER))]

NAME_TAKEN = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="An organization with this name or slug already exists",
)


def get_organization_or_404(db: Session, organization_id: int) -> Organization:
    organization = get_organization(db, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return organization


def require_open_organization(db: Session, organization_id: int) -> Organization:
    """The organization something new is made in, for the owner: it must
    exist and not be suspended."""
    organization = get_organization_or_404(db, organization_id)
    if organization.suspended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The organization is suspended",
        )
    return organization


@router.get("", response_model=list[OrganizationRead])
def read_organizations(
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: OwnerOnly,
) -> list[OrganizationRead]:
    organizations = list_organizations(db)
    create_audit_log(
        db=db,
        event_type=AuditEventType.ORGANIZATIONS_VIEWED,
        user=current_user,
        ip_address=client_ip,
        message="Listed organizations",
    )
    return organizations


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def add_organization(
    organization_in: OrganizationCreate,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: OwnerOnly,
) -> OrganizationRead:
    try:
        organization = create_organization(db, organization_in, current_user, client_ip)
    except IntegrityError as exc:
        if not isinstance(exc.orig, UniqueViolation):
            raise
        raise NAME_TAKEN from exc
    return to_read(db, organization)


@router.patch("/{organization_id}", response_model=OrganizationRead)
def rename(
    organization_id: int,
    rename_in: OrganizationRename,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: OwnerOnly,
) -> OrganizationRead:
    organization = get_organization_or_404(db, organization_id)
    try:
        rename_organization(db, organization, rename_in, current_user, client_ip)
    except IntegrityError as exc:
        if not isinstance(exc.orig, UniqueViolation):
            raise
        raise NAME_TAKEN from exc
    return to_read(db, organization)


@router.post("/{organization_id}/suspend", response_model=OrganizationRead)
def suspend(
    organization_id: int,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: OwnerOnly,
) -> OrganizationRead:
    """Stop the organization's members from signing in and its keys from
    sending events, closing every session now. Its data stays."""
    organization = get_organization_or_404(db, organization_id)
    suspend_organization(db, organization, current_user, client_ip)
    return to_read(db, organization)


@router.post("/{organization_id}/reactivate", response_model=OrganizationRead)
def reactivate(
    organization_id: int,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: OwnerOnly,
) -> OrganizationRead:
    organization = get_organization_or_404(db, organization_id)
    reactivate_organization(db, organization, current_user, client_ip)
    return to_read(db, organization)
