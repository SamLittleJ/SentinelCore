"""falco alert types

Revision ID: 59ed13bc1e83
Revises: 40600bbb2d90
Create Date: 2026-11-03 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "59ed13bc1e83"
down_revision: str | Sequence[str] | None = "40600bbb2d90"
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
    "UNFAMILIAR_SIGN_IN",
    "INVITATION_CREATED",
    "INVITATION_REVOKED",
    "ORGANIZATION_CREATED",
    "ORGANIZATION_RENAMED",
    "ORGANIZATION_SUSPENDED",
    "ORGANIZATION_REACTIVATED",
    "API_KEY_VOLUME_SPIKE",
    "LOGIN_ADDRESS_LIMITED",
    "CROSS_ORGANIZATION_SPRAY_DETECTED",
    "AUDIT_CHAIN_BROKEN",
)
NEW_VALUES = (
    "CONTAINER_SHELL_DETECTED",
    "SENSITIVE_FILE_READ",
    "CONTAINER_NETWORK_TOOL",
)


def upgrade() -> None:
    """Upgrade schema."""
    for value in NEW_VALUES:
        op.execute(f"ALTER TYPE {ENUM} ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so the type is recreated without
    Falco's alerts, whose rows are deleted: no older type means the same.
    """
    new_values_sql = ", ".join(f"'{value}'" for value in NEW_VALUES)
    op.execute(
        f"DELETE FROM security_events WHERE event_type::text IN ({new_values_sql})"
    )
    old_values_sql = ", ".join(f"'{value}'" for value in OLD_VALUES)
    op.execute(f"ALTER TYPE {ENUM} RENAME TO {ENUM}_old")
    op.execute(f"CREATE TYPE {ENUM} AS ENUM ({old_values_sql})")
    op.execute(
        f"ALTER TABLE security_events ALTER COLUMN event_type TYPE {ENUM} "
        f"USING event_type::text::{ENUM}"
    )
    op.execute(f"DROP TYPE {ENUM}_old")
