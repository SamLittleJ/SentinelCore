"""How many events each API key sends, per clock hour of arrival.

The volume spike rule (services/detection_service.py) reads these counts.
They are kept by the database clock when a batch arrives, because a sender
chooses the times its events claim: a flood stamped last week still arrives
now.
"""

from datetime import datetime, timedelta

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.models.api_key_usage import ApiKeyUsage


def record_arrival(db: Session, api_key: ApiKey, count: int, refused: bool) -> datetime:
    """Add a batch of `count` events to `api_key`'s current hour, refused or
    not, and return the hour. Not committed: the batch's own commit, which
    stores or refuses it, records the count with it."""
    statement = insert(ApiKeyUsage).values(
        api_key_id=api_key.id,
        hour=func.date_trunc("hour", func.now(), "UTC"),
        organization_id=api_key.organization_id,
        received=count,
        refused=count if refused else 0,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[ApiKeyUsage.api_key_id, ApiKeyUsage.hour],
        set_={
            "received": ApiKeyUsage.received + statement.excluded.received,
            "refused": ApiKeyUsage.refused + statement.excluded.refused,
        },
    ).returning(ApiKeyUsage.hour)
    return db.execute(statement).scalar_one()


def delete_old_usage(db: Session, retention_days: int) -> int:
    """Delete the hours of the days before the last `retention_days` whole UTC
    days, and today's. Returns how many hours were deleted."""
    today = func.date_trunc("day", func.now(), "UTC")
    deleted = db.scalars(
        delete(ApiKeyUsage)
        .where(ApiKeyUsage.hour < today - timedelta(days=retention_days))
        .returning(ApiKeyUsage.hour)
    ).all()
    db.commit()
    return len(deleted)
