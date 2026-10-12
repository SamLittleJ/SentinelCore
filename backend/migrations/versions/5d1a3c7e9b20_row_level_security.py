"""row-level security

Revision ID: 5d1a3c7e9b20
Revises: 98e290d25920
Create Date: 2026-10-12 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d1a3c7e9b20"
down_revision: str | Sequence[str] | None = "98e290d25920"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The API's role (app/core/row_security.py). Roles belong to the whole
# PostgreSQL server, not to one database, so it may exist already.
APP_ROLE = "sentinelcore_app"

# What the API does to each table, and nothing more. Security events and the
# audit log are only ever added to: the API cannot rewrite history.
PRIVILEGES = {
    "organizations": "SELECT, INSERT, UPDATE",
    "users": "SELECT, INSERT, UPDATE",
    "user_sessions": "SELECT, INSERT, UPDATE, DELETE",
    "security_events": "SELECT, INSERT",
    "audit_logs": "SELECT, INSERT",
    "api_keys": "SELECT, INSERT, UPDATE",
    "invitations": "SELECT, INSERT, UPDATE",
}
# The tables numbered by a sequence; sessions are numbered by a UUID.
SEQUENCES = tuple(table for table in PRIVILEGES if table != "user_sessions")

# Whether the transaction asked for every row, and which organization it
# names, if any. A setting never written reads as null and an ended one as
# '', so both name nothing.
EVERYTHING = "current_setting('sentinelcore.everything', true) = 'on'"
ORGANIZATION = (
    "nullif(current_setting('sentinelcore.organization_id', true), '')::integer"
)

# The rows each table shows: those of the named organization; a session,
# those of the accounts the transaction sees.
BOUNDARIES = {
    "organizations": f"id = {ORGANIZATION}",
    "users": f"organization_id = {ORGANIZATION}",
    "user_sessions": (
        "EXISTS (SELECT 1 FROM users WHERE users.id = user_sessions.user_id)"
    ),
    "security_events": f"organization_id = {ORGANIZATION}",
    "audit_logs": f"organization_id = {ORGANIZATION}",
    "api_keys": f"organization_id = {ORGANIZATION}",
    "invitations": f"organization_id = {ORGANIZATION}",
}
POLICY = "organization_boundary"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS;
            END IF;
        END
        $$
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    for table, privileges in PRIVILEGES.items():
        op.execute(f"GRANT {privileges} ON {table} TO {APP_ROLE}")
    for table in SEQUENCES:
        op.execute(f"GRANT USAGE ON SEQUENCE {table}_id_seq TO {APP_ROLE}")

    for table, boundary in BOUNDARIES.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # Without a TO clause the policy binds every role that does not bypass
        # row security. Its USING clause also checks the rows written.
        op.execute(
            f"CREATE POLICY {POLICY} ON {table} USING ({EVERYTHING} OR {boundary})"
        )

    # One open invitation per email in each organization, rather than in the
    # whole platform: an admin's invitation no longer revokes, or collides
    # with, another organization's, which they cannot see.
    op.drop_index("ix_invitations_open_email", table_name="invitations")
    op.create_index(
        "ix_invitations_open_email",
        "invitations",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )


def downgrade() -> None:
    # Two organizations may each hold an open invitation for one email; the
    # older is revoked, so the platform-wide index can return.
    op.execute(
        """
        UPDATE invitations SET revoked_at = now()
        WHERE accepted_at IS NULL AND revoked_at IS NULL AND id NOT IN (
            SELECT max(id) FROM invitations
            WHERE accepted_at IS NULL AND revoked_at IS NULL
            GROUP BY email
        )
        """
    )
    op.drop_index("ix_invitations_open_email", table_name="invitations")
    op.create_index(
        "ix_invitations_open_email",
        "invitations",
        ["email"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )

    for table in BOUNDARIES:
        op.execute(f"DROP POLICY {POLICY} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table in PRIVILEGES:
        op.execute(f"REVOKE ALL ON {table} FROM {APP_ROLE}")
    for table in SEQUENCES:
        op.execute(f"REVOKE ALL ON SEQUENCE {table}_id_seq FROM {APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
    # The role stays: it is the server's, and other databases on it (tests,
    # the demo) may still grant it privileges.
