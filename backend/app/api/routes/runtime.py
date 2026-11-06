import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.api.deps import get_system_db
from app.schemas.runtime import FalcoAlert
from app.services.runtime_alert_service import store_runtime_alert


def runtime_router(token: SecretStr) -> APIRouter:
    """POST /ingest/runtime, for falcosidekick in the cluster. The API has it
    only with FALCO_INGEST_TOKEN set; nginx never forwards it."""
    router = APIRouter(prefix="/ingest", tags=["ingest"])
    expected = f"Bearer {token.get_secret_value()}".encode()

    def check_token(authorization: Annotated[str | None, Header()] = None) -> None:
        # Constant-time comparison, and one answer for a missing or wrong token.
        if not hmac.compare_digest((authorization or "").encode(), expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @router.post(
        "/runtime",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(check_token)],
    )
    def receive_runtime_alert(
        alert: FalcoAlert, db: Annotated[Session, Depends(get_system_db)]
    ) -> None:
        """Receive one of Falco's alerts. Kept, ignored or already stored, the
        answer is the same, so the sender cannot learn which rules are kept.
        The platform's rows, which belong to no organization, are written only
        in the system scope; the service reads nothing but Falco's own."""
        store_runtime_alert(db, alert)

    return router
