"""add unfamiliar sign-in alert

Revision ID: 1c12aa5d76da
Revises: 3acb81248c5a
Create Date: 2026-10-09 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c12aa5d76da"
down_revision: str | Sequence[str] | None = "3acb81248c5a"
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
    "PASSWORD_SPRAY_DETECTED",
    "DORMANT_ACCOUNT_LOGIN",
    "PRIVILEGED_ROLE_GRANTED",
    "API_KEY_CREATED",
    "API_KEY_REVOKED",
)
NEW_VALUE = "UNFAMILIAR_SIGN_IN"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(f"ALTER TYPE {ENUM} ADD VALUE IF NOT EXISTS '{NEW_VALUE}'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so the type is recreated without it.
    No older type means the same as this alert, and each is derived from
    sign-ins that stay, so its rows are deleted rather than relabelled.
    """
    op.execute(f"DELETE FROM security_events WHERE event_type = '{NEW_VALUE}'")
    old_values_sql = ", ".join(f"'{value}'" for value in OLD_VALUES)
    op.execute(f"ALTER TYPE {ENUM} RENAME TO {ENUM}_old")
    op.execute(f"CREATE TYPE {ENUM} AS ENUM ({old_values_sql})")
    op.execute(
        f"ALTER TABLE security_events ALTER COLUMN event_type TYPE {ENUM} "
        f"USING event_type::text::{ENUM}"
    )
    op.execute(f"DROP TYPE {ENUM}_old")
