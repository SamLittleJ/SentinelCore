from datetime import datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def database_now(db: Session) -> datetime:
    """The database clock, the one that stamps `created_at`. Time windows
    compare against it, so they never mix application and database time."""
    return db.execute(select(func.now())).scalar_one()
