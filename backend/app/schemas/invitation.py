from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.models.user import UserRole
from app.schemas.user import NewPassword, NormalizedEmail, Username


def _not_owner(role: UserRole) -> UserRole:
    # The owner is created once, from the command line, never invited.
    if role == UserRole.OWNER:
        raise ValueError("The owner role cannot be offered in an invitation")
    return role


InvitedRole = Annotated[UserRole, AfterValidator(_not_owner)]

# Well above a real token (about 60 characters); caps the work per request.
InvitationToken = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: NormalizedEmail
    role: InvitedRole


class InvitationRead(BaseModel):
    id: int
    prefix: str
    email: str
    role: UserRole
    created_by_id: int
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    accepted_user_id: int | None
    revoked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class InvitationCreated(BaseModel):
    invitation: InvitationRead
    # The full token, returned only here; only its hash is stored.
    token: str


class InvitationLookup(BaseModel):
    """The token travels in the body, never in the URL, so it stays out of
    access logs."""

    model_config = ConfigDict(extra="forbid")

    token: InvitationToken


class InvitationPreview(BaseModel):
    """What the person invited sees before choosing a username and password."""

    email: str
    role: UserRole
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitationAccept(InvitationLookup):
    username: Username
    password: NewPassword
