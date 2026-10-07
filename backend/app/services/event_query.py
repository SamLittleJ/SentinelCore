from sqlalchemy import ColumnElement
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.security_event import SecurityEvent
from app.schemas.event_filters import EventFilters, EventPageFilters
from app.services.pagination import fetch_page


def event_filter_conditions(
    model: type[AuditLog | SecurityEvent],
    filters: EventFilters,
) -> list[ColumnElement[bool]]:
    """Conditions for the user, target, email and IP filters of `filters`."""
    conditions: list[ColumnElement[bool]] = []
    if filters.user_id is not None:
        conditions.append(model.user_id == filters.user_id)
    if filters.target_user_id is not None:
        conditions.append(model.target_user_id == filters.target_user_id)
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

    `conditions` adds every filter beyond the time range and cursor.
    """
    time_conditions: list[ColumnElement[bool]] = []
    if filters.since is not None:
        time_conditions.append(model.created_at >= filters.since)
    if filters.until is not None:
        time_conditions.append(model.created_at < filters.until)

    return fetch_page(db, model, filters, *conditions, *time_conditions)
