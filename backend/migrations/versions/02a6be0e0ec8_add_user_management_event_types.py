"""add user management event types

Revision ID: 02a6be0e0ec8
Revises: ff842cc80db6
Create Date: 2026-10-06 18:09:57.809679

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02a6be0e0ec8"
down_revision: str | Sequence[str] | None = "ff842cc80db6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQLAlchemy stores enum member names, so the database values are uppercase.
NEW_VALUES = ("USER_ROLE_CHANGED", "USER_ACTIVATED", "USER_DEACTIVATED")

# (table, enum type, values before this revision, fallback for new values)
ENUMS = (
    (
        "audit_logs",
        "audit_event_types",
        (
            "USER_REGISTERED",
            "LOGIN_SUCCESS",
            "LOGIN_FAILED",
            "ADMIN_ENDPOINT_ACCESSED",
        ),
        "ADMIN_ENDPOINT_ACCESSED",
    ),
    (
        "security_events",
        "security_event_types",
        ("USER_REGISTERED", "LOGIN_SUCCESS", "LOGIN_FAILED", "ADMIN_ACCESS"),
        "ADMIN_ACCESS",
    ),
)


def upgrade() -> None:
    """Upgrade schema."""
    for _, enum_name, _, _ in ENUMS:
        for value in NEW_VALUES:
            op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so each type is recreated without them.
    Rows using the new values are first mapped back to the generic admin event
    they were recorded as before this revision.
    """
    new_values = ", ".join(f"'{value}'" for value in NEW_VALUES)

    for table, enum_name, old_values, fallback in ENUMS:
        old_values_sql = ", ".join(f"'{value}'" for value in old_values)

        op.execute(
            f"UPDATE {table} SET event_type = '{fallback}' "
            f"WHERE event_type IN ({new_values})"
        )
        op.execute(f"ALTER TYPE {enum_name} RENAME TO {enum_name}_old")
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({old_values_sql})")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN event_type TYPE {enum_name} "
            f"USING event_type::text::{enum_name}"
        )
        op.execute(f"DROP TYPE {enum_name}_old")
