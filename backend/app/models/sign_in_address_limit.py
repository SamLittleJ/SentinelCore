from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SignInAddressLimit(Base):
    """The token bucket that limits failed sign-ins from one address
    (services/sign_in_limit_service.py).

    An address belongs to no organization: the rows are read and written only
    by sign-in and the cleanup, which see every row. A row whose bucket has
    filled up again means the same as no row, and the cleanup deletes it."""

    __tablename__ = "sign_in_address_limits"

    # An IPv4 address, an IPv6 /64 network, or "unknown"
    # (sign_in_limit_service.address_key).
    address: Mapped[str] = mapped_column(String(45), primary_key=True)
    # The failed attempts the address may still make, as counted at
    # `refilled_at`.
    tokens: Mapped[float] = mapped_column(Float, nullable=False)
    refilled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
