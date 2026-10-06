from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.cookies import CSRF_COOKIE, CSRF_HEADER
from app.main import app
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User

PASSWORD = "testpassword"

# Query string values: a scalar, or a list for repeated parameters.
QueryParams = dict[str, str | int | list[str]]


def register(client: TestClient, username: str = "testuser") -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201


def login(client: TestClient, username: str = "testuser") -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"email": f"{username}@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def failed_login(client: TestClient, username: str = "testuser") -> None:
    response = client.post(
        "/auth/login",
        json={"email": f"{username}@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def get_user(db_session: Session, username: str = "testuser") -> User:
    user = db_session.scalar(select(User).where(User.username == username))
    assert user is not None
    return user


def activity(
    client: TestClient,
    headers: dict[str, str],
    params: QueryParams | None = None,
) -> dict:
    response = client.get("/users/me/activity", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def event_types(page: dict) -> list[str]:
    return [item["event_type"] for item in page["items"]]


def audit_log_count(db_session: Session) -> int:
    return db_session.execute(select(func.count(AuditLog.id))).scalar_one()


# My activity


def test_activity_requires_authentication(client: TestClient) -> None:
    assert client.get("/users/me/activity").status_code == 401


def test_activity_lists_own_events_newest_first(client: TestClient) -> None:
    register(client)
    headers = login(client)

    page = activity(client, headers)

    assert event_types(page) == ["login_success", "user_registered"]
    assert page["next_cursor"] is None


def test_activity_includes_failed_logins_that_only_name_my_email(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    failed_login(client)
    headers = login(client)

    # A wrong password does not link the attempt to the account.
    failed = db_session.scalar(
        select(SecurityEvent).where(
            SecurityEvent.event_type == SecurityEventType.LOGIN_FAILED
        )
    )
    assert failed is not None
    assert failed.user_id is None

    assert event_types(activity(client, headers)) == [
        "login_success",
        "login_failed",
        "user_registered",
    ]


def test_activity_hides_other_accounts_events(client: TestClient) -> None:
    register(client, "alice")
    register(client, "bob")
    login(client, "bob")
    failed_login(client, "bob")
    headers = login(client, "alice")

    assert event_types(activity(client, headers)) == [
        "login_success",
        "user_registered",
    ]


def test_activity_hides_attempts_made_before_the_account_existed(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    user = get_user(db_session)
    db_session.add(
        SecurityEvent(
            event_type=SecurityEventType.LOGIN_FAILED,
            severity=SecuritySeverity.WARN,
            email=user.email,
            source="backend",
            message="seeded",
            created_at=user.created_at - timedelta(days=1),
        )
    )
    db_session.commit()
    headers = login(client)

    assert "login_failed" not in event_types(activity(client, headers))


def test_activity_items_leave_out_operator_details(client: TestClient) -> None:
    register(client)
    headers = login(client)

    item = activity(client, headers)["items"][0]

    assert set(item) == {"id", "event_type", "severity", "ip_address", "created_at"}


def test_activity_filters_by_severity_and_event_type(client: TestClient) -> None:
    register(client)
    failed_login(client)
    headers = login(client)

    warnings = activity(client, headers, {"severity": ["warn", "incident"]})
    logins = activity(
        client, headers, {"event_type": ["login_success", "login_failed"]}
    )

    assert event_types(warnings) == ["login_failed"]
    assert event_types(logins) == ["login_success", "login_failed"]


def test_activity_pages_with_a_cursor(client: TestClient) -> None:
    register(client)
    headers = login(client)
    login(client)

    first = activity(client, headers, {"limit": 2})
    second = activity(client, headers, {"limit": 2, "before_id": first["next_cursor"]})

    assert event_types(first) == ["login_success", "login_success"]
    assert first["next_cursor"] == first["items"][-1]["id"]
    assert event_types(second) == ["user_registered"]
    assert second["next_cursor"] is None


@pytest.mark.parametrize(
    "params",
    [
        {"user_id": 1},
        {"email": "someone@example.com"},
        {"ip_address": "127.0.0.1"},
        {"severity": "critical"},
        {"limit": 0},
    ],
)
def test_activity_rejects_other_filters(
    client: TestClient,
    params: QueryParams,
) -> None:
    register(client)
    headers = login(client)

    response = client.get("/users/me/activity", headers=headers, params=params)

    assert response.status_code == 422


def test_reading_my_activity_is_not_audited(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    headers = login(client)
    before = audit_log_count(db_session)

    activity(client, headers)

    assert audit_log_count(db_session) == before


# Revoking my other sessions


def test_revoking_other_sessions_keeps_the_current_one(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    current = login(client)
    others = [login(client), login(client)]

    response = client.delete("/users/me/sessions", headers=current)

    assert response.status_code == 200
    assert response.json() == {"revoked_sessions": 2}
    assert client.get("/users/me", headers=current).status_code == 200
    for headers in others:
        assert client.get("/users/me", headers=headers).status_code == 401

    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.event_type == AuditEventType.OTHER_SESSIONS_REVOKED
        )
    )
    assert audit is not None
    assert audit.user_id == get_user(db_session).id
    assert audit.message == "User revoked 2 other session(s)"


def test_revoking_other_sessions_leaves_other_users_signed_in(
    client: TestClient,
) -> None:
    register(client, "alice")
    register(client, "bob")
    bob = login(client, "bob")
    alice = login(client, "alice")

    response = client.delete("/users/me/sessions", headers=alice)

    assert response.json() == {"revoked_sessions": 0}
    assert client.get("/users/me", headers=bob).status_code == 200


def test_revoking_other_sessions_requires_authentication(client: TestClient) -> None:
    assert client.delete("/users/me/sessions").status_code == 401


@pytest.fixture()
def browser(client: TestClient) -> Generator[TestClient]:
    """A client on https, so Secure cookies are stored and sent back.

    Depends on `client` for the test database override.
    """
    with TestClient(app, base_url="https://testserver") as browser_client:
        yield browser_client


def test_browser_revoke_of_other_sessions_requires_csrf(browser: TestClient) -> None:
    register(browser)
    other = login(browser)
    response = browser.post(
        "/auth/session",
        json={"email": "testuser@example.com", "password": PASSWORD},
    )
    assert response.status_code == 204

    assert browser.delete("/users/me/sessions").status_code == 403
    assert browser.get("/users/me", headers=other).status_code == 200

    response = browser.delete(
        "/users/me/sessions",
        headers={CSRF_HEADER: browser.cookies[CSRF_COOKIE]},
    )
    assert response.json() == {"revoked_sessions": 1}
    assert browser.get("/users/me", headers=other).status_code == 401
