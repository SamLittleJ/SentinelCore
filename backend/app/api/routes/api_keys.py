from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, require_role
from app.models.api_key import ApiKey
from app.models.audit_log import AuditEventType
from app.models.user import User, UserRole
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.services.api_key_service import (
    create_api_key,
    get_api_key,
    list_api_keys,
    revoke_api_key,
)
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/admin/api-keys", tags=["api-keys"])

# Operators see which systems send events; only the owner issues or revokes
# a key, since a key can write into the detection pipeline.
READ_ROLES = (UserRole.ADMIN, UserRole.OWNER, UserRole.SECURITY_ANALYST)


def _get_key_or_404(db: Session, key_id: int) -> ApiKey:
    api_key = get_api_key(db, key_id)
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    return api_key


@router.get("", response_model=list[ApiKeyRead])
def read_api_keys(
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[User, Depends(require_role(*READ_ROLES))],
) -> list[ApiKey]:
    api_keys = list_api_keys(db)
    create_audit_log(
        db=db,
        event_type=AuditEventType.API_KEYS_VIEWED,
        user=current_user,
        ip_address=client_ip,
        message="Listed API keys",
    )
    return api_keys


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def issue_api_key(
    key_in: ApiKeyCreate,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER))],
) -> ApiKeyCreated:
    """Create a key for another system. The response holds the full key, which
    is not shown again."""
    api_key, key = create_api_key(db, key_in, current_user, client_ip)
    return ApiKeyCreated(api_key=ApiKeyRead.model_validate(api_key), key=key)


@router.post("/{key_id}/revoke", response_model=ApiKeyRead)
def revoke_key(
    key_id: int,
    db: Annotated[Session, Depends(get_db)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER))],
) -> ApiKey:
    """Stop a key from working at once. Revoking a revoked key changes nothing."""
    api_key = _get_key_or_404(db, key_id)
    return revoke_api_key(db, api_key, current_user, client_ip)
