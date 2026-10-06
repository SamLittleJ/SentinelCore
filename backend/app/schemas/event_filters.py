from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyAddress,
    StringConstraints,
    model_validator,
)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class EventFilters(BaseModel):
    """Query filters shared by audit logs and security events."""

    # Reject unknown query parameters, so a mistyped filter fails loudly
    # instead of silently returning unfiltered results.
    model_config = ConfigDict(extra="forbid")

    user_id: int | None = None
    email: Annotated[str, StringConstraints(to_lower=True, max_length=255)] | None = (
        None
    )
    ip_address: IPvAnyAddress | None = None
    # Half-open interval: since <= created_at < until.
    since: AwareDatetime | None = None
    until: AwareDatetime | None = None
    before_id: int | None = Field(default=None, ge=1)
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    @model_validator(mode="after")
    def check_time_range(self) -> Self:
        if self.since and self.until and self.since >= self.until:
            raise ValueError("since must be earlier than until")
        return self

    def describe(self) -> str:
        """Summarize the filters actually used, for audit messages."""
        used = self.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        if not used:
            return "no filters"
        return ", ".join(f"{name}={value}" for name, value in sorted(used.items()))
