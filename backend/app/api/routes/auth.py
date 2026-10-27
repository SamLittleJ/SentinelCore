from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.cookies import clear_auth_cookies, set_auth_cookies
from app.api.deps import (
    ACCOUNT_LOCKED_DETAIL,
    get_client_ip,
    get_current_session,
    get_current_user,
    get_db,
    get_system_db,
    get_user_agent,
)
from app.core.config import settings
from app.core.security import create_access_token
from app.models.audit_log import AuditEventType
from app.models.security_event import SecurityEventType, SecuritySeverity
from app.models.user import User
from app.models.user_session import UserSession
from app.schemas.user import Token, UserLogin
from app.services.audit_service import create_audit_log
from app.services.login_protection_service import (
    count_recent_failed_logins,
    get_lockout_seconds_remaining,
    lock_login,
)
from app.services.security_event_service import create_security_event
from app.services.session_service import (
    create_session,
    revoke_session,
    stage_revoke_all_sessions,
)
from app.services.sign_in_limit_service import (
    address_key,
    give_back,
    limit_address,
    refuse_attempt,
    take_attempt,
)
from app.services.user_service import (
    authenticate_user,
    is_account_locked,
    may_sign_in,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def too_many_login_attempts(retry_after_seconds: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many failed login attempts. Try again later.",
        headers={"Retry-After": str(retry_after_seconds)},
    )


def _log_in(
    db: Session,
    user_in: UserLogin,
    client_ip: str | None,
    user_agent: str | None,
) -> tuple[Token, UserSession]:
    """Shared by the JSON and OAuth2 form login endpoints, so both get the
    same brute-force protection, events and session handling.

    The address's limit comes first, before the email's lockout and the
    password, and answers as the lockout does, so a refused attempt learns
    nothing and writes no event.
    """
    address = address_key(client_ip)
    attempt = take_attempt(db, address)
    if attempt.retry_after:
        refuse_attempt(address)
        raise too_many_login_attempts(attempt.retry_after)

    try:
        token, session = _sign_in(db, user_in, client_ip, user_agent)
    except HTTPException:
        if attempt.took_last:
            limit_address(db, address, client_ip)
        raise

    give_back(db, address)
    return token, session


def _sign_in(
    db: Session,
    user_in: UserLogin,
    client_ip: str | None,
    user_agent: str | None,
) -> tuple[Token, UserSession]:
    """Check the email's lockout and the password, and open a session; every
    refusal is an HTTPException."""
    email = user_in.email

    def record(
        audit_type: AuditEventType,
        event_type: SecurityEventType,
        severity: SecuritySeverity,
        message: str,
        user: User | None = None,
    ) -> None:
        """One outcome of this sign-in, in the audit log and as a security
        event, with the same message."""
        create_audit_log(
            db=db,
            event_type=audit_type,
            user=user,
            email=email,
            ip_address=client_ip,
            message=message,
        )
        create_security_event(
            db=db,
            event_type=event_type,
            severity=severity,
            user=user,
            email=email,
            ip_address=client_ip,
            user_agent=user_agent,
            message=message,
        )

    # A locked email is rejected before the password is checked, so guesses
    # made during the lockout reveal nothing.
    lockout_seconds = get_lockout_seconds_remaining(db, email)
    if lockout_seconds:
        record(
            AuditEventType.LOGIN_BLOCKED,
            SecurityEventType.LOGIN_BLOCKED,
            SecuritySeverity.WARN,
            f"Login blocked for locked email: {email}",
        )
        raise too_many_login_attempts(lockout_seconds)

    user = authenticate_user(db, email, user_in.password)
    if user is None or not may_sign_in(db, user):
        if user is None:
            message = f"Failed login attempt for email: {email}"
        elif not user.is_active:
            message = f"Login attempt for inactive user: {email}"
        else:
            message = f"Login attempt for a member of a suspended organization: {email}"

        record(
            AuditEventType.LOGIN_FAILED,
            SecurityEventType.LOGIN_FAILED,
            SecuritySeverity.WARN,
            message,
            user,
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

    # Checked after the password, like the inactive status, so only someone
    # who knows it learns that the account is locked. The response does not
    # say when the lock ends: during a suspected compromise that someone may
    # be the attacker.
    if is_account_locked(db, user):
        record(
            AuditEventType.LOGIN_BLOCKED,
            SecurityEventType.LOGIN_BLOCKED,
            SecuritySeverity.WARN,
            f"Login with valid password blocked for locked user: {email}",
            user,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ACCOUNT_LOCKED_DETAIL,
        )

    record(
        AuditEventType.LOGIN_SUCCESS,
        SecurityEventType.LOGIN_SUCCESS,
        SecuritySeverity.INFO,
        f"Successful login for user: {user.email}",
        user,
    )

    session = create_session(db, user, client_ip, user_agent)
    access_token = create_access_token(
        user_id=user.id,
        session_id=session.id,
        issued_at=session.created_at,
        expires_at=session.expires_at,
    )

    token = Token(
        access_token=access_token,
        # OAuth2 token type, not a password or secret.
        token_type="bearer",  # nosec B106
        expires_in=settings.access_token_expire_minutes * 60,
    )
    return token, session


@router.post("/login", response_model=Token)
def login_user(
    user_in: UserLogin,
    db: Annotated[Session, Depends(get_system_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    user_agent: Annotated[str | None, Depends(get_user_agent)],
) -> Token:
    token, _ = _log_in(db, user_in, client_ip, user_agent)
    return token


@router.post("/session", status_code=status.HTTP_204_NO_CONTENT)
def create_browser_session(
    user_in: UserLogin,
    response: Response,
    db: Annotated[Session, Depends(get_system_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    user_agent: Annotated[str | None, Depends(get_user_agent)],
) -> None:
    """Browser login: the token is set as an httpOnly cookie and never
    appears in the response body.

    Only JSON bodies are accepted, so another site cannot submit this login
    with an HTML form (login CSRF).
    """
    token, session = _log_in(db, user_in, client_ip, user_agent)
    set_auth_cookies(response, token.access_token, session.id, token.expires_in)


@router.post("/token", response_model=Token)
def login_for_access_token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_system_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    user_agent: Annotated[str | None, Depends(get_user_agent)],
) -> Token:
    """OAuth2 password flow, used by the Authorize button in Swagger UI.

    The form's `username` field carries the email address.
    """
    try:
        user_in = UserLogin(email=form.username, password=form.password)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    token, _ = _log_in(db, user_in, client_ip, user_agent)
    return token


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(get_current_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> None:
    """Revoke the session of the token used for this request."""
    revoke_session(db, session)
    clear_auth_cookies(response)

    create_audit_log(
        db=db,
        event_type=AuditEventType.SESSION_REVOKED,
        user=current_user,
        ip_address=client_ip,
        message=f"User logged out, session_id={session.id}",
    )


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> None:
    """Revoke every active session of the current user, this one included."""
    stage_revoke_all_sessions(db, current_user.id)
    db.commit()
    clear_auth_cookies(response)

    create_audit_log(
        db=db,
        event_type=AuditEventType.ALL_SESSIONS_REVOKED,
        user=current_user,
        ip_address=client_ip,
        message="User logged out of all sessions",
    )
