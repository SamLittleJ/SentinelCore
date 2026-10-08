"""add api keys and ingestion

Revision ID: 3acb81248c5a
Revises: da3df9063709
Create Date: 2026-10-09 00:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3acb81248c5a"
down_revision: str | Sequence[str] | None = "da3df9063709"
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
    "ACCOUNT_LOCKED",
    "ACCOUNT_UNLOCKED",
    "PASSWORD_SPRAY_DETECTED",
    "DORMANT_ACCOUNT_LOGIN",
    "PRIVILEGED_ROLE_GRANTED",
)
SECURITY_NEW_VALUES = ("API_KEY_CREATED", "API_KEY_REVOKED")
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
    "ACCOUNT_LOCKED",
    "ACCOUNT_UNLOCKED",
)
AUDIT_NEW_VALUES = ("API_KEY_CREATED", "API_KEY_REVOKED", "API_KEYS_VIEWED")

ENUMS = (
    ("security_events", SECURITY_ENUM, SECURITY_OLD_VALUES, SECURITY_NEW_VALUES),
    ("audit_logs", AUDIT_ENUM, AUDIT_OLD_VALUES, AUDIT_NEW_VALUES),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prefix"),
    )
    op.create_index(op.f("ix_api_keys_id"), "api_keys", ["id"], unique=False)
    op.add_column(
        "security_events",
        sa.Column("user_agent", sa.String(length=255), nullable=True),
    )
    for _, enum_name, _, new_values in ENUMS:
        for value in new_values:
            op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so each type is recreated without
    them. No older type means the same as the key events, so their rows are
    deleted along with the keys.
    """
    for table, enum_name, old_values, new_values in ENUMS:
        new_values_sql = ", ".join(f"'{value}'" for value in new_values)
        op.execute(f"DELETE FROM {table} WHERE event_type IN ({new_values_sql})")
        old_values_sql = ", ".join(f"'{value}'" for value in old_values)
        op.execute(f"ALTER TYPE {enum_name} RENAME TO {enum_name}_old")
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({old_values_sql})")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN event_type TYPE {enum_name} "
            f"USING event_type::text::{enum_name}"
        )
        op.execute(f"DROP TYPE {enum_name}_old")

    op.drop_column("security_events", "user_agent")
    op.drop_index(op.f("ix_api_keys_id"), table_name="api_keys")
    op.drop_table("api_keys")
