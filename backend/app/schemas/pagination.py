from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class Page[ItemT](BaseModel):
    """One page of results, newest first.

    `next_cursor` is the `before_id` value for the next page, or None when
    there are no more results.
    """

    items: list[ItemT]
    next_cursor: int | None


class CursorPageFilters(BaseModel):
    """Cursor and page size shared by every listing that returns a Page."""

    # Reject unknown query parameters, so a mistyped filter fails loudly
    # instead of silently returning unfiltered results.
    model_config = ConfigDict(extra="forbid")

    before_id: int | None = Field(default=None, ge=1)
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    def describe(self) -> str:
        """Summarize the filters actually used, for audit messages."""
        used = self.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        if not used:
            return "no filters"
        return ", ".join(f"{name}={value}" for name, value in sorted(used.items()))
