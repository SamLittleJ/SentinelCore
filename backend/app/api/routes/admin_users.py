from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, require_role
from app.models.audit_log import AuditEventType
from app.models.security_event import SecurityEventType, SecuritySeverity
from app.models.user import User, UserRole
from app.schemas.user import UserRead, UserRoleUpdate, UserStatusUpdate
from app.services.audit_service import create_audit_log
from app.services.security_event_service import create_security_event
from app.services.user_service import (
    get_user_by_id,
    list_users,
    update_user_role,
    update_user_status,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=list[UserRead])
def read_users(
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN, UserRole.OWNER)),
    ],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[User]:
    create_audit_log(
        db=db,
        ip_address=client_ip,
        user=current_user,
        event_type=AuditEventType.ADMIN_ENDPOINT_ACCESSED,
        message="Admin listed users",
    )

    create_security_event(
        db=db,
        ip_address=client_ip,
        user=current_user,
        event_type=SecurityEventType.ADMIN_ACCESS,
        severity=SecuritySeverity.INFO,
        message="Admin listed users",
    )

    return list_users(db, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserRead)
def read_user_by_id(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN, UserRole.OWNER)),
    ],
) -> User:
    target_user = get_user_by_id(db, user_id)

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    create_audit_log(
        db=db,
        ip_address=client_ip,
        user=current_user,
        event_type=AuditEventType.ADMIN_ENDPOINT_ACCESSED,
        message=f"Admin viewed user details for user_id={target_user.id}",
    )

    create_security_event(
        db=db,
        ip_address=client_ip,
        user=current_user,
        event_type=SecurityEventType.ADMIN_ACCESS,
        severity=SecuritySeverity.INFO,
        message=f"Admin viewed user details for user_id={target_user.id}",
    )

    return target_user


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
    target_user = get_user_by_id(db, user_id)

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

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
    target_user = get_user_by_id(db, user_id)

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Users cannot change their own status",
        )

    if target_user.role == UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change the status of an owner",
        )

    if current_user.role == UserRole.ADMIN and target_user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an owner can change the status of an admin",
        )

    return update_user_status(
        db=db,
        ip_address=client_ip,
        user=target_user,
        is_active=status_in.is_active,
        actor=current_user,
    )
