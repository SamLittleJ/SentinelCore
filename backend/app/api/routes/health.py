import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/health")
def health_check() -> dict[str, str]:
    """Liveness: the process is running and can answer requests."""
    return {"status": "ok"}


@router.get("/health/ready", response_model=None)
def readiness_check(
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str] | JSONResponse:
    """Readiness: the application can serve traffic, database included."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Readiness check failed: database unavailable")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "unavailable"},
        )

    return {"status": "ok", "database": "ok"}
