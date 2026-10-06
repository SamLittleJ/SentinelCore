from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import app
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole
from app.services import user_service

EMAIL = "testuser@example.com"
PASSWORD = "testpassword"
LOCKED_DETAIL = "Too many failed login attempts. Try again later."


def register(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"username": "testuser", "email": EMAIL, "password": PASSWORD},
    )
    assert response.status_code == 201


def login(client: TestClient, password: str = PASSWORD, email: str = EMAIL):
    return client.post("/auth/login", json={"email": email, "password": password})


def fail_logins(client: TestClient, count: int, email: str = EMAIL) -> list[int]:
    return [
        login(client, password="wrongpassword", email=email).status_code
        for _ in range(count)
    ]


def count_security_events(db_session: Session, event_type: SecurityEventType) -> int:
    return db_session.scalar(
        select(func.count(SecurityEvent.id)).where(
            SecurityEvent.event_type == event_type
        )
    )


def shift_security_events_back(db_session: Session, minutes: int) -> None:
    """Move all recorded security events into the past to simulate elapsed time."""
    db_session.execute(
        update(SecurityEvent).values(
            created_at=SecurityEvent.created_at - timedelta(minutes=minutes)
        )
    )
    db_session.commit()


def test_threshold_failure_locks_login_and_records_incident(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)

    statuses = fail_logins(client, settings.login_max_failed_attempts - 1)
    assert statuses == [401] * (settings.login_max_failed_attempts - 1)

    response = login(client, password="wrongpassword")

    assert response.status_code == 429
    assert response.json()["detail"] == LOCKED_DETAIL
    assert response.headers["Retry-After"] == str(settings.login_lockout_minutes * 60)

    incidents = list(
        db_session.scalars(
            select(SecurityEvent).where(
                SecurityEvent.event_type == SecurityEventType.BRUTE_FORCE_DETECTED
            )
        ).all()
    )
    assert len(incidents) == 1
    assert incidents[0].severity == SecuritySeverity.INCIDENT
    assert incidents[0].email == EMAIL
    assert incidents[0].user_id is not None

    audit_messages = db_session.scalars(
        select(AuditLog.message).where(
            AuditLog.event_type == AuditEventType.LOGIN_LOCKED
        )
    ).all()
    assert audit_messages == [
        f"Login locked for email: {EMAIL} for {settings.login_lockout_minutes} "
        f"minutes after {settings.login_max_failed_attempts} failed attempts"
    ]


def test_locked_login_rejects_correct_password_without_checking_it(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register(client)
    fail_logins(client, settings.login_max_failed_attempts)

    verify_calls: list[str] = []
    monkeypatch.setattr(
        user_service,
        "verify_password",
        lambda password, hashed: verify_calls.append(password) or True,
    )

    response = login(client)

    assert response.status_code == 429
    assert response.json()["detail"] == LOCKED_DETAIL
    assert (
        0
        < int(response.headers["Retry-After"])
        <= (settings.login_lockout_minutes * 60)
    )
    assert verify_calls == []
    assert count_security_events(db_session, SecurityEventType.LOGIN_SUCCESS) == 0
    assert count_security_events(db_session, SecurityEventType.LOGIN_BLOCKED) == 1
    assert (
        count_security_events(db_session, SecurityEventType.BRUTE_FORCE_DETECTED) == 1
    )


def test_unknown_email_is_locked_like_an_existing_one(
    client: TestClient,
    db_session: Session,
) -> None:
    statuses = fail_logins(
        client, settings.login_max_failed_attempts, email="nobody@example.com"
    )

    assert statuses[-1] == 429
    assert login(client, email="nobody@example.com").status_code == 429
    assert (
        count_security_events(db_session, SecurityEventType.BRUTE_FORCE_DETECTED) == 1
    )


def test_lockout_expires(client: TestClient, db_session: Session) -> None:
    register(client)
    fail_logins(client, settings.login_max_failed_attempts)

    shift_security_events_back(db_session, settings.login_lockout_minutes + 1)

    assert login(client).status_code == 200


def test_failures_outside_window_are_not_counted(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    fail_logins(client, settings.login_max_failed_attempts - 1)

    shift_security_events_back(db_session, settings.login_failure_window_minutes + 1)

    assert fail_logins(client, 1) == [401]
    assert (
        count_security_events(db_session, SecurityEventType.BRUTE_FORCE_DETECTED) == 0
    )


def test_successful_login_resets_failure_count(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    below_threshold = settings.login_max_failed_attempts - 1

    assert fail_logins(client, below_threshold) == [401] * below_threshold
    assert login(client).status_code == 200
    assert fail_logins(client, below_threshold) == [401] * below_threshold
    assert (
        count_security_events(db_session, SecurityEventType.BRUTE_FORCE_DETECTED) == 0
    )


def test_expired_lockout_does_not_count_earlier_failures_again(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With a window longer than the lockout, failures that caused the first
    # lockout are still inside the window once it expires.
    monkeypatch.setattr(settings, "login_failure_window_minutes", 60)
    register(client)
    fail_logins(client, settings.login_max_failed_attempts)

    shift_security_events_back(db_session, settings.login_lockout_minutes + 1)

    assert fail_logins(client, 1) == [401]
    assert (
        count_security_events(db_session, SecurityEventType.BRUTE_FORCE_DETECTED) == 1
    )


def test_lockout_applies_only_to_the_attacked_email(client: TestClient) -> None:
    register(client)
    client.post(
        "/auth/register",
        json={
            "username": "otheruser",
            "email": "other@example.com",
            "password": PASSWORD,
        },
    )

    fail_logins(client, settings.login_max_failed_attempts)

    assert login(client).status_code == 429
    assert login(client, email="other@example.com").status_code == 200


def test_thresholds_come_from_settings(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "login_max_failed_attempts", 2)
    monkeypatch.setattr(settings, "login_lockout_minutes", 1)
    register(client)

    response = None
    for _ in range(2):
        response = login(client, password="wrongpassword")

    assert response is not None
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"


def test_events_record_client_ip(
    client: TestClient,
    db_session: Session,
) -> None:
    # The `client` fixture installs the test database override used here too.
    with TestClient(app, client=("203.0.113.7", 50000)) as remote_client:
        register(remote_client)
        login(remote_client)
        login(remote_client, password="wrongpassword")

    audit_ips = set(db_session.scalars(select(AuditLog.ip_address)).all())
    security_ips = set(db_session.scalars(select(SecurityEvent.ip_address)).all())
    assert audit_ips == {"203.0.113.7"}
    assert security_ips == {"203.0.113.7"}


def test_non_ip_client_host_is_stored_as_null(
    client: TestClient,
    db_session: Session,
) -> None:
    # TestClient reports its host as "testclient", which is not an IP address.
    register(client)

    assert set(db_session.scalars(select(SecurityEvent.ip_address)).all()) == {None}


def test_security_events_api_exposes_ip_address(
    client: TestClient,
    db_session: Session,
) -> None:
    with TestClient(app, client=("2001:db8::1", 50000)) as remote_client:
        register(remote_client)

    user = db_session.scalar(select(User))
    assert user is not None
    user.role = UserRole.SECURITY_ANALYST
    db_session.commit()

    token = login(client).json()["access_token"]
    response = client.get(
        "/security/events",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    registered = [
        event
        for event in response.json()["items"]
        if event["event_type"] == SecurityEventType.USER_REGISTERED
    ]
    assert registered[0]["ip_address"] == "2001:db8::1"
