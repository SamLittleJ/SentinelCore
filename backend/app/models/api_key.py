from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApiKey(Base):
    """A key another system uses to send security events to the ingestion
    endpoint. Only a hash of its secret is stored; the full key is shown once,
    when it is created."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Shown in lists and logs to tell keys apart; the key starts with it.
    prefix: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    # SHA-256 of the secret part, hex encoded.
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Stamped as `source` on every event the key sends.
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
