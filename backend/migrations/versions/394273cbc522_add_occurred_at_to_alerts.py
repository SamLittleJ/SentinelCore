"""add occurred_at to alerts

Revision ID: 394273cbc522
Revises: 1c12aa5d76da
Create Date: 2026-10-09 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "394273cbc522"
down_revision: str | Sequence[str] | None = "1c12aa5d76da"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQLAlchemy stores enum member names, so the database values are uppercase.
ALERT_TYPES = (
    "BRUTE_FORCE_DETECTED",
    "PASSWORD_SPRAY_DETECTED",
    "DORMANT_ACCOUNT_LOGIN",
    "PRIVILEGED_ROLE_GRANTED",
    "UNFAMILIAR_SIGN_IN",
)


def upgrade() -> None:
    """Upgrade schema.

    Existing alerts get the time they were raised: the time of the event that
    raised them was not kept, and for events recorded as they happened it is
    the same moment.
    """
    op.add_column(
        "security_events",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    )
    alert_types_sql = ", ".join(f"'{value}'" for value in ALERT_TYPES)
    op.execute(
        "UPDATE security_events SET occurred_at = created_at "
        f"WHERE event_type IN ({alert_types_sql})"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("security_events", "occurred_at")
