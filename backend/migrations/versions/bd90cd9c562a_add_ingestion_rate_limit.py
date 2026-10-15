"""add ingestion rate limit

Revision ID: bd90cd9c562a
Revises: 5d1a3c7e9b20
Create Date: 2026-10-15 10:56:22.786881

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bd90cd9c562a"
down_revision: str | Sequence[str] | None = "5d1a3c7e9b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Existing keys start with an empty bucket state, which their next batch
    reads as a full bucket. The API's role already may update `api_keys`.
    """
    op.add_column("api_keys", sa.Column("rate_tokens", sa.Float(), nullable=True))
    op.add_column(
        "api_keys",
        sa.Column("rate_refilled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("api_keys", "rate_refilled_at")
    op.drop_column("api_keys", "rate_tokens")
