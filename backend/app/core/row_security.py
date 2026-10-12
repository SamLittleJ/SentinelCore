"""Row-level security: PostgreSQL's own copy of the organization boundary.

The application filters every query by the reader's organization
(services/tenancy.py). The database repeats that filter on its side: each
table holding an organization's records has a policy (migration
`5d1a3c7e9b20`) that shows, and lets the application write, only the rows of
the organization the current transaction names, or every row when it names
everything. A query that forgets its filter still gets one organization's
rows only.

The transaction names them in two settings, written here at the start of
every transaction of a session from the scope the session was given. A
session given no scope names nothing and sees no rows: code that runs before
anyone has signed in, or for no one, asks for everything explicitly.

The policies bind the application's role only if it is not a superuser and
lacks BYPASSRLS: the API connects as `sentinelcore_app`, never as the owner
of the tables, who runs the migrations.
"""

from typing import Protocol

from sqlalchemy import Connection, event, text
from sqlalchemy.orm import Session, SessionTransaction

# The role the policies and privileges are written for (the migration
# creates it). The API's DATABASE_URL names it.
APP_ROLE = "sentinelcore_app"

# The transaction settings the policies read. A custom setting needs a dot in
# its name.
EVERYTHING_SETTING = "sentinelcore.everything"
ORGANIZATION_SETTING = "sentinelcore.organization_id"

_SCOPE_KEY = "row_scope"


class RowScope(Protocol):
    """What a session may see: every row, or one organization's (services/
    tenancy.py `Scope`)."""

    @property
    def everything(self) -> bool: ...

    @property
    def organization_id(self) -> int | None: ...


def restrict_rows(db: Session, scope: RowScope | None) -> None:
    """Show `db` the rows `scope` covers from now on, in the current
    transaction and every later one; None shows no rows."""
    db.info[_SCOPE_KEY] = scope
    if db.in_transaction():
        _name_scope(db.connection(), scope)


def _name_scope(connection: Connection, scope: RowScope | None) -> None:
    everything = scope is not None and scope.everything
    organization_id = None if scope is None else scope.organization_id
    # Local to the transaction, so a pooled connection keeps nothing.
    connection.execute(
        text(
            "SELECT set_config(:everything_setting, :everything, true), "
            "set_config(:organization_setting, :organization_id, true)"
        ),
        {
            "everything_setting": EVERYTHING_SETTING,
            "everything": "on" if everything else "",
            "organization_setting": ORGANIZATION_SETTING,
            "organization_id": "" if organization_id is None else str(organization_id),
        },
    )


@event.listens_for(Session, "after_begin")
def _name_scope_on_begin(
    session: Session, transaction: SessionTransaction, connection: Connection
) -> None:
    # Settings end with the transaction, and the application commits more
    # than once in a request, so every new transaction names them again.
    _name_scope(connection, session.info.get(_SCOPE_KEY))
