from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, require_role
from app.models.audit_log import AuditEventType
from app.models.user import User, UserRole
from app.schemas.pagination import Page
from app.schemas.security_event import AccountActivityFilters, SecurityEventRead
from app.schemas.user import (
    SessionsRevoked,
    UserFilters,
    UserRead,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.services.audit_service import create_audit_log
from app.services.security_event_service import list_user_activity
from app.services.user_service import (
    get_user_by_id,
    list_users,
    revoke_all_user_sessions,
    update_user_role,
    update_user_status,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


# Analysts read accounts to investigate; changing them stays with admins.
# Reads are recorded only in the audit log: viewing accounts is an audit fact,
# not a security signal, as for the event and log listings.
READ_ROLES = (UserRole.ADMIN, UserRole.OWNER, UserRole.SECURITY_ANALYST)


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.get("", response_model=Page[UserRead])
def read_users(
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[User, Depends(require_role(*READ_ROLES))],
    filters: Annotated[UserFilters, Query()],
) -> Page[UserRead]:
    users, next_cursor = list_users(db, filters)

    create_audit_log(
        db=db,
        ip_address=client_ip,
        user=current_user,
        event_type=AuditEventType.USERS_VIEWED,
        message=f"Listed users with {filters.describe()}",
    )

    return Page[UserRead].model_validate(
        {"items": users, "next_cursor": next_cursor},
        from_attributes=True,
    )


@router.get("/{user_id}", response_model=UserRead)
def read_user_by_id(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[User, Depends(require_role(*READ_ROLES))],
) -> User:
    target_user = _get_user_or_404(db, user_id)

    create_audit_log(
        db=db,
        ip_address=client_ip,
        user=current_user,
        target_user=target_user,
        event_type=AuditEventType.USERS_VIEWED,
        message=f"Viewed user details for user_id={target_user.id}",
    )

    return target_user


@router.get("/{user_id}/activity", response_model=Page[SecurityEventRead])
def read_user_activity(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[User, Depends(require_role(*READ_ROLES))],
    filters: Annotated[AccountActivityFilters, Query()],
) -> Page[SecurityEventRead]:
    """The security events about one account, the same set its owner sees in
    their own activity, with the operator details included."""
    target_user = _get_user_or_404(db, user_id)
    events, next_cursor = list_user_activity(db, target_user, filters)

    create_audit_log(
        db=db,
        ip_address=client_ip,
        user=current_user,
        target_user=target_user,
        event_type=AuditEventType.SECURITY_EVENTS_VIEWED,
        message=(
            f"Viewed activity of user_id={target_user.id} with {filters.describe()}"
        ),
    )

    return Page[SecurityEventRead].model_validate(
        {"items": events, "next_cursor": next_cursor},
        from_attributes=True,
    )


@router.patch("/{user_id}/role", response_model=UserRead)
def change_user_role(
    user_id: int,
    role_in: UserRoleUpdate,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.OWNER)),
    ],
) -> User:
    target_user = _get_user_or_404(db, user_id)

    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owners cannot change their own role",
        )

    if target_user.role == UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change the role of an owner",
        )

    if role_in.role == UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot promote a user to owner",
        )

    return update_user_role(
        db=db,
        ip_address=client_ip,
        user=target_user,
        new_role=role_in.role,
        actor=current_user,
    )


def _ensure_can_manage_account(
    actor: User,
    target: User,
    *,
    self_detail: str,
    owner_detail: str,
    admin_detail: str,
) -> None:
    """Account management hierarchy shared by status and session actions:
    no one acts on their own account or on an owner, and only an owner acts on
    an admin. Each action supplies its own error messages."""
    if target.id == actor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=self_detail)

    if target.role == UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=owner_detail)

    if actor.role == UserRole.ADMIN and target.role == UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=admin_detail)


@router.patch("/{user_id}/status", response_model=UserRead)
def change_user_status(
    user_id: int,
    status_in: UserStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN, UserRole.OWNER)),
    ],
) -> User:
    target_user = _get_user_or_404(db, user_id)

    _ensure_can_manage_account(
        current_user,
        target_user,
        self_detail="Users cannot change their own status",
        owner_detail="Cannot change the status of an owner",
        admin_detail="Only an owner can change the status of an admin",
    )

    return update_user_status(
        db=db,
        ip_address=client_ip,
        user=target_user,
        is_active=status_in.is_active,
        actor=current_user,
    )


@router.delete("/{user_id}/sessions", response_model=SessionsRevoked)
def revoke_user_sessions(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN, UserRole.OWNER)),
    ],
) -> SessionsRevoked:
    """Sign a user out everywhere, for example after a suspected compromise,
    without deactivating the account."""
    target_user = _get_user_or_404(db, user_id)

    _ensure_can_manage_account(
        current_user,
        target_user,
        self_detail="Use /auth/logout-all to revoke your own sessions",
        owner_detail="Cannot revoke the sessions of an owner",
        admin_detail="Only an owner can revoke the sessions of an admin",
    )

    revoked = revoke_all_user_sessions(
        db=db,
        user=target_user,
        actor=current_user,
        ip_address=client_ip,
    )
    return SessionsRevoked(revoked_sessions=revoked)
