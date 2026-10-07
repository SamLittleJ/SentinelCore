"""add target user to events

Revision ID: 06b4f5ced4de
Revises: 85be834babe0
Create Date: 2026-10-07 12:19:54.899908

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "06b4f5ced4de"
down_revision: str | Sequence[str] | None = "85be834babe0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("security_events", "audit_logs")


def upgrade() -> None:
    """Upgrade schema.

    Existing rows keep a null target: older admin actions only name it in
    their message.
    """
    for table in TABLES:
        op.add_column(table, sa.Column("target_user_id", sa.Integer(), nullable=True))
        # PostgreSQL's default name, matching the unnamed ForeignKey in the model.
        op.create_foreign_key(
            f"{table}_target_user_id_fkey",
            table,
            "users",
            ["target_user_id"],
            ["id"],
        )
        op.create_index(
            op.f(f"ix_{table}_target_user_id"),
            table,
            ["target_user_id"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        op.drop_index(op.f(f"ix_{table}_target_user_id"), table_name=table)
        op.drop_constraint(f"{table}_target_user_id_fkey", table, type_="foreignkey")
        op.drop_column(table, "target_user_id")
