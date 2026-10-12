"""Accounts for tests.

Accounts join through invitations, which need an inviter. Most tests are about
something else, so they create accounts straight through the service an
accepted invitation uses, with the same events, in a database session of
their own that sees every organization.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.services.user_service import commit_account_created, stage_user
from tests.conftest import system_session

PASSWORD = "testpassword"
# The organization test accounts join unless a test names another.
TEST_ORGANIZATION = "test"


def organization_id(db: Session, slug: str = TEST_ORGANIZATION) -> int:
    """The id of the organization `slug`, created on first use."""
    found = db.scalar(select(Organization.id).where(Organization.slug == slug))
    if found is not None:
        return found
    organization = Organization(name=slug.capitalize(), slug=slug)
    db.add(organization)
    db.commit()
    return organization.id


def create_account(
    username: str = "testuser",
    email: str | None = None,
    password: str = PASSWORD,
    role: UserRole = UserRole.USER,
    organization: str = TEST_ORGANIZATION,
) -> int:
    """Create an account, `<username>@example.com` unless `email` is given,
    in `organization` (the owner in none), and return its id."""
    user_in = UserCreate(
        username=username,
        email=email or f"{username}@example.com",
        password=password,
    )
    with system_session() as db:
        in_organization = (
            None if role == UserRole.OWNER else organization_id(db, organization)
        )
        user = stage_user(db, user_in, role, in_organization)
        commit_account_created(db, user, f"Account created for a test: {user.email}")
        return user.id


def set_role(user: User, role: UserRole) -> None:
    """Give `user` `role`, as tests do straight in the database. The platform
    owner belongs to no organization, which the database enforces."""
    user.role = role
    if role == UserRole.OWNER:
        user.organization_id = None


def org_id_for_tests() -> int:
    """The organization test accounts join, created on first use."""
    with system_session() as db:
        return organization_id(db)
