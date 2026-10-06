"""add user sessions

Revision ID: 232fc184b0d7
Revises: 1ff3830ec505
Create Date: 2026-10-06 19:14:51.925775

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "232fc184b0d7"
down_revision: str | Sequence[str] | None = "1ff3830ec505"
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
    "AUDIT_LOGS_VIEWED",
    "SECURITY_EVENTS_VIEWED",
)
NEW_VALUES = ("SESSION_REVOKED", "ALL_SESSIONS_REVOKED")

# Session events map back to the generic admin access event on downgrade.
DOWNGRADE_FALLBACK = "ADMIN_ENDPOINT_ACCESSED"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False
    )

    for value in NEW_VALUES:
        op.execute(f"ALTER TYPE {ENUM_NAME} ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema.

    Dropping the table ends every session; tokens issued before the upgrade
    used a different `sub` and remain invalid. PostgreSQL cannot drop enum
    values, so the type is recreated after rows are mapped back.
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

    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_table("user_sessions")
