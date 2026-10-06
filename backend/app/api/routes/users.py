import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_client_ip,
    get_current_session,
    get_current_user,
    get_db,
    require_role,
)
from app.models.audit_log import AuditEventType
from app.models.security_event import SecurityEventType, SecuritySeverity
from app.models.user import User, UserRole
from app.models.user_session import UserSession
from app.schemas.user import SessionRead, UserRead
from app.services.audit_service import create_audit_log
from app.services.security_event_service import create_security_event
from app.services.session_service import (
    get_active_session,
    list_active_sessions,
    revoke_session,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return current_user


@router.get("/admin-only")
def read_admin_only(
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[
        User, Depends(require_role(UserRole.ADMIN, UserRole.OWNER))
    ],
) -> dict:
    create_audit_log(
        db=db,
        ip_address=client_ip,
        event_type=AuditEventType.ADMIN_ENDPOINT_ACCESSED,
        user=current_user,
        message=f"Admin endpoint accessed by user: {current_user.email}",
    )

    create_security_event(
        db=db,
        ip_address=client_ip,
        event_type=SecurityEventType.ADMIN_ACCESS,
        severity=SecuritySeverity.INFO,
        user=current_user,
        message=f"Admin endpoint accessed by user: {current_user.email}",
    )

    return {
        "message": "You have admin-level access.",
        "username": current_user.username,
        "role": current_user.role,
    }


@router.get("/me/sessions", response_model=list[SessionRead])
def read_my_sessions(
    db: Annotated[Session, Depends(get_db)],
    current_session: Annotated[UserSession, Depends(get_current_session)],
) -> list[SessionRead]:
    sessions = list_active_sessions(db, current_session.user_id)
    return [
        SessionRead(
            id=session.id,
            created_at=session.created_at,
            expires_at=session.expires_at,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            current=session.id == current_session.id,
        )
        for session in sessions
    ]


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_my_session(
    session_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> None:
    session = get_active_session(db, session_id)
    # Another user's session answers like a missing one, so session ids
    # belonging to others cannot be confirmed.
    if session is None or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    revoke_session(db, session)

    create_audit_log(
        db=db,
        event_type=AuditEventType.SESSION_REVOKED,
        user=current_user,
        ip_address=client_ip,
        message=f"User revoked session_id={session.id}",
    )
