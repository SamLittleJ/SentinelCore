from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.security_event import SecurityEvent
from app.schemas.event_filters import EventFilters, EventPageFilters


def event_filter_conditions(
    model: type[AuditLog | SecurityEvent],
    filters: EventFilters,
) -> list[ColumnElement[bool]]:
    """Conditions for the user, email and IP filters of `filters`."""
    conditions: list[ColumnElement[bool]] = []
    if filters.user_id is not None:
        conditions.append(model.user_id == filters.user_id)
    if filters.email is not None:
        conditions.append(model.email == filters.email)
    if filters.ip_address is not None:
        conditions.append(model.ip_address == str(filters.ip_address))
    return conditions


def fetch_event_page[EventT: AuditLog | SecurityEvent](
    db: Session,
    model: type[EventT],
    filters: EventPageFilters,
    *conditions: ColumnElement[bool],
) -> tuple[list[EventT], int | None]:
    """Return one page of events, newest first, and the cursor for the next.

    Events are ordered by id, which follows insertion order and is unique, so
    `before_id` pages stay stable while new events are being recorded.
    `conditions` adds every filter beyond the time range and cursor.
    """
    statement = select(model).where(*conditions)

    if filters.since is not None:
        statement = statement.where(model.created_at >= filters.since)
    if filters.until is not None:
        statement = statement.where(model.created_at < filters.until)
    if filters.before_id is not None:
        statement = statement.where(model.id < filters.before_id)

    # One extra row tells whether another page exists.
    statement = statement.order_by(model.id.desc()).limit(filters.limit + 1)
    events = list(db.scalars(statement).all())

    if len(events) > filters.limit:
        events = events[: filters.limit]
        return events, events[-1].id

    return events, None
