"""add account lock

Revision ID: 2b5ba1e0d7df
Revises: 370d6e54e7cf
Create Date: 2026-10-07 12:41:52.237155

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2b5ba1e0d7df"
down_revision: str | Sequence[str] | None = "370d6e54e7cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQLAlchemy stores enum member names, so the database values are uppercase.
SECURITY_ENUM = "security_event_types"
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
)
AUDIT_ENUM = "audit_event_types"
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
)

# The closest older events: a lock always revoked the account's sessions, and
# an unlock gives access back like a reactivation.
SECURITY_FALLBACKS = {
    "ACCOUNT_LOCKED": "USER_SESSIONS_REVOKED",
    "ACCOUNT_UNLOCKED": "USER_ACTIVATED",
}
AUDIT_FALLBACKS = {
    "ACCOUNT_LOCKED": "ALL_SESSIONS_REVOKED",
    "ACCOUNT_UNLOCKED": "USER_ACTIVATED",
}

ENUMS = (
    ("security_events", SECURITY_ENUM, SECURITY_OLD_VALUES, SECURITY_FALLBACKS),
    ("audit_logs", AUDIT_ENUM, AUDIT_OLD_VALUES, AUDIT_FALLBACKS),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    for _, enum_name, _, fallbacks in ENUMS:
        for value in fallbacks:
            op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so each type is recreated without
    them after rows using them are mapped back.
    """
    for table, enum_name, old_values, fallbacks in ENUMS:
        for value, fallback in fallbacks.items():
            op.execute(
                f"UPDATE {table} SET event_type = '{fallback}' "
                f"WHERE event_type = '{value}'"
            )
        old_values_sql = ", ".join(f"'{value}'" for value in old_values)
        op.execute(f"ALTER TYPE {enum_name} RENAME TO {enum_name}_old")
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({old_values_sql})")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN event_type TYPE {enum_name} "
            f"USING event_type::text::{enum_name}"
        )
        op.execute(f"DROP TYPE {enum_name}_old")

    op.drop_column("users", "locked_until")
