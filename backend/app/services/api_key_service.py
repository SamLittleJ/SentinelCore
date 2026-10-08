"""API keys for the ingestion endpoint.

A key reads `sck_<prefix>_<secret>`. The prefix finds the key and is safe to
show; the secret is 32 random bytes, of which only a SHA-256 hash is stored.
A fast hash is enough here, unlike for passwords: the secret is random and
long, so guessing it from its hash is not feasible.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import database_now
from app.core.metrics import record_security_event
from app.models.api_key import ApiKey
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate

KEY_SCHEME = "sck"


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _commit_key_change(
    db: Session,
    actor: User,
    audit_event_type: AuditEventType,
    security_event_type: SecurityEventType,
    message: str,
    ip_address: str | None,
) -> None:
    """Commit a staged change to a key together with its audit and security
    events, so either all three are stored or none are."""
    db.add_all(
        [
            AuditLog(
                event_type=audit_event_type,
                user_id=actor.id,
                email=actor.email,
                ip_address=ip_address,
                message=message,
            ),
            SecurityEvent(
                event_type=security_event_type,
                severity=SecuritySeverity.INFO,
                user_id=actor.id,
                email=actor.email,
                ip_address=ip_address,
                message=message,
            ),
        ]
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    record_security_event(security_event_type, SecuritySeverity.INFO)


def create_api_key(
    db: Session,
    data: ApiKeyCreate,
    actor: User,
    ip_address: str | None = None,
) -> tuple[ApiKey, str]:
    """Create a key and return it with its full value, which is never
    available again."""
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    api_key = ApiKey(
        prefix=prefix,
        secret_hash=_hash_secret(secret),
        name=data.name,
        source=data.source,
        created_by_id=actor.id,
        expires_at=database_now(db) + timedelta(days=data.expires_in_days),
    )
    db.add(api_key)
    _commit_key_change(
        db,
        actor,
        AuditEventType.API_KEY_CREATED,
        SecurityEventType.API_KEY_CREATED,
        (
            f"Owner created API key {prefix} ({data.name}) for source "
            f"{data.source}, valid for {data.expires_in_days} days"
        ),
        ip_address,
    )
    db.refresh(api_key)
    return api_key, f"{KEY_SCHEME}_{prefix}_{secret}"


def list_api_keys(db: Session) -> list[ApiKey]:
    return list(db.scalars(select(ApiKey).order_by(ApiKey.id.desc())).all())


def get_api_key(db: Session, key_id: int) -> ApiKey | None:
    return db.get(ApiKey, key_id)


def revoke_api_key(
    db: Session,
    api_key: ApiKey,
    actor: User,
    ip_address: str | None = None,
) -> ApiKey:
    if api_key.revoked_at is not None:
        return api_key  # No change needed

    api_key.revoked_at = database_now(db)
    _commit_key_change(
        db,
        actor,
        AuditEventType.API_KEY_REVOKED,
        SecurityEventType.API_KEY_REVOKED,
        f"Owner revoked API key {api_key.prefix} ({api_key.name})",
        ip_address,
    )
    db.refresh(api_key)
    return api_key


def authenticate_api_key(db: Session, presented: str) -> ApiKey | None:
    """The key `presented` stands for, if it is valid now: known, matching,
    not revoked and not expired. Every failure looks the same to the caller."""
    scheme, _, rest = presented.partition("_")
    prefix, _, secret = rest.partition("_")
    if scheme != KEY_SCHEME or not prefix or not secret:
        return None

    api_key = db.scalar(select(ApiKey).where(ApiKey.prefix == prefix))
    # Compared in constant time, so the response time does not reveal how
    # much of the secret matched.
    expected = api_key.secret_hash if api_key else _hash_secret("")
    matches = hmac.compare_digest(_hash_secret(secret), expected)
    if api_key is None or not matches:
        return None
    if api_key.revoked_at is not None or api_key.expires_at <= database_now(db):
        return None
    return api_key
