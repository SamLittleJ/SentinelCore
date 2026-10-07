"""add login protection events and ip address

Revision ID: 449c22b3652c
Revises: 7242f1f7b69b
Create Date: 2026-10-06 18:25:21.875949

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "449c22b3652c"
down_revision: str | Sequence[str] | None = "7242f1f7b69b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, enum type, values before this revision, values added by it)
# SQLAlchemy stores enum member names, so the database values are uppercase.
ENUMS = (
    (
        "audit_logs",
        "audit_event_types",
        (
            "USER_REGISTERED",
            "LOGIN_SUCCESS",
            "LOGIN_FAILED",
            "ADMIN_ENDPOINT_ACCESSED",
            "USER_ROLE_CHANGED",
            "USER_ACTIVATED",
            "USER_DEACTIVATED",
        ),
        ("LOGIN_LOCKED", "LOGIN_BLOCKED"),
    ),
    (
        "security_events",
        "security_event_types",
        (
            "USER_REGISTERED",
            "LOGIN_SUCCESS",
            "LOGIN_FAILED",
            "ADMIN_ACCESS",
            "USER_ROLE_CHANGED",
            "USER_ACTIVATED",
            "USER_DEACTIVATED",
        ),
        ("BRUTE_FORCE_DETECTED", "LOGIN_BLOCKED"),
    ),
)

# Login protection events map back to the generic failed login on downgrade.
DOWNGRADE_FALLBACK = "LOGIN_FAILED"

INDEX_NAME = "ix_security_events_email_type_created"


def upgrade() -> None:
    """Upgrade schema."""
    for table, enum_name, _, new_values in ENUMS:
        for value in new_values:
            op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")
        op.add_column(table, sa.Column("ip_address", sa.String(length=45)))

    op.create_index(
        INDEX_NAME,
        "security_events",
        ["email", "event_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so each type is recreated without them
    after rows using the new values are mapped back to `LOGIN_FAILED`.
    """
    op.drop_index(INDEX_NAME, table_name="security_events")

    for table, enum_name, old_values, new_values in ENUMS:
        op.drop_column(table, "ip_address")

        new_values_sql = ", ".join(f"'{value}'" for value in new_values)
        old_values_sql = ", ".join(f"'{value}'" for value in old_values)

        op.execute(
            f"UPDATE {table} SET event_type = '{DOWNGRADE_FALLBACK}' "
            f"WHERE event_type IN ({new_values_sql})"
        )
        op.execute(f"ALTER TYPE {enum_name} RENAME TO {enum_name}_old")
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({old_values_sql})")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN event_type TYPE {enum_name} "
            f"USING event_type::text::{enum_name}"
        )
        op.execute(f"DROP TYPE {enum_name}_old")
