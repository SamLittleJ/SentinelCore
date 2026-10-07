from pydantic import BaseModel


class Page[ItemT](BaseModel):
    """One page of results, newest first.

    `next_cursor` is the `before_id` value for the next page, or None when
    there are no more results.
    """

    items: list[ItemT]
    next_cursor: int | None
