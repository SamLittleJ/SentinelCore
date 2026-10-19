"""add sign-in address limit

Revision ID: 02ba8f21ff4e
Revises: 8975371eccc3
Create Date: 2026-10-15 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02ba8f21ff4e"
down_revision: str | Sequence[str] | None = "8975371eccc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# As in 5d1a3c7e9b20: the API's role, and the scope that sees every row.
APP_ROLE = "sentinelcore_app"
EVERYTHING = "current_setting('sentinelcore.everything', true) = 'on'"
POLICY = "organization_boundary"
TABLE = "sign_in_address_limits"

# SQLAlchemy stores enum member names, so the database values are uppercase.
NEW_VALUE = "LOGIN_ADDRESS_LIMITED"
SECURITY_OLD_VALUES = (
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
)
AUDIT_OLD_VALUES = (
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
    "USERS_VIEWED",
    "ACCOUNT_LOCKED",
    "ACCOUNT_UNLOCKED",
    "API_KEY_CREATED",
    "API_KEY_REVOKED",
    "API_KEYS_VIEWED",
    "INVITATION_CREATED",
    "INVITATION_REVOKED",
    "INVITATIONS_VIEWED",
    "ORGANIZATION_CREATED",
    "ORGANIZATION_RENAMED",
    "ORGANIZATION_SUSPENDED",
    "ORGANIZATION_REACTIVATED",
    "ORGANIZATIONS_VIEWED",
)
ENUMS = (
    ("security_events", "security_event_types", SECURITY_OLD_VALUES),
    ("audit_logs", "audit_event_types", AUDIT_OLD_VALUES),
)


def upgrade() -> None:
    """Upgrade schema."""
    for _, enum, _ in ENUMS:
        op.execute(f"ALTER TYPE {enum} ADD VALUE IF NOT EXISTS '{NEW_VALUE}'")

    op.create_table(
        TABLE,
        sa.Column("address", sa.String(length=45), nullable=False),
        sa.Column("tokens", sa.Float(), nullable=False),
        sa.Column("refilled_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("address"),
    )

    # Sign-in takes and gives back tokens; the cleanup deletes full buckets.
    # An address belongs to no organization, so only the scope that sees
    # every row, which sign-in and the cleanup use, may reach the table.
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {TABLE} TO {APP_ROLE}")
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY {POLICY} ON {TABLE} USING ({EVERYTHING})")


def downgrade() -> None:
    """Downgrade schema.

    Dropping the table drops its policy and privileges. PostgreSQL cannot drop
    enum values, so each type is recreated without the new one, whose rows
    are deleted: no older type means the same.
    """
    op.drop_table(TABLE)

    for table, enum, old_values in ENUMS:
        op.execute(f"DELETE FROM {table} WHERE event_type = '{NEW_VALUE}'")
        old_values_sql = ", ".join(f"'{value}'" for value in old_values)
        op.execute(f"ALTER TYPE {enum} RENAME TO {enum}_old")
        op.execute(f"CREATE TYPE {enum} AS ENUM ({old_values_sql})")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN event_type TYPE {enum} "
            f"USING event_type::text::{enum}"
        )
        op.execute(f"DROP TYPE {enum}_old")
