from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.models.security_event import RESERVED_SOURCES

# How long a new key lasts; every key expires.
KeyLifetimeDays = Literal[30, 90, 365]


def _not_reserved(source: str) -> str:
    # Ingested events must never pass for the application's own.
    if source in RESERVED_SOURCES:
        raise ValueError(f"'{source}' is reserved for the application's own events")
    return source


# A short lowercase label, e.g. "github" or "k8s-audit".
SourceName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=2,
        max_length=50,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    ),
    AfterValidator(_not_reserved),
]


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)
    ]
    source: SourceName
    expires_in_days: KeyLifetimeDays


class ApiKeyRead(BaseModel):
    id: int
    prefix: str
    name: str
    source: str
    created_by_id: int
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreated(BaseModel):
    api_key: ApiKeyRead
    # The full key, returned only here; only its hash is stored.
    key: str
