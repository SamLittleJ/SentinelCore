"""add detection alerts

Revision ID: da3df9063709
Revises: fae4d7e28eb6
Create Date: 2026-10-08 23:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "da3df9063709"
down_revision: str | Sequence[str] | None = "fae4d7e28eb6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQLAlchemy stores enum member names, so the database values are uppercase.
ENUM = "security_event_types"
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
    "USER_SESSIONS_REVOKED",
    "ACCOUNT_LOCKED",
    "ACCOUNT_UNLOCKED",
)
NEW_VALUES = (
    "PASSWORD_SPRAY_DETECTED",
    "DORMANT_ACCOUNT_LOGIN",
    "PRIVILEGED_ROLE_GRANTED",
)
INDEX = "ix_security_events_ip_type_created"


def upgrade() -> None:
    """Upgrade schema."""
    for value in NEW_VALUES:
        op.execute(f"ALTER TYPE {ENUM} ADD VALUE IF NOT EXISTS '{value}'")
    op.create_index(
        INDEX,
        "security_events",
        ["ip_address", "event_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so the type is recreated without them.
    No older type means the same as these alerts, and each is derived from
    events that stay, so their rows are deleted rather than relabelled.
    """
    op.drop_index(INDEX, table_name="security_events")
    new_values_sql = ", ".join(f"'{value}'" for value in NEW_VALUES)
    op.execute(f"DELETE FROM security_events WHERE event_type IN ({new_values_sql})")
    old_values_sql = ", ".join(f"'{value}'" for value in OLD_VALUES)
    op.execute(f"ALTER TYPE {ENUM} RENAME TO {ENUM}_old")
    op.execute(f"CREATE TYPE {ENUM} AS ENUM ({old_values_sql})")
    op.execute(
        f"ALTER TABLE security_events ALTER COLUMN event_type TYPE {ENUM} "
        f"USING event_type::text::{ENUM}"
    )
    op.execute(f"DROP TYPE {ENUM}_old")
