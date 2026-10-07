"""index events by time

Revision ID: fae4d7e28eb6
Revises: 2b5ba1e0d7df
Create Date: 2026-10-07 13:21:55.072028

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fae4d7e28eb6"
down_revision: str | Sequence[str] | None = "2b5ba1e0d7df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The listings are ordered by (created_at, id), newest first.
INDEXES = (
    ("ix_security_events_created_at_id", "security_events"),
    ("ix_audit_logs_created_at_id", "audit_logs"),
)


def upgrade() -> None:
    """Upgrade schema."""
    for name, table in INDEXES:
        op.create_index(name, table, ["created_at", "id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    for name, table in INDEXES:
        op.drop_index(name, table_name=table)
