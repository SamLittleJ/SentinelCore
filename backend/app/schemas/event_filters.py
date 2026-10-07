from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    IPvAnyAddress,
    StringConstraints,
    model_validator,
)

from app.schemas.pagination import CursorPageFilters


class EventPageFilters(CursorPageFilters):
    """Time range and cursor shared by every event listing."""

    # Half-open interval: since <= created_at < until.
    since: AwareDatetime | None = None
    until: AwareDatetime | None = None

    @model_validator(mode="after")
    def check_time_range(self) -> Self:
        if self.since and self.until and self.since >= self.until:
            raise ValueError("since must be earlier than until")
        return self


class EventFilters(EventPageFilters):
    """Query filters shared by audit logs and security events."""

    user_id: int | None = None
    target_user_id: int | None = None
    email: Annotated[str, StringConstraints(to_lower=True, max_length=255)] | None = (
        None
    )
    ip_address: IPvAnyAddress | None = None
