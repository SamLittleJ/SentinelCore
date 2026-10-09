from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole
from tests.accounts import create_account

BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

# Query string values: a scalar, or a list for repeated parameters.
QueryParams = dict[str, str | int | list[str]]


def create_user(
    client: TestClient,
    db_session: Session,
    username: str,
    role: UserRole = UserRole.USER,
) -> User:
    email = f"{username}@example.com"
    create_account(username, email, "testpassword")

    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = role
    db_session.commit()
    return user


def login_headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"email": f"{username}@example.com", "password": "testpassword"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def clear_events(db_session: Session) -> None:
    db_session.execute(delete(AuditLog))
    db_session.execute(delete(SecurityEvent))
    db_session.commit()


@pytest.fixture()
def analyst_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    create_user(client, db_session, "analyst", UserRole.SECURITY_ANALYST)
    headers = login_headers(client, "analyst")
    # Start each test from an empty event history.
    clear_events(db_session)
    return headers


def add_security_event(
    db_session: Session,
    minutes: int = 0,
    event_type: SecurityEventType = SecurityEventType.LOGIN_FAILED,
    severity: SecuritySeverity = SecuritySeverity.WARN,
    user_id: int | None = None,
    email: str | None = None,
    ip_address: str | None = None,
) -> int:
    event = SecurityEvent(
        event_type=event_type,
        severity=severity,
        user_id=user_id,
        email=email,
        ip_address=ip_address,
        source="backend",
        message="seeded",
        created_at=BASE_TIME + timedelta(minutes=minutes),
    )
    db_session.add(event)
    db_session.commit()
    return event.id


def add_audit_log(
    db_session: Session,
    event_type: AuditEventType = AuditEventType.LOGIN_FAILED,
    email: str | None = None,
    minutes: int = 0,
) -> int:
    audit_log = AuditLog(
        event_type=event_type,
        email=email,
        message="seeded",
        created_at=BASE_TIME + timedelta(minutes=minutes),
    )
    db_session.add(audit_log)
    db_session.commit()
    return audit_log.id


def event_ids(response) -> list[int]:
    assert response.status_code == 200, response.json()
    return [item["id"] for item in response.json()["items"]]


@pytest.mark.parametrize("path", ["/admin/audit-logs", "/security/events"])
def test_regular_user_cannot_read_logs(
    client: TestClient,
    db_session: Session,
    path: str,
) -> None:
    create_user(client, db_session, "regular")

    response = client.get(path, headers=login_headers(client, "regular"))

    assert response.status_code == 403


def test_events_are_returned_newest_first_on_a_single_page(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    ids = [add_security_event(db_session, minutes=i) for i in range(3)]

    response = client.get("/security/events", headers=analyst_headers)

    assert event_ids(response) == sorted(ids, reverse=True)
    assert response.json()["next_cursor"] is None


def test_cursor_pagination_returns_every_event_once(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    ids = [add_security_event(db_session, minutes=i) for i in range(7)]

    seen: list[int] = []
    params: dict[str, int] = {"limit": 3}
    page_sizes: list[int] = []
    while True:
        response = client.get(
            "/security/events", params=params, headers=analyst_headers
        )
        page = event_ids(response)
        page_sizes.append(len(page))
        seen.extend(page)

        next_cursor = response.json()["next_cursor"]
        if next_cursor is None:
            break
        assert next_cursor == page[-1]
        params = {"limit": 3, "before_id": next_cursor}

    assert page_sizes == [3, 3, 1]
    assert seen == sorted(ids, reverse=True)


def test_events_are_listed_by_time_even_when_recorded_late(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    # An event can be recorded after newer ones, for example when it reaches
    # the system late. It is listed at the time it happened.
    recorded_first = add_security_event(db_session, minutes=30)
    recorded_late = add_security_event(db_session, minutes=10)
    newest = add_security_event(db_session, minutes=40)

    response = client.get("/security/events", headers=analyst_headers)

    assert event_ids(response) == [newest, recorded_first, recorded_late]


def test_pagination_follows_time_and_breaks_ties_by_id(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    # created_at is the transaction start time, so events recorded in order
    # can carry out-of-order or equal timestamps.
    minutes = [5, 0, 5, 3, 5, 1, 0]
    ids = [add_security_event(db_session, minutes=m) for m in minutes]
    by_time = sorted(zip(minutes, ids, strict=True), reverse=True)
    expected = [event_id for _, event_id in by_time]

    seen: list[int] = []
    params: dict[str, int] = {"limit": 2}
    while True:
        response = client.get(
            "/security/events", params=params, headers=analyst_headers
        )
        seen.extend(event_ids(response))
        next_cursor = response.json()["next_cursor"]
        if next_cursor is None:
            break
        params = {"limit": 2, "before_id": next_cursor}

    assert seen == expected


def test_unknown_cursor_returns_an_empty_page(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    add_security_event(db_session)

    response = client.get(
        "/security/events", params={"before_id": 999999}, headers=analyst_headers
    )

    assert event_ids(response) == []
    assert response.json()["next_cursor"] is None


def test_audit_logs_are_listed_by_time(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    recorded_first = add_audit_log(db_session, minutes=30)
    recorded_late = add_audit_log(db_session, minutes=10)

    first = client.get(
        "/admin/audit-logs", params={"limit": 1}, headers=analyst_headers
    )
    second = client.get(
        "/admin/audit-logs",
        params={"limit": 1, "before_id": first.json()["next_cursor"]},
        headers=analyst_headers,
    )

    assert event_ids(first) == [recorded_first]
    assert event_ids(second) == [recorded_late]


def test_pages_stay_stable_when_new_events_arrive(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    ids = [add_security_event(db_session, minutes=i) for i in range(4)]

    first = client.get("/security/events", params={"limit": 2}, headers=analyst_headers)
    newer_id = add_security_event(db_session, minutes=10)
    second = client.get(
        "/security/events",
        params={"limit": 2, "before_id": first.json()["next_cursor"]},
        headers=analyst_headers,
    )

    assert event_ids(first) == [ids[3], ids[2]]
    assert event_ids(second) == [ids[1], ids[0]]
    assert newer_id not in event_ids(second)


def test_security_event_filters(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    target = create_user(client, db_session, "target")
    clear_events(db_session)

    failed = add_security_event(
        db_session, email="target@example.com", ip_address="203.0.113.7"
    )
    incident = add_security_event(
        db_session,
        event_type=SecurityEventType.BRUTE_FORCE_DETECTED,
        severity=SecuritySeverity.INCIDENT,
        user_id=target.id,
        email="target@example.com",
        ip_address="2001:db8::1",
    )
    success = add_security_event(
        db_session,
        event_type=SecurityEventType.LOGIN_SUCCESS,
        severity=SecuritySeverity.INFO,
        user_id=target.id,
        email="other@example.com",
    )

    def query(params: QueryParams) -> set[int]:
        return set(
            event_ids(
                client.get("/security/events", params=params, headers=analyst_headers)
            )
        )

    assert query({"event_type": ["login_failed", "brute_force_detected"]}) == {
        failed,
        incident,
    }
    assert query({"severity": ["incident", "info"]}) == {incident, success}
    assert query({"user_id": target.id}) == {incident, success}
    assert query({"email": "TARGET@Example.com"}) == {failed, incident}
    assert query({"ip_address": "203.0.113.7"}) == {failed}
    # A non-canonical IPv6 form matches the canonical stored value.
    assert query({"ip_address": "2001:DB8:0:0::1"}) == {incident}
    # Filters combine with AND.
    assert query({"email": "target@example.com", "severity": "incident"}) == {incident}


def test_time_range_is_half_open(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    add_security_event(db_session, minutes=0)
    middle = add_security_event(db_session, minutes=10)
    add_security_event(db_session, minutes=20)

    response = client.get(
        "/security/events",
        params={
            "since": (BASE_TIME + timedelta(minutes=10)).isoformat(),
            "until": (BASE_TIME + timedelta(minutes=20)).isoformat(),
        },
        headers=analyst_headers,
    )

    assert event_ids(response) == [middle]


@pytest.mark.parametrize(
    "params",
    [
        {"since": "2026-01-02T00:00:00Z", "until": "2026-01-01T00:00:00Z"},
        {"since": "2026-01-01T00:00:00Z", "until": "2026-01-01T00:00:00Z"},
        {"since": "2026-01-01T00:00:00"},
        {"event_typ": "login_failed"},
        {"event_type": "not_a_type"},
        {"severity": "critical"},
        {"limit": 0},
        {"limit": 201},
        {"before_id": 0},
        {"ip_address": "not-an-ip"},
    ],
)
def test_invalid_query_returns_422(
    client: TestClient,
    analyst_headers: dict[str, str],
    params: QueryParams,
) -> None:
    response = client.get("/security/events", params=params, headers=analyst_headers)

    assert response.status_code == 422


def test_audit_log_filters(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    failed = add_audit_log(db_session, email="target@example.com")
    locked = add_audit_log(
        db_session, event_type=AuditEventType.LOGIN_LOCKED, email="target@example.com"
    )
    add_audit_log(db_session, email="other@example.com")

    response = client.get(
        "/admin/audit-logs",
        params={
            "event_type": ["login_failed", "login_locked"],
            "email": "target@example.com",
        },
        headers=analyst_headers,
    )

    assert event_ids(response) == [locked, failed]


def test_viewing_audit_logs_is_audited_but_not_returned(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    seeded = add_audit_log(db_session)

    response = client.get(
        "/admin/audit-logs",
        params={"event_type": "login_failed", "limit": 10},
        headers=analyst_headers,
    )

    assert event_ids(response) == [seeded]

    view_logs = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.AUDIT_LOGS_VIEWED
            )
        ).all()
    )
    assert len(view_logs) == 1
    assert view_logs[0].email == "analyst@example.com"
    assert view_logs[0].message == (
        "Viewed audit logs with event_type=['login_failed'], limit=10"
    )


def test_viewing_security_events_is_audited_without_a_security_event(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    response = client.get("/security/events", headers=analyst_headers)

    assert event_ids(response) == []

    messages = db_session.scalars(
        select(AuditLog.message).where(
            AuditLog.event_type == AuditEventType.SECURITY_EVENTS_VIEWED
        )
    ).all()
    assert messages == ["Viewed security events with no filters"]
    assert db_session.scalar(select(SecurityEvent.id)) is None
