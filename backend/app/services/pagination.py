from datetime import datetime

from sqlalchemy import ColumnElement, literal, select, tuple_
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models.audit_log import AuditLog
from app.models.security_event import SecurityEvent
from app.models.user import User
from app.schemas.pagination import CursorPageFilters


def fetch_page[RowT: AuditLog | SecurityEvent | User](
    db: Session,
    model: type[RowT],
    filters: CursorPageFilters,
    *conditions: ColumnElement[bool],
    time_column: InstrumentedAttribute[datetime] | None = None,
) -> tuple[list[RowT], int | None]:
    """Return one page of rows, newest first, and the cursor for the next.

    With `time_column`, rows are ordered by that time, and by id among rows
    with the same time; without it, by id alone. Either way the order is
    total, so paging with `before_id` returns every row exactly once. The
    cursor stays the id of the last row: the next page starts after that row's
    position, looked up in the database.

    `conditions` adds every filter beyond the cursor.
    """
    statement = select(model).where(*conditions)

    if time_column is None:
        order: tuple[ColumnElement, ...] = (model.id.desc(),)
        if filters.before_id is not None:
            statement = statement.where(model.id < filters.before_id)
    else:
        order = (time_column.desc(), model.id.desc())
        if filters.before_id is not None:
            # An unknown cursor makes the comparison null, so the page is empty.
            cursor_time = (
                select(time_column).where(model.id == filters.before_id)
            ).scalar_subquery()
            statement = statement.where(
                tuple_(time_column, model.id)
                < tuple_(cursor_time, literal(filters.before_id))
            )

    # One extra row tells whether another page exists.
    statement = statement.order_by(*order).limit(filters.limit + 1)
    rows = list(db.scalars(statement).all())

    if len(rows) > filters.limit:
        rows = rows[: filters.limit]
        return rows, rows[-1].id

    return rows, None
