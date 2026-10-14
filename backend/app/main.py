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
    invitations,
    metrics,
    organizations,
    security,
    users,
)
from app.api.security_headers import SecurityHeadersMiddleware, internal_error_handler
from app.core.config import Settings, settings
from app.core.logging import configure_logging
from app.services.session_cleanup import run_session_cleanup_periodically

configure_logging(settings.log_level, settings.log_format)


def create_app(settings: Settings) -> FastAPI:
    """The API, with its documentation, headers and cleanup task set from
    `settings`; routes and services read the shared settings. Tests build
    their own, with the settings they need."""

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        cleanup_task = None
        if settings.session_cleanup_interval_minutes > 0:
            cleanup_task = asyncio.create_task(
                run_session_cleanup_periodically(
                    settings.session_cleanup_interval_minutes
                )
            )

        yield

        if cleanup_task is not None:
            cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cleanup_task

    # The documentation runs code from a CDN (threat model T-58). When it is
    # off, its paths are unknown ones, answered with a plain 404.
    docs = settings.api_docs_enabled
    app = FastAPI(
        title="SentinelCore API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )

    app.middleware("http")(observe_requests)
    # Added last, so it wraps the others and every response they produce. An
    # unhandled error is answered outside every middleware, hence the handler.
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_max_age=settings.hsts_max_age,
        documentation=docs,
    )
    app.add_exception_handler(Exception, internal_error_handler(settings.hsts_max_age))

    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(audit.router)
    app.include_router(security.router)
    app.include_router(admin_users.router)
    app.include_router(api_keys.router)
    app.include_router(organizations.router)
    app.include_router(invitations.router)
    app.include_router(invitations.public_router)
    app.include_router(ingest.router)
    return app


app = create_app(settings)
