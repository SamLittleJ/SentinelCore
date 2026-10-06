from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import create_access_token
from app.models.audit_log import AuditEventType
from app.models.security_event import SecurityEventType, SecuritySeverity
from app.schemas.user import Token, UserCreate, UserLogin, UserRead
from app.services.audit_service import create_audit_log
from app.services.security_event_service import create_security_event
from app.services.user_service import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_username,
)

router = APIRouter(prefix="/auth", tags=["auth"])

DUPLICATE_USER_DETAILS = {
    "ix_users_email": "Email already registered",
    "ix_users_username": "Username already taken",
}


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    user_in: UserCreate, db: Annotated[Session, Depends(get_db)]
) -> UserRead:
    existing_user_by_email = get_user_by_email(db, user_in.email)
    if existing_user_by_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    existing_user_by_username = get_user_by_username(db, user_in.username)
    if existing_user_by_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # The checks above can race with a concurrent registration; the unique
    # indexes are the final guard.
    try:
        user = create_user(db, user_in)
    except IntegrityError as exc:
        if not isinstance(exc.orig, UniqueViolation):
            raise
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=DUPLICATE_USER_DETAILS.get(
                exc.orig.diag.constraint_name, "User already exists"
            ),
        ) from exc

    create_audit_log(
        db=db,
        event_type=AuditEventType.USER_REGISTERED,
        user=user,
        message=f"User registered: {user.email}",
    )

    create_security_event(
        db=db,
        event_type=SecurityEventType.USER_REGISTERED,
        severity=SecuritySeverity.INFO,
        user=user,
        message=f"New user registered: {user.email}",
    )
    return user


@router.post("/login", response_model=Token)
def login_user(user_in: UserLogin, db: Annotated[Session, Depends(get_db)]) -> Token:
    user = authenticate_user(db, user_in.email, user_in.password)
    if not user:
        create_audit_log(
            db=db,
            event_type=AuditEventType.LOGIN_FAILED,
            email=user_in.email,
            message=f"Failed login attempt for email: {user_in.email}",
        )

        create_security_event(
            db=db,
            event_type=SecurityEventType.LOGIN_FAILED,
            severity=SecuritySeverity.WARN,
            email=user_in.email,
            message=f"Failed login attempt for email: {user_in.email}",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        create_audit_log(
            db=db,
            event_type=AuditEventType.LOGIN_FAILED,
            user=user,
            message=f"Login attempt for inactive user: {user.email}",
        )

        create_security_event(
            db=db,
            event_type=SecurityEventType.LOGIN_FAILED,
            severity=SecuritySeverity.WARN,
            user=user,
            message=f"Login attempt for inactive user: {user.email}",
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    create_audit_log(
        db=db,
        event_type=AuditEventType.LOGIN_SUCCESS,
        user=user,
        message=f"Successful login for user: {user.email}",
    )

    create_security_event(
        db=db,
        event_type=SecurityEventType.LOGIN_SUCCESS,
        severity=SecuritySeverity.INFO,
        user=user,
        message=f"Successful login for user: {user.email}",
    )

    access_token = create_access_token(user.email)

    return Token(
        access_token=access_token,
        # OAuth2 token type, not a password or secret.
        token_type="bearer",  # nosec B106
    )
