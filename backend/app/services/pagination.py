from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.security_event import SecurityEvent
from app.models.user import User
from app.schemas.pagination import CursorPageFilters


def fetch_page[RowT: AuditLog | SecurityEvent | User](
    db: Session,
    model: type[RowT],
    filters: CursorPageFilters,
    *conditions: ColumnElement[bool],
) -> tuple[list[RowT], int | None]:
    """Return one page of rows, newest first, and the cursor for the next.

    Rows are ordered by id, which follows insertion order and is unique, so
    `before_id` pages stay stable while new rows are being added.
    `conditions` adds every filter beyond the cursor.
    """
    statement = select(model).where(*conditions)

    if filters.before_id is not None:
        statement = statement.where(model.id < filters.before_id)

    # One extra row tells whether another page exists.
    statement = statement.order_by(model.id.desc()).limit(filters.limit + 1)
    rows = list(db.scalars(statement).all())

    if len(rows) > filters.limit:
        rows = rows[: filters.limit]
        return rows, rows[-1].id

    return rows, None
