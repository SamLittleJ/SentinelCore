import secrets
import uuid
from datetime import datetime

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()

# Verified against when no user matches, so a login for an unknown email
# costs the same hashing time as a login for an existing one.
DUMMY_PASSWORD_HASH = password_hash.hash(secrets.token_urlsafe(32))

REQUIRED_CLAIMS = ["iss", "aud", "sub", "jti", "iat", "exp"]


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(
    user_id: int,
    session_id: uuid.UUID,
    issued_at: datetime,
    expires_at: datetime,
) -> str:
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        # RFC 7519 requires `sub` to be a string.
        "sub": str(user_id),
        "jti": str(session_id),
        "iat": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    """Verify signature, algorithm, issuer, audience and expiry.

    Raises `jwt.InvalidTokenError` if any check fails or a claim is missing.
    """
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": REQUIRED_CLAIMS},
    )
