"""lowercase user emails and usernames

Revision ID: 7242f1f7b69b
Revises: 02a6be0e0ec8
Create Date: 2026-10-06 18:20:14.697934

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7242f1f7b69b"
down_revision: str | Sequence[str] | None = "02a6be0e0ec8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("email", "username")


def upgrade() -> None:
    """Upgrade schema.

    The API now lowercases emails and usernames on input, so stored values
    must be lowercase too or existing accounts could no longer be found.
    """
    connection = op.get_bind()

    for column in COLUMNS:
        # Accounts that differ only by case cannot be merged automatically.
        conflicts = connection.execute(
            sa.text(
                f"SELECT lower({column}) FROM users "
                f"GROUP BY lower({column}) HAVING count(*) > 1"
            )
        ).scalars()
        conflicting_values = sorted(conflicts)
        if conflicting_values:
            raise RuntimeError(
                f"Cannot lowercase users.{column}: these values are used by "
                f"more than one account: {', '.join(conflicting_values)}. "
                "Resolve the duplicates manually, then rerun the migration."
            )

        op.execute(
            f"UPDATE users SET {column} = lower({column}) "
            f"WHERE {column} <> lower({column})"
        )


def downgrade() -> None:
    """Downgrade schema.

    The original casing is not stored, so it cannot be restored. Lowercase
    values remain valid under the previous revision.
    """
