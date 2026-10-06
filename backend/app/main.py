from fastapi import FastAPI

from app.api.middleware import observe_requests
from app.api.routes import admin_users, audit, auth, health, metrics, security, users
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging(settings.log_level, settings.log_format)

app = FastAPI(title="SentinelCore API", version="0.1.0")

app.middleware("http")(observe_requests)

app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(audit.router)
app.include_router(security.router)
app.include_router(admin_users.router)
