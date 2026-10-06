import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.user_session import UserSession

USER_AGENT_MAX_LENGTH = 255


def create_session(
    db: Session,
    user: User,
    ip_address: str | None,
    user_agent: str | None,
) -> UserSession:
    # Both timestamps come from the application clock, the same one that later
    # validates the token's iat and exp.
    created_at = datetime.now(UTC)
    session = UserSession(
        user_id=user.id,
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=settings.access_token_expire_minutes),
        ip_address=ip_address,
        user_agent=user_agent[:USER_AGENT_MAX_LENGTH] if user_agent else None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _active_sessions_condition():
    return (UserSession.revoked_at.is_(None)) & (UserSession.expires_at > func.now())


def get_active_session(db: Session, session_id: uuid.UUID) -> UserSession | None:
    statement = select(UserSession).where(
        UserSession.id == session_id,
        _active_sessions_condition(),
    )
    return db.scalar(statement)


def list_active_sessions(db: Session, user_id: int) -> list[UserSession]:
    statement = (
        select(UserSession)
        .where(UserSession.user_id == user_id, _active_sessions_condition())
        .order_by(UserSession.created_at.desc())
    )
    return list(db.scalars(statement).all())


def revoke_session(db: Session, session: UserSession) -> None:
    session.revoked_at = datetime.now(UTC)
    db.commit()


def stage_revoke_all_sessions(db: Session, user_id: int) -> int:
    """Mark every active session of `user_id` as revoked, without committing,
    so callers can commit it together with related changes.

    Returns the number of sessions revoked.
    """
    revoked_ids = db.scalars(
        update(UserSession)
        .where(UserSession.user_id == user_id, _active_sessions_condition())
        .values(revoked_at=func.now())
        .returning(UserSession.id)
    ).all()
    return len(revoked_ids)


def delete_stale_sessions(db: Session, retention_days: int) -> int:
    """Delete sessions that expired or were revoked more than `retention_days`
    ago. Active sessions are never deleted. Returns the number deleted."""
    cutoff = func.now() - timedelta(days=retention_days)
    deleted_ids = db.scalars(
        delete(UserSession)
        .where(
            or_(
                UserSession.expires_at < cutoff,
                UserSession.revoked_at < cutoff,
            )
        )
        .returning(UserSession.id)
    ).all()
    db.commit()
    return len(deleted_ids)
