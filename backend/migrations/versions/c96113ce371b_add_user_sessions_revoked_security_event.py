"""add user sessions revoked security event

Revision ID: c96113ce371b
Revises: 232fc184b0d7
Create Date: 2026-10-06 19:23:24.222191

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c96113ce371b"
down_revision: str | Sequence[str] | None = "232fc184b0d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_NAME = "security_event_types"

# SQLAlchemy stores enum member names, so the database values are uppercase.
OLD_VALUES = (
    "USER_REGISTERED",
    "LOGIN_SUCCESS",
    "LOGIN_FAILED",
    "ADMIN_ACCESS",
    "USER_ROLE_CHANGED",
    "USER_ACTIVATED",
    "USER_DEACTIVATED",
    "BRUTE_FORCE_DETECTED",
    "LOGIN_BLOCKED",
)
NEW_VALUE = "USER_SESSIONS_REVOKED"

# Maps back to the generic admin access event on downgrade.
DOWNGRADE_FALLBACK = "ADMIN_ACCESS"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(f"ALTER TYPE {ENUM_NAME} ADD VALUE IF NOT EXISTS '{NEW_VALUE}'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so the type is recreated without it
    after rows using it are mapped back to the generic admin access event.
    """
    old_values_sql = ", ".join(f"'{value}'" for value in OLD_VALUES)

    op.execute(
        f"UPDATE security_events SET event_type = '{DOWNGRADE_FALLBACK}' "
        f"WHERE event_type = '{NEW_VALUE}'"
    )
    op.execute(f"ALTER TYPE {ENUM_NAME} RENAME TO {ENUM_NAME}_old")
    op.execute(f"CREATE TYPE {ENUM_NAME} AS ENUM ({old_values_sql})")
    op.execute(
        f"ALTER TABLE security_events ALTER COLUMN event_type TYPE {ENUM_NAME} "
        f"USING event_type::text::{ENUM_NAME}"
    )
    op.execute(f"DROP TYPE {ENUM_NAME}_old")
