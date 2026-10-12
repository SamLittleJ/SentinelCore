from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Registers the table the organization foreign key names.
from app.models import organization  # noqa: F401


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    SECURITY_ANALYST = "security_analyst"
    OWNER = "owner"


class User(Base):
    __tablename__ = "users"
    # The platform owner belongs to no organization; every other account to
    # exactly one.
    __table_args__ = (
        CheckConstraint(
            "(role = 'OWNER') = (organization_id IS NULL)",
            name="ck_users_owner_has_no_organization",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        default=UserRole.USER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set when the account is created, from its invitation, and never changed.
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    # Logins are refused until this time, on the database clock; set when an
    # operator contains a suspected compromise. Past values mean unlocked.
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
