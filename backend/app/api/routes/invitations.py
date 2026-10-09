from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, require_role
from app.models.audit_log import AuditEventType
from app.models.invitation import Invitation
from app.models.user import User, UserRole
from app.schemas.invitation import (
    InvitationAccept,
    InvitationCreate,
    InvitationCreated,
    InvitationLookup,
    InvitationPreview,
    InvitationRead,
)
from app.schemas.user import UserRead
from app.services.audit_service import create_audit_log
from app.services.invitation_service import (
    accept_invitation,
    create_invitation,
    find_open_invitation,
    get_invitation,
    list_invitations,
    may_invite,
    revoke_invitation,
)
from app.services.user_service import get_user_by_email

router = APIRouter(prefix="/admin/invitations", tags=["invitations"])
# For the person invited, who has no account yet.
public_router = APIRouter(prefix="/auth/invitations", tags=["invitations"])

# Analysts see who is about to join, as they see every account; admins and
# the owner invite.
READ_ROLES = (UserRole.ADMIN, UserRole.OWNER, UserRole.SECURITY_ANALYST)
INVITE_ROLES = (UserRole.ADMIN, UserRole.OWNER)

ROLE_NOT_GRANTABLE = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Only the owner invites admins, and nobody invites an owner",
)
# Unknown, wrong, used, revoked or expired: the same answer for each, so a
# token cannot be probed for which of these it is.
INVITATION_NOT_VALID = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="This invitation is not valid. Ask for a new one.",
)


def _get_invitation_or_404(db: Session, invitation_id: int) -> Invitation:
    invitation = get_invitation(db, invitation_id)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )
    return invitation


@router.get("", response_model=list[InvitationRead])
def read_invitations(
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[User, Depends(require_role(*READ_ROLES))],
) -> list[Invitation]:
    invitations = list_invitations(db)
    create_audit_log(
        db=db,
        event_type=AuditEventType.INVITATIONS_VIEWED,
        user=current_user,
        ip_address=client_ip,
        message="Listed invitations",
    )
    return invitations


@router.post("", response_model=InvitationCreated, status_code=status.HTTP_201_CREATED)
def invite(
    invitation_in: InvitationCreate,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[User, Depends(require_role(*INVITE_ROLES))],
) -> InvitationCreated:
    """Invite someone. The response holds the token for the link, which is
    not shown again."""
    if not may_invite(current_user, invitation_in.role):
        raise ROLE_NOT_GRANTABLE
    # The caller is an operator who sees every account, so this is no oracle.
    if get_user_by_email(db, invitation_in.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    try:
        invitation, token = create_invitation(
            db, invitation_in, current_user, client_ip
        )
    except IntegrityError as exc:
        # Another invitation for the email was created at the same moment.
        if not isinstance(exc.orig, UniqueViolation):
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another invitation for this email was just created",
        ) from exc
    return InvitationCreated(
        invitation=InvitationRead.model_validate(invitation), token=token
    )


@router.post("/{invitation_id}/revoke", response_model=InvitationRead)
def revoke(
    invitation_id: int,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[User, Depends(require_role(*INVITE_ROLES))],
) -> Invitation:
    """Stop an invitation from working. Revoking a used or revoked one
    changes nothing."""
    invitation = _get_invitation_or_404(db, invitation_id)
    if not may_invite(current_user, invitation.role):
        raise ROLE_NOT_GRANTABLE
    return revoke_invitation(db, invitation, current_user, client_ip)


@public_router.post("/preview", response_model=InvitationPreview)
def preview_invitation(
    lookup: InvitationLookup,
    db: Annotated[Session, Depends(get_db)],
) -> Invitation:
    """The email and role an invitation offers, before it is accepted."""
    invitation = find_open_invitation(db, lookup.token)
    if invitation is None:
        raise INVITATION_NOT_VALID
    return invitation


@public_router.post(
    "/accept", response_model=UserRead, status_code=status.HTTP_201_CREATED
)
def accept(
    acceptance: InvitationAccept,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> User:
    """Create the invited account with the username and password its owner
    chose. It does not sign them in: they sign in next, as every time."""
    invitation = find_open_invitation(db, acceptance.token, for_update=True)
    if invitation is None:
        db.rollback()  # Releases the lock, if a row was found.
        raise INVITATION_NOT_VALID
    if get_user_by_email(db, invitation.email) is not None:
        # The email got an account some other way since, so the invitation
        # can no longer be used.
        db.rollback()
        raise INVITATION_NOT_VALID
    try:
        return accept_invitation(
            db, invitation, acceptance.username, acceptance.password, client_ip
        )
    except IntegrityError as exc:
        if not isinstance(exc.orig, UniqueViolation):
            raise
        # An account took the email between the check above and now.
        if exc.orig.diag.constraint_name == "ix_users_email":
            raise INVITATION_NOT_VALID from exc
        # Only holders of a valid invitation learn that a username is taken;
        # sign-in is by email, so a username alone opens nothing.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        ) from exc
