from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApiKeyUsage(Base):
    """How many events an API key sent in one clock hour, by the database
    clock when they arrived, not the time the events say they happened.

    The volume spike rule compares an hour with the key's usual busiest hour
    (services/detection_service.py). Old hours are deleted by the periodic
    cleanup (API_KEY_USAGE_RETENTION_DAYS)."""

    __tablename__ = "api_key_usage"

    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"), primary_key=True)
    # The start of the hour, in UTC.
    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    # The key's organization, which row-level security checks.
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    # Every event of a valid batch, refused or not: a flood the rate limit
    # turns away is still a flood.
    received: Mapped[int] = mapped_column(Integer, nullable=False)
    # Those of them refused over the rate limit.
    refused: Mapped[int] = mapped_column(Integer, nullable=False)
    # When the hour raised its volume spike alert; one alert per hour at most.
    alerted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
