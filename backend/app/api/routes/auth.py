from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.models.audit_log import AuditEventType
from app.models.security_event import SecurityEventType, SecuritySeverity
from app.schemas.user import Token, UserCreate, UserLogin, UserRead
from app.services.audit_service import create_audit_log
from app.services.login_protection_service import (
    count_recent_failed_logins,
    get_lockout_seconds_remaining,
    lock_login,
)
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
    user_in: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
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
        ip_address=client_ip,
        event_type=AuditEventType.USER_REGISTERED,
        user=user,
        message=f"User registered: {user.email}",
    )

    create_security_event(
        db=db,
        ip_address=client_ip,
        event_type=SecurityEventType.USER_REGISTERED,
        severity=SecuritySeverity.INFO,
        user=user,
        message=f"New user registered: {user.email}",
    )
    return user


def too_many_login_attempts(retry_after_seconds: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many failed login attempts. Try again later.",
        headers={"Retry-After": str(retry_after_seconds)},
    )


@router.post("/login", response_model=Token)
def login_user(
    user_in: UserLogin,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> Token:
    email = user_in.email

    # A locked email is rejected before the password is checked, so guesses
    # made during the lockout reveal nothing.
    lockout_seconds = get_lockout_seconds_remaining(db, email)
    if lockout_seconds:
        message = f"Login blocked for locked email: {email}"
        create_audit_log(
            db=db,
            event_type=AuditEventType.LOGIN_BLOCKED,
            email=email,
            ip_address=client_ip,
            message=message,
        )

        create_security_event(
            db=db,
            event_type=SecurityEventType.LOGIN_BLOCKED,
            severity=SecuritySeverity.WARN,
            email=email,
            ip_address=client_ip,
            message=message,
        )

        raise too_many_login_attempts(lockout_seconds)

    user = authenticate_user(db, email, user_in.password)
    if user is None or not user.is_active:
        if user is None:
            message = f"Failed login attempt for email: {email}"
        else:
            message = f"Login attempt for inactive user: {email}"

        create_audit_log(
            db=db,
            event_type=AuditEventType.LOGIN_FAILED,
            user=user,
            email=email,
            ip_address=client_ip,
            message=message,
        )

        create_security_event(
            db=db,
            event_type=SecurityEventType.LOGIN_FAILED,
            severity=SecuritySeverity.WARN,
            user=user,
            email=email,
            ip_address=client_ip,
            message=message,
        )

        if count_recent_failed_logins(db, email) >= settings.login_max_failed_attempts:
            raise too_many_login_attempts(lock_login(db, email, user, client_ip))

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    create_audit_log(
        db=db,
        event_type=AuditEventType.LOGIN_SUCCESS,
        user=user,
        ip_address=client_ip,
        message=f"Successful login for user: {user.email}",
    )

    create_security_event(
        db=db,
        event_type=SecurityEventType.LOGIN_SUCCESS,
        severity=SecuritySeverity.INFO,
        user=user,
        ip_address=client_ip,
        message=f"Successful login for user: {user.email}",
    )

    access_token = create_access_token(user.email)

    return Token(
        access_token=access_token,
        # OAuth2 token type, not a password or secret.
        token_type="bearer",  # nosec B106
    )
