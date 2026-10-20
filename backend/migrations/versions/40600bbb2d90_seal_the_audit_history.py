"""seal the audit history

Revision ID: 40600bbb2d90
Revises: a5eaa2f50fd1
Create Date: 2026-10-20 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.audit_seal import GENESIS, seal
from app.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "40600bbb2d90"
down_revision: str | Sequence[str] | None = "a5eaa2f50fd1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQLAlchemy stores enum member names, so the database values are uppercase.
ENUM = "security_event_types"
OLD_VALUES = (
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
    "API_KEY_CREATED",
    "API_KEY_REVOKED",
    "UNFAMILIAR_SIGN_IN",
    "INVITATION_CREATED",
    "INVITATION_REVOKED",
    "ORGANIZATION_CREATED",
    "ORGANIZATION_RENAMED",
    "ORGANIZATION_SUSPENDED",
    "ORGANIZATION_REACTIVATED",
    "API_KEY_VOLUME_SPIKE",
    "LOGIN_ADDRESS_LIMITED",
    "CROSS_ORGANIZATION_SPRAY_DETECTED",
)
NEW_VALUE = "AUDIT_CHAIN_BROKEN"


def upgrade() -> None:
    """Upgrade schema.

    The history already recorded is sealed in the order it was written, one
    chain per organization and one for the platform, before the columns
    become required.
    """
    op.add_column("audit_logs", sa.Column("chain_seq", sa.Integer(), nullable=True))
    op.add_column(
        "audit_logs", sa.Column("chain_hash", sa.String(length=64), nullable=True)
    )

    connection = op.get_bind()
    records = connection.execute(
        sa.text(
            "SELECT id, event_type::text AS event_type, user_id, target_user_id, "
            "organization_id, email, ip_address, message, created_at "
            "FROM audit_logs ORDER BY organization_id NULLS FIRST, id"
        )
    ).all()
    key = settings.audit_chain_key.get_secret_value().encode()
    seals = []
    chain: object = object()  # No record's organization.
    chain_seq, previous = 0, GENESIS
    for record in records:
        if record.organization_id != chain:
            chain, chain_seq, previous = record.organization_id, 0, GENESIS
        chain_seq += 1
        previous = seal(
            key,
            previous=previous,
            chain_seq=chain_seq,
            event_type=record.event_type,
            user_id=record.user_id,
            target_user_id=record.target_user_id,
            organization_id=record.organization_id,
            email=record.email,
            ip_address=record.ip_address,
            message=record.message,
            created_at=record.created_at,
        )
        seals.append({"id": record.id, "chain_seq": chain_seq, "chain_hash": previous})
    if seals:
        connection.execute(
            sa.text(
                "UPDATE audit_logs SET chain_seq = :chain_seq, "
                "chain_hash = :chain_hash WHERE id = :id"
            ),
            seals,
        )

    op.alter_column("audit_logs", "chain_seq", nullable=False)
    op.alter_column("audit_logs", "chain_hash", nullable=False)
    op.create_unique_constraint(
        "uq_audit_logs_chain",
        "audit_logs",
        ["organization_id", "chain_seq"],
        postgresql_nulls_not_distinct=True,
    )
    op.execute(f"ALTER TYPE {ENUM} ADD VALUE IF NOT EXISTS '{NEW_VALUE}'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so the type is recreated without the
    alert, whose rows are deleted: no older type means the same.
    """
    op.execute(f"DELETE FROM security_events WHERE event_type = '{NEW_VALUE}'")
    old_values_sql = ", ".join(f"'{value}'" for value in OLD_VALUES)
    op.execute(f"ALTER TYPE {ENUM} RENAME TO {ENUM}_old")
    op.execute(f"CREATE TYPE {ENUM} AS ENUM ({old_values_sql})")
    op.execute(
        f"ALTER TABLE security_events ALTER COLUMN event_type TYPE {ENUM} "
        f"USING event_type::text::{ENUM}"
    )
    op.execute(f"DROP TYPE {ENUM}_old")

    op.drop_constraint("uq_audit_logs_chain", "audit_logs", type_="unique")
    op.drop_column("audit_logs", "chain_hash")
    op.drop_column("audit_logs", "chain_seq")
