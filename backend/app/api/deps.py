import hmac
import ipaddress
import uuid
from collections.abc import Callable, Generator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.api.cookies import CSRF_HEADER, SESSION_COOKIE
from app.core.database import SessionLocal
from app.core.security import csrf_token_for, decode_access_token
from app.models.user import User, UserRole
from app.models.user_session import UserSession
from app.services.session_service import get_active_session

# /auth/token accepts the OAuth2 password form, so Swagger UI can log in.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

# Methods that never change state; cookie-authenticated requests with any
# other method must carry the CSRF token.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def get_client_ip(request: Request) -> str | None:
    """Return the client's IP address, or None if it is not a valid IP.

    Behind a reverse proxy, run uvicorn with --proxy-headers and
    --forwarded-allow-ips so request.client reflects the real client.
    """
    if request.client is None:
        return None

    try:
        return str(ipaddress.ip_address(request.client.host))
    except ValueError:
        return None


def get_current_session(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)],
) -> UserSession:
    """Validate the access token and return its active session.

    The token comes from the Authorization header (API clients, Swagger) or,
    when that is absent, from the session cookie set by browser login.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = bearer_token
    from_cookie = False
    if token is None:
        token = request.cookies.get(SESSION_COOKIE)
        from_cookie = token is not None
    if token is None:
        raise credentials_exception

    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
        session_id = uuid.UUID(payload["jti"])
    except (InvalidTokenError, ValueError) as exc:
        raise credentials_exception from exc

    user = db.get(User, user_id)
    if user is None:
        raise credentials_exception

    # Checked before the session, so a deactivated user gets a clear answer
    # even though deactivation also revokes their sessions.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    session = get_active_session(db, session_id)
    if session is None or session.user_id != user.id:
        raise credentials_exception

    # Browsers attach cookies automatically, including to requests started by
    # other sites; the CSRF header proves the request came from our frontend.
    if from_cookie and request.method not in SAFE_METHODS:
        provided = request.headers.get(CSRF_HEADER, "").encode()
        expected = csrf_token_for(session.id).encode()
        if not hmac.compare_digest(provided, expected):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing or invalid",
            )

    return session


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(get_current_session)],
) -> User:
    # Already loaded by get_current_session, so this reads the identity map.
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*allowed_roles: UserRole) -> Callable:
    def role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker
