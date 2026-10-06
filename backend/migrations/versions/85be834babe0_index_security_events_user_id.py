"""index security events user id

Revision ID: 85be834babe0
Revises: b4d5adf355fa
Create Date: 2026-10-06 20:17:07.766404

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "85be834babe0"
down_revision: str | Sequence[str] | None = "b4d5adf355fa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        op.f("ix_security_events_user_id"),
        "security_events",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_security_events_user_id"), table_name="security_events")
