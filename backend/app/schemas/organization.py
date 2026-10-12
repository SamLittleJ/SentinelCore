from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

OrganizationName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)
]
# Lowercase letters, digits and inner hyphens, e.g. "acme" or "globex-eu".
OrganizationSlug = Annotated[
    str,
    StringConstraints(
        min_length=2, max_length=40, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    ),
]


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: OrganizationName
    slug: OrganizationSlug


class OrganizationRename(BaseModel):
    """Only the name changes: the slug stays, so links and filters keep
    working."""

    model_config = ConfigDict(extra="forbid")

    name: OrganizationName


class OrganizationRead(BaseModel):
    id: int
    name: str
    slug: str
    created_at: datetime
    suspended_at: datetime | None
    # Accounts that belong to it, active or not.
    members: int
