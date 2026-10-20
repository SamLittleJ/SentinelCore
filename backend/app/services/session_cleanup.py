import asyncio
import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.metrics import SESSIONS_DELETED
from app.core.row_security import restrict_rows
from app.services.api_key_usage_service import delete_old_usage
from app.services.audit_chain_service import check_audit_chains
from app.services.session_service import delete_stale_sessions
from app.services.sign_in_limit_service import delete_full_buckets
from app.services.tenancy import SYSTEM

logger = logging.getLogger(__name__)


def run_session_cleanup() -> int:
    """Delete stale sessions, of every account, the API keys' old hourly
    counts and the sign-in limits of addresses whose buckets filled up again,
    then check the audit chains, in a database session of its own. Returns
    the sessions deleted."""
    with SessionLocal() as db:
        restrict_rows(db, SYSTEM)
        deleted = delete_stale_sessions(db, settings.session_retention_days)
        deleted_usage = delete_old_usage(db, settings.api_key_usage_retention_days)
        deleted_limits = delete_full_buckets(db)
        try:
            check_audit_chains(db)
        except Exception:
            # The deletions are committed; the chains are checked next time.
            db.rollback()
            logger.exception("Audit chain check failed")

    SESSIONS_DELETED.inc(deleted)
    logger.info(
        "Session cleanup completed",
        extra={
            "deleted_sessions": deleted,
            "retention_days": settings.session_retention_days,
            "deleted_api_key_usage_hours": deleted_usage,
            "api_key_usage_retention_days": settings.api_key_usage_retention_days,
            "deleted_sign_in_address_limits": deleted_limits,
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
