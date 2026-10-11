"""add organizations

Revision ID: 98e290d25920
Revises: c6ead3f94e93
Create Date: 2026-10-11 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "98e290d25920"
down_revision: str | Sequence[str] | None = "c6ead3f94e93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_VALUES = (
    "ORGANIZATION_CREATED",
    "ORGANIZATION_RENAMED",
    "ORGANIZATION_SUSPENDED",
    "ORGANIZATION_REACTIVATED",
)
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
    "API_KEY_CREATED",
    "API_KEY_REVOKED",
    "UNFAMILIAR_SIGN_IN",
    "INVITATION_CREATED",
    "INVITATION_REVOKED",
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
    "ACCOUNT_LOCKED",
    "ACCOUNT_UNLOCKED",
    "API_KEY_CREATED",
    "API_KEY_REVOKED",
    "API_KEYS_VIEWED",
    "INVITATION_CREATED",
    "INVITATION_REVOKED",
    "INVITATIONS_VIEWED",
)
ENUMS = (
    ("security_events", SECURITY_ENUM, SECURITY_OLD_VALUES, ORGANIZATION_VALUES),
    (
        "audit_logs",
        AUDIT_ENUM,
        AUDIT_OLD_VALUES,
        (*ORGANIZATION_VALUES, "ORGANIZATIONS_VIEWED"),
    ),
)
# Tables whose rows all belong to an organization once filled in.
OWNED_TABLES = ("invitations", "api_keys")
EVENT_TABLES = ("security_events", "audit_logs")

# Records about the owner's own account, which belong to the platform: the
# owner's sign-ins and sessions, and the owner's account being created.
PLATFORM_TYPES = {
    "security_events": (
        "USER_REGISTERED",
        "LOGIN_SUCCESS",
        "LOGIN_FAILED",
        "BRUTE_FORCE_DETECTED",
        "LOGIN_BLOCKED",
    ),
    "audit_logs": (
        "USER_REGISTERED",
        "LOGIN_SUCCESS",
        "LOGIN_FAILED",
        "LOGIN_LOCKED",
        "LOGIN_BLOCKED",
        "SESSION_REVOKED",
        "ALL_SESSIONS_REVOKED",
        "OTHER_SESSIONS_REVOKED",
    ),
}


def _values(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    """Upgrade schema.

    Everything already stored belongs to one company, so it moves to an
    organization named "Default", created only when there is something to
    move. The exceptions stay with the platform: the owner's own sign-ins
    and sessions, and failed sign-ins of this application that name no
    account.
    """
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"], unique=False)

    for table in ("users", *OWNED_TABLES, *EVENT_TABLES):
        op.add_column(table, sa.Column("organization_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_organization_id",
            table,
            "organizations",
            ["organization_id"],
            ["id"],
        )
        op.create_index(
            op.f(f"ix_{table}_organization_id"),
            table,
            ["organization_id"],
            unique=False,
        )

    op.execute(
        """
        INSERT INTO organizations (name, slug)
        SELECT 'Default', 'default'
        WHERE EXISTS (SELECT 1 FROM users WHERE role <> 'OWNER')
           OR EXISTS (SELECT 1 FROM invitations)
           OR EXISTS (SELECT 1 FROM api_keys)
        """
    )
    default = "(SELECT id FROM organizations WHERE slug = 'default')"
    op.execute(f"UPDATE users SET organization_id = {default} WHERE role <> 'OWNER'")
    for table in OWNED_TABLES:
        op.execute(f"UPDATE {table} SET organization_id = {default}")
    # A comparison with NULL is neither true nor false, and a row whose
    # condition is NULL is skipped, so every IN is made false when empty.
    for table in EVENT_TABLES:
        owner_ids = "SELECT id FROM users WHERE role = 'OWNER'"
        owner_emails = "SELECT email FROM users WHERE role = 'OWNER'"
        known_emails = "SELECT email FROM users"
        op.execute(
            f"""
            UPDATE {table} SET organization_id = {default}
            WHERE NOT (
                target_user_id IS NULL
                AND event_type IN ({_values(PLATFORM_TYPES[table])})
                AND (
                    COALESCE(user_id IN ({owner_ids}), false)
                    OR COALESCE(email IN ({owner_emails}), false)
                )
            )
            AND NOT (
                {"source = 'backend' AND" if table == "security_events" else ""}
                user_id IS NULL
                AND target_user_id IS NULL
                AND NOT COALESCE(email IN ({known_emails}), false)
                AND event_type IN ('LOGIN_FAILED', 'LOGIN_BLOCKED')
            )
            """
        )

    for table in OWNED_TABLES:
        op.alter_column(table, "organization_id", nullable=False)
    op.create_check_constraint(
        "ck_users_owner_has_no_organization",
        "users",
        "(role = 'OWNER') = (organization_id IS NULL)",
    )
    for _, enum_name, _, new_values in ENUMS:
        for value in new_values:
            op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL cannot drop enum values, so each type is recreated without
    them, after deleting the rows that use them. Which organization each
    record belonged to is lost: with one organization again, nothing needs
    it.
    """
    for table, enum_name, old_values, new_values in ENUMS:
        op.execute(f"DELETE FROM {table} WHERE event_type IN ({_values(new_values)})")
        op.execute(f"ALTER TYPE {enum_name} RENAME TO {enum_name}_old")
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({_values(old_values)})")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN event_type TYPE {enum_name} "
            f"USING event_type::text::{enum_name}"
        )
        op.execute(f"DROP TYPE {enum_name}_old")

    op.drop_constraint("ck_users_owner_has_no_organization", "users", type_="check")
    for table in ("users", *OWNED_TABLES, *EVENT_TABLES):
        op.drop_index(op.f(f"ix_{table}_organization_id"), table_name=table)
        op.drop_constraint(f"fk_{table}_organization_id", table, type_="foreignkey")
        op.drop_column(table, "organization_id")
    op.drop_index(op.f("ix_organizations_id"), table_name="organizations")
    op.drop_table("organizations")
