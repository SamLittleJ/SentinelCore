"""add users viewed audit event

Revision ID: 370d6e54e7cf
Revises: 06b4f5ced4de
Create Date: 2026-10-07 12:19:55.128608

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "370d6e54e7cf"
down_revision: str | Sequence[str] | None = "06b4f5ced4de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_NAME = "audit_event_types"

# SQLAlchemy stores enum member names, so the database values are uppercase.
OLD_VALUES = (
    "USER_REGISTERED",
    "LOGIN_SUCCESS",
    "LOGIN_FAILED",
    "ADMIN_ENDPOINT_ACCESSED",
    "USER_ROLE_CHANGED",
    "USER_ACTIVATED",
    "USER_DEACTIVATED",
    "LOGIN_LOCKED",
    "LOGIN_BLOCKED",
    "AUDIT_LOGS_VIEWED",
    "SECURITY_EVENTS_VIEWED",
    "SESSION_REVOKED",
    "ALL_SESSIONS_REVOKED",
    "OTHER_SESSIONS_REVOKED",
)
NEW_VALUE = "USERS_VIEWED"

# User reads were recorded as admin endpoint access before this type existed.
DOWNGRADE_FALLBACK = "ADMIN_ENDPOINT_ACCESSED"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(f"ALTER TYPE {ENUM_NAME} ADD VALUE IF NOT EXISTS '{NEW_VALUE}'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so the type is recreated without it
    after rows using it are mapped back.
    """
    old_values_sql = ", ".join(f"'{value}'" for value in OLD_VALUES)

    op.execute(
        f"UPDATE audit_logs SET event_type = '{DOWNGRADE_FALLBACK}' "
        f"WHERE event_type = '{NEW_VALUE}'"
    )
    op.execute(f"ALTER TYPE {ENUM_NAME} RENAME TO {ENUM_NAME}_old")
    op.execute(f"CREATE TYPE {ENUM_NAME} AS ENUM ({old_values_sql})")
    op.execute(
        f"ALTER TABLE audit_logs ALTER COLUMN event_type TYPE {ENUM_NAME} "
        f"USING event_type::text::{ENUM_NAME}"
    )
    op.execute(f"DROP TYPE {ENUM_NAME}_old")
