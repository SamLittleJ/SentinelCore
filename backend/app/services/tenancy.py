"""Which organization a record belongs to.

Every security event and audit record gets an organization when it is
written, and later reads show each organization only its own. Records about
things that belong to an organization (an invitation, an API key, an
ingested event and the alerts it raises, the organization itself) name it
explicitly. Everything else follows one rule, here:

1. an action on an account belongs to that account's organization, even
   when the platform owner takes it;
2. otherwise the record belongs to the organization of the account that
   acted or signed in;
3. otherwise, for a sign-in that names an email, to the organization of the
   account with that email;
4. otherwise to the platform, with no organization: the owner's own
   sign-ins, and failed sign-ins naming an email no account has. Guessing
   would show a company attempts on addresses that are not its own.

Reads follow the same boundary (`Scope`): a member sees their organization's
records only, and the platform owner every organization's and the
platform's, or one organization's when they name it. The database enforces it
too, through row-level security on the scope of whoever is asking.
"""

from dataclasses import dataclass

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models.user import User, UserRole


def organization_of(
    db: Session,
    user: User | None = None,
    target: User | None = None,
    email: str | None = None,
) -> int | None:
    """The organization of a record about `target`, by `user`, or naming
    `email`, by the rule above."""
    for account in (target, user):
        if account is not None:
            return account.organization_id
    if email:
        return db.scalar(select(User.organization_id).where(User.email == email))
    return None


@dataclass(frozen=True)
class Scope:
    """The records a read may return: those of one organization, or, with
    `everything`, those of every organization and of the platform."""

    organization_id: int | None = None
    everything: bool = False

    def conditions(
        self, column: InstrumentedAttribute[int | None]
    ) -> list[ColumnElement[bool]]:
        """The conditions that keep a query on `column` inside the scope."""
        if self.everything:
            return []
        return [column == self.organization_id]

    def includes(self, organization_id: int | None) -> bool:
        return self.everything or organization_id == self.organization_id


EVERYTHING = Scope(everything=True)
# The scope of code that acts for no signed-in account: sign-in itself, which
# must find an account, a session, an API key or an invitation before knowing
# its organization, and background tasks. The database shows it every row
# (core/row_security.py).
SYSTEM = EVERYTHING


def scope_of(user: User) -> Scope:
    """What `user` may read: everything for the platform owner, their own
    organization for everyone else."""
    if user.role == UserRole.OWNER:
        return EVERYTHING
    return Scope(organization_id=user.organization_id)
