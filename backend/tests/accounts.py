"""Accounts for tests.

Accounts join through invitations, which need an inviter. Most tests are about
something else, so they create accounts straight through the service an
accepted invitation uses, with the same events, in a database session of
their own.
"""

from app.models.user import UserRole
from app.schemas.user import UserCreate
from app.services.user_service import commit_account_created, stage_user
from tests.conftest import TestingSessionLocal

PASSWORD = "testpassword"


def create_account(
    username: str = "testuser",
    email: str | None = None,
    password: str = PASSWORD,
    role: UserRole = UserRole.USER,
) -> int:
    """Create an account, `<username>@example.com` unless `email` is given,
    and return its id."""
    user_in = UserCreate(
        username=username,
        email=email or f"{username}@example.com",
        password=password,
    )
    with TestingSessionLocal() as db:
        user = stage_user(db, user_in, role)
        commit_account_created(db, user, f"Account created for a test: {user.email}")
        return user.id
