"""Invitations: the only way an account joins the organization after the
first owner.

An admin or the owner invites an email with a role and hands the link over
themselves; the person invited opens it and picks a username and password, so
nobody else ever knows that password. A token reads `sci_<prefix>_<secret>`
(core/secret_tokens.py) and works once, until it expires.

Who may offer a role is checked again when the invitation is accepted: an
invitation is worth only what its author may still grant.
"""

from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import database_now
from app.core.metrics import record_security_event
from app.core.secret_tokens import issue_token, secret_matches, split_token
from app.models.audit_log import AuditEventType, AuditLog
from app.models.invitation import Invitation
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole
from app.schemas.invitation import InvitationCreate
from app.schemas.user import UserCreate
from app.services.user_service import commit_account_created, stage_user

INVITATION_SCHEME = "sci"

# Admins grow the organization with everyday roles; only the owner adds
# another admin. Nobody invites an owner.
GRANTABLE_ROLES: dict[UserRole, frozenset[UserRole]] = {
    UserRole.ADMIN: frozenset({UserRole.USER, UserRole.SECURITY_ANALYST}),
    UserRole.OWNER: frozenset(
        {UserRole.USER, UserRole.SECURITY_ANALYST, UserRole.ADMIN}
    ),
}


def may_invite(actor: User, role: UserRole) -> bool:
    return actor.is_active and role in GRANTABLE_ROLES.get(actor.role, frozenset())


def _role_name(actor: User) -> str:
    return actor.role.value.replace("_", " ").capitalize()


def _commit_invitation_change(
    db: Session,
    actor: User,
    audit_event_type: AuditEventType,
    security_event_type: SecurityEventType,
    message: str,
    ip_address: str | None,
) -> None:
    """Commit a staged change to an invitation together with its audit and
    security events, so either all three are stored or none are."""
    db.add_all(
        [
            AuditLog(
                event_type=audit_event_type,
                user_id=actor.id,
                email=actor.email,
                ip_address=ip_address,
                message=message,
            ),
            SecurityEvent(
                event_type=security_event_type,
                severity=SecuritySeverity.INFO,
                user_id=actor.id,
                email=actor.email,
                ip_address=ip_address,
                source="backend",
                message=message,
            ),
        ]
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    record_security_event(security_event_type, SecuritySeverity.INFO)


def create_invitation(
    db: Session,
    data: InvitationCreate,
    actor: User,
    ip_address: str | None = None,
) -> tuple[Invitation, str]:
    """Invite `data.email` with `data.role`, replacing any open invitation
    for that email, and return it with its full token, which is never
    available again. The caller checks `may_invite` and that no account has
    the email."""
    now = database_now(db)
    replaced = db.scalars(
        update(Invitation)
        .where(
            Invitation.email == data.email,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
        .values(revoked_at=now)
        .returning(Invitation.id)
    ).all()
    token = issue_token(INVITATION_SCHEME)
    invitation = Invitation(
        prefix=token.prefix,
        secret_hash=token.secret_hash,
        email=data.email,
        role=data.role,
        created_by_id=actor.id,
        expires_at=now + timedelta(hours=settings.invitation_expire_hours),
    )
    db.add(invitation)
    message = (
        f"{_role_name(actor)} invited {data.email} as {data.role.value} "
        f"(invitation {token.prefix}), valid for "
        f"{settings.invitation_expire_hours} hours"
    )
    if replaced:
        message += f"; replaced {len(replaced)} earlier invitation(s)"
    _commit_invitation_change(
        db,
        actor,
        AuditEventType.INVITATION_CREATED,
        SecurityEventType.INVITATION_CREATED,
        message,
        ip_address,
    )
    db.refresh(invitation)
    return invitation, token.value


def list_invitations(db: Session) -> list[Invitation]:
    return list(db.scalars(select(Invitation).order_by(Invitation.id.desc())).all())


def get_invitation(db: Session, invitation_id: int) -> Invitation | None:
    return db.get(Invitation, invitation_id)


def revoke_invitation(
    db: Session,
    invitation: Invitation,
    actor: User,
    ip_address: str | None = None,
) -> Invitation:
    if invitation.accepted_at is not None or invitation.revoked_at is not None:
        return invitation  # No change needed: used, or already revoked

    invitation.revoked_at = database_now(db)
    _commit_invitation_change(
        db,
        actor,
        AuditEventType.INVITATION_REVOKED,
        SecurityEventType.INVITATION_REVOKED,
        (
            f"{_role_name(actor)} revoked invitation {invitation.prefix} "
            f"for {invitation.email}"
        ),
        ip_address,
    )
    db.refresh(invitation)
    return invitation


def find_open_invitation(
    db: Session, presented: str, *, for_update: bool = False
) -> Invitation | None:
    """The invitation `presented` stands for, if it can still be accepted:
    known, matching, neither used, revoked nor expired, and its author may
    still grant its role. Every failure looks the same to the caller.

    `for_update` locks the row until the transaction ends, so two requests
    with the same token cannot both use it."""
    parts = split_token(INVITATION_SCHEME, presented)
    if parts is None:
        return None
    prefix, secret = parts

    statement = select(Invitation).where(Invitation.prefix == prefix)
    if for_update:
        statement = statement.with_for_update()
    invitation = db.scalar(statement)
    matches = secret_matches(secret, invitation.secret_hash if invitation else None)
    if invitation is None or not matches:
        return None
    if (
        invitation.accepted_at is not None
        or invitation.revoked_at is not None
        or invitation.expires_at <= database_now(db)
    ):
        return None
    author = db.get(User, invitation.created_by_id)
    if author is None or not may_invite(author, invitation.role):
        return None
    return invitation


def accept_invitation(
    db: Session,
    invitation: Invitation,
    username: str,
    password: str,
    ip_address: str | None = None,
) -> User:
    """Create the account `invitation` offers, and use the invitation up.

    `invitation` comes from `find_open_invitation(..., for_update=True)` in
    the same transaction. A taken username raises IntegrityError, after a
    rollback that also releases the invitation.
    """
    user_in = UserCreate(username=username, email=invitation.email, password=password)
    try:
        user = stage_user(db, user_in, invitation.role)
    except Exception:
        db.rollback()
        raise
    invitation.accepted_at = database_now(db)
    invitation.accepted_user_id = user.id
    return commit_account_created(
        db,
        user,
        (
            f"Account created for {user.email} with the {user.role.value} role, "
            f"from invitation {invitation.prefix} by "
            f"user_id={invitation.created_by_id}"
        ),
        ip_address,
    )
