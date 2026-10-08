import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.middleware import observe_requests
from app.api.routes import (
    admin_users,
    api_keys,
    audit,
    auth,
    health,
    ingest,
    metrics,
    security,
    users,
)
from app.core.config import settings
from app.core.logging import configure_logging
from app.services.session_cleanup import run_session_cleanup_periodically

configure_logging(settings.log_level, settings.log_format)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cleanup_task = None
    if settings.session_cleanup_interval_minutes > 0:
        cleanup_task = asyncio.create_task(
            run_session_cleanup_periodically(settings.session_cleanup_interval_minutes)
        )

    yield

    if cleanup_task is not None:
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(title="SentinelCore API", version="0.1.0", lifespan=lifespan)

app.middleware("http")(observe_requests)

app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(audit.router)
app.include_router(security.router)
app.include_router(admin_users.router)
app.include_router(api_keys.router)
app.include_router(ingest.router)
