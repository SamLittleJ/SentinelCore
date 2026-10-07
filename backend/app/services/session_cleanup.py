import asyncio
import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.metrics import SESSIONS_DELETED
from app.services.session_service import delete_stale_sessions

logger = logging.getLogger(__name__)


def run_session_cleanup() -> int:
    """Delete stale sessions in a database session of its own."""
    with SessionLocal() as db:
        deleted = delete_stale_sessions(db, settings.session_retention_days)

    SESSIONS_DELETED.inc(deleted)
    logger.info(
        "Session cleanup completed",
        extra={
            "deleted_sessions": deleted,
            "retention_days": settings.session_retention_days,
        },
    )
    return deleted


async def run_session_cleanup_periodically(interval_minutes: int) -> None:
    """Run the cleanup every `interval_minutes`, until cancelled.

    A failed run is logged and retried at the next interval, so a temporary
    database outage does not stop the task.
    """
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            # The cleanup uses the synchronous database driver.
            await asyncio.to_thread(run_session_cleanup)
        except Exception:
            logger.exception("Session cleanup failed")
