from fastapi import FastAPI
from app.api.routes import health, auth, users, audit, security
from app.models.security_event import SecurityEvent
from app.core.database import engine, Base
from app.models.user import User
from app.models.audit_log import AuditLog

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SentinelCore API", version="0.1.0")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(audit.router)
app.include_router(security.router)