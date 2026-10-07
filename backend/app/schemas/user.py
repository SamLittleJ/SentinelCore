import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    StrictBool,
    StringConstraints,
)

from app.models.user import UserRole

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50  # matches users.username String(50)
PASSWORD_MIN_LENGTH = 12
# Caps the work spent hashing a single request; well above any real password.
PASSWORD_MAX_LENGTH = 128

# Usernames are stored lowercase so "Admin" and "admin" cannot coexist.
Username = Annotated[
    str,
    StringConstraints(
        to_lower=True,
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        pattern=r"^[A-Za-z0-9_.-]+$",
    ),
]

# Emails are stored lowercase so lookups and uniqueness ignore case.
NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]

NewPassword = Annotated[
    str,
    StringConstraints(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH),
]

# No minimum at login: accounts created before the policy must still sign in.
LoginPassword = Annotated[str, StringConstraints(max_length=PASSWORD_MAX_LENGTH)]


class UserCreate(BaseModel):
    username: Username
    email: NormalizedEmail
    password: NewPassword


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: NormalizedEmail
    password: LoginPassword


class Token(BaseModel):
    access_token: str
    token_type: str
    # Seconds until the token expires, as in the OAuth2 token response.
    expires_in: int


class SessionRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    ip_address: str | None
    user_agent: str | None
    # True for the session of the token used in the request.
    current: bool


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserStatusUpdate(BaseModel):
    is_active: StrictBool


class SessionsRevoked(BaseModel):
    revoked_sessions: int
