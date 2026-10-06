from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole
from app.schemas.user import UserCreate


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
    limit: int = 50,
    offset: int = 0,
) -> list[User]:
    statement = select(User).order_by(User.id).offset(offset).limit(limit)
    return list(db.scalars(statement).all())


def get_user_by_id(db: Session, user_id: int) -> User | None:
    statement = select(User).where(User.id == user_id)
    return db.scalar(statement)


def update_user_role(
    db: Session,
    user: User,
    new_role: UserRole,
    actor: User,
) -> User:
    previous_role = user.role

    if previous_role == new_role:
        return user  # No change needed

    message = (
        f"Owner changed role for user_id={user.id}"
        f" from {previous_role.value} to {new_role.value}"
    )

    user.role = new_role

    db.add_all(
        [
            AuditLog(
                event_type=AuditEventType.ADMIN_ENDPOINT_ACCESSED,
                user_id=actor.id,
                email=actor.email,
                message=message,
            ),
            SecurityEvent(
                event_type=SecurityEventType.ADMIN_ACCESS,
                severity=SecuritySeverity.INFO,
                user_id=actor.id,
                email=actor.email,
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

    db.refresh(user)
    return user
