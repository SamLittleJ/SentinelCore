from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import UserRole


class Invitation(Base):
    """An offer of an account with a given email and role, made by an admin or
    the owner. Accounts are only created this way, apart from the first owner
    (`python -m app.cli create-owner`).

    The person invited receives a link with a token; only a hash of its secret
    is stored. The token works once, until `expires_at`.
    """

    __tablename__ = "invitations"
    # At most one open invitation per email: a new one revokes the old one.
    # Expired ones still count, since the index cannot read the clock; they
    # are revoked the same way.
    __table_args__ = (
        Index(
            "ix_invitations_open_email",
            "email",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Finds the invitation from its token; safe to show and log.
    prefix: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    # SHA-256 of the secret part, hex encoded.
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False
    )
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The account created from it.
    accepted_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
