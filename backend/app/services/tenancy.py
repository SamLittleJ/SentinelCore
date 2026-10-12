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
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


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
