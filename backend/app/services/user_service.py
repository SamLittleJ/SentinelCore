from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.metrics import record_security_event
from app.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserFilters
from app.services.pagination import fetch_page
from app.services.session_service import stage_revoke_all_sessions


def get_user_by_email(db: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return db.scalar(statement)


def get_user_by_username(db: Session, username: str) -> User | None:
    statement = select(User).where(User.username == username)
    return db.scalar(statement)


def create_user(db: Session, user_in: UserCreate) -> User:
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        role=UserRole.USER,
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


def list_users(
    db: Session,
    filters: UserFilters,
) -> tuple[list[User], int | None]:
    """One page of users, newest first, and the cursor for the next."""
    conditions: list[ColumnElement[bool]] = []
    if filters.q is not None:
        # autoescape keeps % and _ in the search text literal.
        conditions.append(
            or_(
                User.email.contains(filters.q, autoescape=True),
                User.username.contains(filters.q, autoescape=True),
            )
        )
    if filters.role:
        conditions.append(User.role.in_(filters.role))
    if filters.is_active is not None:
        conditions.append(User.is_active.is_(filters.is_active))

    return fetch_page(db, User, filters, *conditions)


def get_user_by_id(db: Session, user_id: int) -> User | None:
    statement = select(User).where(User.id == user_id)
    return db.scalar(statement)


def _commit_user_change(
    db: Session,
    user: User,
    actor: User,
    audit_event_type: AuditEventType,
    security_event_type: SecurityEventType,
    message: str,
    ip_address: str | None,
) -> User:
    """Commit a staged change to `user` together with its audit and security
    events, so either all three are stored or none are. The events name
    `actor` as their user and `user` as their target."""
    db.add_all(
        [
            AuditLog(
                event_type=audit_event_type,
                user_id=actor.id,
                target_user_id=user.id,
                email=actor.email,
                ip_address=ip_address,
                message=message,
            ),
            SecurityEvent(
                event_type=security_event_type,
                severity=SecuritySeverity.INFO,
                user_id=actor.id,
                target_user_id=user.id,
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
    db.refresh(user)
    return user


def update_user_role(
    db: Session,
    user: User,
    new_role: UserRole,
    actor: User,
    ip_address: str | None = None,
) -> User:
    previous_role = user.role

    if previous_role == new_role:
        return user  # No change needed

    message = (
        f"Owner changed role for user_id={user.id}"
        f" from {previous_role.value} to {new_role.value}"
    )

    user.role = new_role

    return _commit_user_change(
        db=db,
        user=user,
        actor=actor,
        audit_event_type=AuditEventType.USER_ROLE_CHANGED,
        security_event_type=SecurityEventType.USER_ROLE_CHANGED,
        message=message,
        ip_address=ip_address,
    )


def update_user_status(
    db: Session,
    user: User,
    is_active: bool,
    actor: User,
    ip_address: str | None = None,
) -> User:
    if user.is_active == is_active:
        return user  # No change needed

    action = "activated" if is_active else "deactivated"
    message = f"{actor.role.value.capitalize()} {action} user_id={user.id}"

    user.is_active = is_active
    if not is_active:
        # Committed together with the status change and its events.
        stage_revoke_all_sessions(db, user.id)

    return _commit_user_change(
        db=db,
        user=user,
        actor=actor,
        audit_event_type=(
            AuditEventType.USER_ACTIVATED
            if is_active
            else AuditEventType.USER_DEACTIVATED
        ),
        security_event_type=(
            SecurityEventType.USER_ACTIVATED
            if is_active
            else SecurityEventType.USER_DEACTIVATED
        ),
        message=message,
        ip_address=ip_address,
    )


def revoke_all_user_sessions(
    db: Session,
    user: User,
    actor: User,
    ip_address: str | None = None,
) -> int:
    """Revoke every active session of `user` on behalf of `actor`, together
    with the audit and security events. Returns the number revoked."""
    revoked = stage_revoke_all_sessions(db, user.id)
    message = (
        f"{actor.role.value.capitalize()} revoked {revoked} session(s) "
        f"for user_id={user.id}"
    )

    _commit_user_change(
        db=db,
        user=user,
        actor=actor,
        audit_event_type=AuditEventType.ALL_SESSIONS_REVOKED,
        security_event_type=SecurityEventType.USER_SESSIONS_REVOKED,
        message=message,
        ip_address=ip_address,
    )
    return revoked
