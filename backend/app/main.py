from fastapi import FastAPI
from .api.routes import health, auth
from app.core.database import engine, Base
from app.models.user import User

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SentinelCore API", version="0.1.0")

app.include_router(health.router)
app.include_router(auth.router)
