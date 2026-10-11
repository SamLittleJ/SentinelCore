from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Organization(Base):
    """A tenant: a company whose accounts, keys and events are kept apart from
    every other's. Every account belongs to exactly one, except the platform
    owner, who belongs to none and administers them all.

    Organizations are never deleted, so their audit trail stays; the owner
    suspends one instead.
    """

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # Short and fixed, for links and filters: renaming keeps it.
    slug: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # While set, members cannot sign in and the organization's API keys are
    # refused, as if they did not exist.
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
