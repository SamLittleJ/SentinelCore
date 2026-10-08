from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.api_key import ApiKey
from app.schemas.ingest import IngestRequest, IngestResult
from app.services.api_key_service import authenticate_api_key
from app.services.ingestion_service import ingest_events

router = APIRouter(prefix="/ingest", tags=["ingest"])

api_key_scheme = HTTPBearer(
    scheme_name="IngestionKey",
    description="An API key issued by the owner, as `Bearer sck_...`.",
    auto_error=False,
)


def get_ingestion_key(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(api_key_scheme)
    ],
) -> ApiKey:
    """The API key of the request. A missing, unknown, revoked or expired key
    gets the same answer, so a caller cannot tell them apart."""
    api_key = authenticate_api_key(db, credentials.credentials) if credentials else None
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key


@router.post(
    "/events", response_model=IngestResult, status_code=status.HTTP_202_ACCEPTED
)
def ingest_security_events(
    request: IngestRequest,
    db: Annotated[Session, Depends(get_db)],
    api_key: Annotated[ApiKey, Depends(get_ingestion_key)],
) -> IngestResult:
    """Receive sign-ins from another system. They are stored with the key's
    source and go through the detection rules."""
    return IngestResult(accepted=ingest_events(db, api_key, request.events))
