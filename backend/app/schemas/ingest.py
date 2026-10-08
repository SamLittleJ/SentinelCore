from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyAddress,
    StringConstraints,
    field_validator,
)

from app.schemas.user import NormalizedEmail

MAX_EVENTS_PER_REQUEST = 500
# A sender's clock may run a little ahead of ours.
MAX_CLOCK_SKEW = timedelta(minutes=5)
# Old enough to send a year of history, which the rules look back over.
MAX_EVENT_AGE = timedelta(days=365)


class IngestedEvent(BaseModel):
    """A sign-in reported by another system. The server sets the severity and
    the message; the sender only states what happened."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["login_success", "login_failed"]
    occurred_at: AwareDatetime
    email: NormalizedEmail
    ip_address: IPvAnyAddress | None = None
    user_agent: Annotated[str, StringConstraints(max_length=255)] | None = None

    @field_validator("occurred_at")
    @classmethod
    def check_occurred_at(cls, value: datetime) -> datetime:
        now = datetime.now(UTC)
        if value > now + MAX_CLOCK_SKEW:
            raise ValueError("occurred_at is in the future")
        if value < now - MAX_EVENT_AGE:
            raise ValueError("occurred_at is more than a year ago")
        return value


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: Annotated[
        list[IngestedEvent],
        Field(min_length=1, max_length=MAX_EVENTS_PER_REQUEST),
    ]


class IngestResult(BaseModel):
    # Alerts the events raised are not reported: a sender with a stolen key
    # must not learn what the rules catch.
    accepted: int
