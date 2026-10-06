import ipaddress
import uuid
from collections.abc import Callable, Generator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.models.user_session import UserSession
from app.services.session_service import get_active_session

# /auth/token accepts the OAuth2 password form, so Swagger UI can log in.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


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
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> UserSession:
    """Validate the bearer token and return its active session."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

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
