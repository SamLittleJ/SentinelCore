"""add log view audit event types

Revision ID: 1ff3830ec505
Revises: 449c22b3652c
Create Date: 2026-10-06 18:43:36.507080

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1ff3830ec505"
down_revision: str | Sequence[str] | None = "449c22b3652c"
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
)
NEW_VALUES = ("AUDIT_LOGS_VIEWED", "SECURITY_EVENTS_VIEWED")

# Log views map back to the generic admin access event on downgrade.
DOWNGRADE_FALLBACK = "ADMIN_ENDPOINT_ACCESSED"


def upgrade() -> None:
    """Upgrade schema."""
    for value in NEW_VALUES:
        op.execute(f"ALTER TYPE {ENUM_NAME} ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so the type is recreated without them
    after rows using the new values are mapped back to the generic admin event.
    """
    new_values_sql = ", ".join(f"'{value}'" for value in NEW_VALUES)
    old_values_sql = ", ".join(f"'{value}'" for value in OLD_VALUES)

    op.execute(
        f"UPDATE audit_logs SET event_type = '{DOWNGRADE_FALLBACK}' "
        f"WHERE event_type IN ({new_values_sql})"
    )
    op.execute(f"ALTER TYPE {ENUM_NAME} RENAME TO {ENUM_NAME}_old")
    op.execute(f"CREATE TYPE {ENUM_NAME} AS ENUM ({old_values_sql})")
    op.execute(
        f"ALTER TABLE audit_logs ALTER COLUMN event_type TYPE {ENUM_NAME} "
        f"USING event_type::text::{ENUM_NAME}"
    )
    op.execute(f"DROP TYPE {ENUM_NAME}_old")
