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
    """Readiness: the application can serve traffic, database included.

    A database role that bypasses row-level security, such as a superuser,
    would leave the organizations to the application's filters alone, so
    the application is not ready on one.
    """
    try:
        bypasses = db.execute(
            text(
                "SELECT rolsuper OR rolbypassrls FROM pg_roles "
                "WHERE rolname = current_user"
            )
        ).scalar_one()
    except SQLAlchemyError:
        logger.exception("Readiness check failed: database unavailable")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "unavailable"},
        )

    if bypasses:
        logger.error(
            "Readiness check failed: the database role bypasses row-level "
            "security; DATABASE_URL must name the API's role"
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "unsafe role"},
        )

    return {"status": "ok", "database": "ok"}
