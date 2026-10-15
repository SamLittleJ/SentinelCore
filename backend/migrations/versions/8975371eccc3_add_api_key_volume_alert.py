"""add api key volume alert

Revision ID: 8975371eccc3
Revises: bd90cd9c562a
Create Date: 2026-10-15 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8975371eccc3"
down_revision: str | Sequence[str] | None = "bd90cd9c562a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# As in 5d1a3c7e9b20: the API's role, and the rows a transaction may see.
APP_ROLE = "sentinelcore_app"
EVERYTHING = "current_setting('sentinelcore.everything', true) = 'on'"
ORGANIZATION = (
    "nullif(current_setting('sentinelcore.organization_id', true), '')::integer"
)
POLICY = "organization_boundary"
TABLE = "api_key_usage"

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
)
NEW_VALUE = "API_KEY_VOLUME_SPIKE"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(f"ALTER TYPE {ENUM} ADD VALUE IF NOT EXISTS '{NEW_VALUE}'")

    op.create_table(
        TABLE,
        sa.Column("api_key_id", sa.Integer(), nullable=False),
        sa.Column("hour", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("received", sa.Integer(), nullable=False),
        sa.Column("refused", sa.Integer(), nullable=False),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("api_key_id", "hour"),
    )
    op.create_index(
        op.f("ix_api_key_usage_organization_id"),
        TABLE,
        ["organization_id"],
        unique=False,
    )

    # Ingestion counts arrivals and marks alerted hours; the cleanup deletes
    # old hours. The table has no sequence: its key is the key and the hour.
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {TABLE} TO {APP_ROLE}")
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {POLICY} ON {TABLE} "
        f"USING ({EVERYTHING} OR organization_id = {ORGANIZATION})"
    )


def downgrade() -> None:
    """Downgrade schema.

    Dropping the table drops its policy and privileges. PostgreSQL cannot drop
    enum values, so the type is recreated without the alert, whose rows are
    deleted: no older type means the same.
    """
    op.drop_index(op.f("ix_api_key_usage_organization_id"), table_name=TABLE)
    op.drop_table(TABLE)

    op.execute(f"DELETE FROM security_events WHERE event_type = '{NEW_VALUE}'")
    old_values_sql = ", ".join(f"'{value}'" for value in OLD_VALUES)
    op.execute(f"ALTER TYPE {ENUM} RENAME TO {ENUM}_old")
    op.execute(f"CREATE TYPE {ENUM} AS ENUM ({old_values_sql})")
    op.execute(
        f"ALTER TABLE security_events ALTER COLUMN event_type TYPE {ENUM} "
        f"USING event_type::text::{ENUM}"
    )
    op.execute(f"DROP TYPE {ENUM}_old")
