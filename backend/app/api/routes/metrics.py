import hmac
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import settings

router = APIRouter()


def _metrics_token() -> str | None:
    if settings.metrics_token is None:
        return None
    # An empty METRICS_TOKEN= in .env means no token, not an empty one.
    return settings.metrics_token.get_secret_value() or None


@router.get("/metrics", include_in_schema=False)
def read_metrics(
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    token = _metrics_token()
    if token is not None:
        expected = f"Bearer {token}".encode()
        provided = (authorization or "").encode()
        # Constant-time comparison, so response timing does not leak the token.
        if not hmac.compare_digest(provided, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid metrics token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
