"""The organization perspective: user list and detail, an account's activity,
targets of admin actions and the security summary."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole
from tests.accounts import create_account

PASSWORD = "testpassword"

# Query string values: a scalar, or a list for repeated parameters.
QueryParams = dict[str, str | int | list[str]]


def create_user(
    client: TestClient,
    db_session: Session,
    username: str,
    role: UserRole = UserRole.USER,
    is_active: bool = True,
) -> User:
    email = f"{username}@example.com"
    create_account(username, email, PASSWORD)

    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = role
    user.is_active = is_active
    db_session.commit()
    return user


def login_headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"email": f"{username}@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def clear_events(db_session: Session) -> None:
    db_session.execute(delete(AuditLog))
    db_session.execute(delete(SecurityEvent))
    db_session.commit()


def database_now(db_session: Session) -> datetime:
    return db_session.execute(select(func.now())).scalar_one()


def add_event(
    db_session: Session,
    event_type: SecurityEventType = SecurityEventType.LOGIN_FAILED,
    severity: SecuritySeverity = SecuritySeverity.WARN,
    minutes_ago: float = 0,
    user_id: int | None = None,
    target_user_id: int | None = None,
    email: str | None = None,
    ip_address: str | None = None,
) -> int:
    event = SecurityEvent(
        event_type=event_type,
        severity=severity,
        user_id=user_id,
        target_user_id=target_user_id,
        email=email,
        ip_address=ip_address,
        source="backend",
        message="seeded",
        created_at=database_now(db_session) - timedelta(minutes=minutes_ago),
    )
    db_session.add(event)
    db_session.commit()
    return event.id


def items(response) -> list[dict]:
    assert response.status_code == 200, response.json()
    return response.json()["items"]


def usernames(response) -> list[str]:
    return [user["username"] for user in items(response)]


@pytest.fixture()
def analyst_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    create_user(client, db_session, "analyst", UserRole.SECURITY_ANALYST)
    return login_headers(client, "analyst")


@pytest.mark.parametrize(
    "path",
    [
        "/admin/users",
        "/admin/users/{user_id}",
        "/admin/users/{user_id}/activity",
        "/security/summary",
    ],
)
def test_regular_user_cannot_read_organization_data(
    client: TestClient,
    db_session: Session,
    path: str,
) -> None:
    user = create_user(client, db_session, "regular")

    response = client.get(
        path.format(user_id=user.id), headers=login_headers(client, "regular")
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/admin/users",
        "/admin/users/{user_id}",
        "/admin/users/{user_id}/activity",
        "/security/summary",
    ],
)
def test_analyst_reads_organization_data(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
    path: str,
) -> None:
    user = create_user(client, db_session, "member")

    response = client.get(path.format(user_id=user.id), headers=analyst_headers)

    assert response.status_code == 200


def test_user_reads_are_audited_without_security_events(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    analyst = db_session.scalar(select(User).where(User.username == "analyst"))
    member = create_user(client, db_session, "member")
    clear_events(db_session)

    assert client.get("/admin/users?role=user", headers=analyst_headers).is_success
    assert client.get(f"/admin/users/{member.id}", headers=analyst_headers).is_success

    audit_logs = list(db_session.scalars(select(AuditLog).order_by(AuditLog.id)))
    assert [log.event_type for log in audit_logs] == [
        AuditEventType.USERS_VIEWED,
        AuditEventType.USERS_VIEWED,
    ]
    assert analyst is not None
    assert [log.user_id for log in audit_logs] == [analyst.id, analyst.id]
    assert [log.target_user_id for log in audit_logs] == [None, member.id]
    assert audit_logs[0].message == "Listed users with role=['user']"
    assert audit_logs[1].message == f"Viewed user details for user_id={member.id}"
    assert db_session.scalar(select(func.count(SecurityEvent.id))) == 0


def test_user_list_filters(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    create_user(client, db_session, "alice")
    create_user(client, db_session, "bob", UserRole.ADMIN)
    create_user(client, db_session, "carol", UserRole.SECURITY_ANALYST, False)
    create_user(client, db_session, "dan_ops")

    def query(params: QueryParams) -> set[str]:
        response = client.get("/admin/users", params=params, headers=analyst_headers)
        return set(usernames(response))

    everyone = {"analyst", "alice", "bob", "carol", "dan_ops"}
    assert query({}) == everyone
    # Case-insensitive substring of the username or the email.
    assert query({"q": " ALIC "}) == {"alice"}
    assert query({"q": "example.com"}) == everyone
    # Wildcards in the search text are literal characters.
    assert query({"q": "_"}) == {"dan_ops"}
    assert query({"q": "%"}) == set()
    assert query({"role": ["admin", "security_analyst"]}) == {
        "analyst",
        "bob",
        "carol",
    }
    assert query({"is_active": "false"}) == {"carol"}
    # Filters combine with AND.
    assert query({"role": "security_analyst", "is_active": "true"}) == {"analyst"}


def test_user_list_pages_newest_first(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    for username in ("user1", "user2", "user3", "user4"):
        create_user(client, db_session, username)

    first = client.get("/admin/users?limit=3", headers=analyst_headers)
    assert usernames(first) == ["user4", "user3", "user2"]
    cursor = first.json()["next_cursor"]
    assert cursor == items(first)[-1]["id"]

    second = client.get(
        f"/admin/users?limit=3&before_id={cursor}", headers=analyst_headers
    )
    assert usernames(second) == ["user1", "analyst"]
    assert second.json()["next_cursor"] is None


@pytest.mark.parametrize(
    "params",
    [
        {"offset": 10},
        {"role": "root"},
        {"is_active": "maybe"},
        {"q": "   "},
        {"q": "x" * 256},
        {"limit": 201},
        {"before_id": 0},
    ],
)
def test_user_list_rejects_invalid_filters(
    client: TestClient,
    analyst_headers: dict[str, str],
    params: QueryParams,
) -> None:
    response = client.get("/admin/users", params=params, headers=analyst_headers)

    assert response.status_code == 422


def test_admin_actions_can_be_filtered_by_target(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    create_user(client, db_session, "owner", UserRole.OWNER)
    target = create_user(client, db_session, "target")
    bystander = create_user(client, db_session, "bystander")
    owner_headers = login_headers(client, "owner")
    clear_events(db_session)

    for user in (target, bystander):
        response = client.patch(
            f"/admin/users/{user.id}/role",
            json={"role": "admin"},
            headers=owner_headers,
        )
        assert response.status_code == 200

    events = items(
        client.get(
            "/security/events",
            params={"target_user_id": target.id},
            headers=analyst_headers,
        )
    )
    # Newest first: the promotion to admin also raises a detection alert.
    assert [event["event_type"] for event in events] == [
        "privileged_role_granted",
        "user_role_changed",
    ]
    assert {event["target_user_id"] for event in events} == {target.id}

    audit_logs = items(
        client.get(
            "/admin/audit-logs",
            params={"target_user_id": target.id},
            headers=analyst_headers,
        )
    )
    assert [log["event_type"] for log in audit_logs] == ["user_role_changed"]
    assert audit_logs[0]["target_user_id"] == target.id


def test_target_sees_actions_on_their_account_without_the_actor_ip(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_user(client, db_session, "owner", UserRole.OWNER)
    target = create_user(client, db_session, "target")
    create_user(client, db_session, "bystander")
    action = add_event(
        db_session,
        event_type=SecurityEventType.USER_ROLE_CHANGED,
        severity=SecuritySeverity.INFO,
        user_id=owner.id,
        target_user_id=target.id,
        email=owner.email,
        ip_address="198.51.100.20",
    )

    def find_action(username: str) -> dict | None:
        response = client.get(
            "/users/me/activity", headers=login_headers(client, username)
        )
        return next((item for item in items(response) if item["id"] == action), None)

    as_target = find_action("target")
    assert as_target is not None
    assert as_target["as_target"] is True
    assert as_target["ip_address"] is None

    as_actor = find_action("owner")
    assert as_actor is not None
    assert as_actor["as_target"] is False
    assert as_actor["ip_address"] == "198.51.100.20"

    assert find_action("bystander") is None


def test_account_activity_for_operators(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    analyst = db_session.scalar(select(User).where(User.username == "analyst"))
    member = create_user(client, db_session, "member")
    other = create_user(client, db_session, "other")
    clear_events(db_session)

    own_login = add_event(
        db_session,
        event_type=SecurityEventType.LOGIN_SUCCESS,
        severity=SecuritySeverity.INFO,
        user_id=member.id,
        email=member.email,
    )
    failed_by_email = add_event(db_session, email=member.email)
    action_on_member = add_event(
        db_session,
        event_type=SecurityEventType.USER_DEACTIVATED,
        severity=SecuritySeverity.INFO,
        user_id=other.id,
        target_user_id=member.id,
        email=other.email,
    )
    add_event(db_session, user_id=other.id, email=other.email)

    response = client.get(f"/admin/users/{member.id}/activity", headers=analyst_headers)

    events = items(response)
    assert [event["id"] for event in events] == [
        action_on_member,
        failed_by_email,
        own_login,
    ]
    # Operators get the full record, message included.
    assert events[0]["message"] == "seeded"
    assert events[0]["user_id"] == other.id
    assert events[0]["target_user_id"] == member.id

    filtered = client.get(
        f"/admin/users/{member.id}/activity",
        params={"severity": "warn"},
        headers=analyst_headers,
    )
    assert [event["id"] for event in items(filtered)] == [failed_by_email]

    audit_logs = list(db_session.scalars(select(AuditLog).order_by(AuditLog.id)))
    assert analyst is not None
    assert [
        (log.event_type, log.user_id, log.target_user_id) for log in audit_logs
    ] == [
        (AuditEventType.SECURITY_EVENTS_VIEWED, analyst.id, member.id),
        (AuditEventType.SECURITY_EVENTS_VIEWED, analyst.id, member.id),
    ]
    assert audit_logs[1].message == (
        f"Viewed activity of user_id={member.id} with severity=['warn']"
    )


def test_unknown_user_detail_and_activity_return_404(
    client: TestClient,
    analyst_headers: dict[str, str],
) -> None:
    for path in ("/admin/users/9999", "/admin/users/9999/activity"):
        response = client.get(path, headers=analyst_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"


def test_security_summary(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    create_user(client, db_session, "member")
    create_user(client, db_session, "former", is_active=False)
    clear_events(db_session)
    lockout = settings.login_lockout_minutes

    # Inside the last 24 hours.
    add_event(
        db_session,
        event_type=SecurityEventType.LOGIN_SUCCESS,
        severity=SecuritySeverity.INFO,
        minutes_ago=60,
    )
    add_event(db_session, minutes_ago=10, ip_address="203.0.113.5")
    add_event(db_session, minutes_ago=20, ip_address="203.0.113.5")
    add_event(db_session, minutes_ago=30, ip_address="198.51.100.9")
    add_event(db_session, minutes_ago=40)
    add_event(
        db_session,
        event_type=SecurityEventType.BRUTE_FORCE_DETECTED,
        severity=SecuritySeverity.INCIDENT,
        minutes_ago=lockout - 1,
        email="locked@example.com",
    )
    # A lockout that has already expired.
    add_event(
        db_session,
        event_type=SecurityEventType.BRUTE_FORCE_DETECTED,
        severity=SecuritySeverity.INCIDENT,
        minutes_ago=lockout + 1,
        email="expired@example.com",
    )
    # Inside the week but not the day.
    add_event(db_session, minutes_ago=25 * 60, ip_address="203.0.113.5")
    # Older than the week.
    add_event(
        db_session,
        event_type=SecurityEventType.BRUTE_FORCE_DETECTED,
        severity=SecuritySeverity.INCIDENT,
        minutes_ago=8 * 24 * 60,
    )

    response = client.get("/security/summary", headers=analyst_headers)

    assert response.status_code == 200
    summary = response.json()
    assert summary["last_24h"] == {"info": 1, "warn": 4, "incident": 2}
    assert summary["last_7d"] == {"info": 1, "warn": 5, "incident": 2}
    assert summary["failed_logins_24h"] == 4
    assert summary["locked_logins"] == 1
    assert summary["top_failed_login_sources"] == [
        {"ip_address": "203.0.113.5", "failed_logins": 2},
        {"ip_address": "198.51.100.9", "failed_logins": 1},
    ]
    # The analyst, the member and the deactivated account.
    assert summary["users_total"] == 3
    assert summary["users_inactive"] == 1
    # Counts are not records, so loading the overview is not audited.
    assert db_session.scalar(select(func.count(AuditLog.id))) == 0


def test_security_summary_lists_the_top_five_sources(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    clear_events(db_session)
    # 192.0.2.1 fails once, 192.0.2.2 twice, and so on.
    for host in range(1, 7):
        for _ in range(host):
            add_event(db_session, ip_address=f"192.0.2.{host}")
    # Ties are ordered by address.
    add_event(db_session, ip_address="192.0.2.0")
    add_event(db_session, ip_address="192.0.2.0")

    summary = client.get("/security/summary", headers=analyst_headers).json()

    assert summary["top_failed_login_sources"] == [
        {"ip_address": "192.0.2.6", "failed_logins": 6},
        {"ip_address": "192.0.2.5", "failed_logins": 5},
        {"ip_address": "192.0.2.4", "failed_logins": 4},
        {"ip_address": "192.0.2.3", "failed_logins": 3},
        {"ip_address": "192.0.2.0", "failed_logins": 2},
    ]
    assert summary["failed_logins_24h"] == 23


def test_empty_security_summary(
    client: TestClient,
    db_session: Session,
    analyst_headers: dict[str, str],
) -> None:
    clear_events(db_session)

    summary = client.get("/security/summary", headers=analyst_headers).json()

    assert summary["last_24h"] == {"info": 0, "warn": 0, "incident": 0}
    assert summary["last_7d"] == {"info": 0, "warn": 0, "incident": 0}
    assert summary["failed_logins_24h"] == 0
    assert summary["locked_logins"] == 0
    assert summary["top_failed_login_sources"] == []
    assert summary["users_total"] == 1
