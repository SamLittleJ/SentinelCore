from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.api_key import ApiKey
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole

PASSWORD = "testpassword"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0"


def register(client: TestClient, username: str) -> str:
    email = f"{username}@example.com"
    response = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    return email


@pytest.fixture()
def key(client: TestClient, db_session: Session) -> str:
    """A valid key for the "vpn" source, issued by an owner."""
    email = register(client, "owneruser")
    owner = db_session.scalar(select(User).where(User.email == email))
    assert owner is not None
    owner.role = UserRole.OWNER
    db_session.commit()
    token = client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    response = client.post(
        "/admin/api-keys",
        json={"name": "Corporate VPN", "source": "vpn", "expires_in_days": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["key"]


def event(event_type: str = "login_failed", **overrides) -> dict:
    return {
        "event_type": event_type,
        "occurred_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        "email": "Mihai.Pop@Example.com",
        "ip_address": "198.51.100.7",
        "user_agent": UA,
        **overrides,
    }


def ingest(client: TestClient, key: str, events: list[dict]):
    return client.post(
        "/ingest/events",
        json={"events": events},
        headers={"Authorization": f"Bearer {key}"},
    )


def ingested(db_session: Session) -> list[SecurityEvent]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(SecurityEvent)
            .where(SecurityEvent.source == "vpn")
            .order_by(SecurityEvent.created_at)
        ).all()
    )


def test_events_are_stored_with_the_key_source_and_their_own_time(
    client: TestClient,
    db_session: Session,
    key: str,
) -> None:
    email = register(client, "mihai.pop")
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    earlier = datetime.now(UTC) - timedelta(hours=3)
    later = datetime.now(UTC) - timedelta(hours=1)

    response = ingest(
        client,
        key,
        [
            event("login_success", occurred_at=later.isoformat()),
            event("login_failed", occurred_at=earlier.isoformat()),
        ],
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": 2}
    failed, success = ingested(db_session)
    assert failed.event_type == SecurityEventType.LOGIN_FAILED
    assert failed.severity == SecuritySeverity.WARN
    assert failed.created_at == earlier
    # A failed sign-in names only the email, as for this application's own.
    assert failed.user_id is None
    assert failed.email == "mihai.pop@example.com"
    assert failed.ip_address == "198.51.100.7"
    assert failed.user_agent == UA
    assert failed.message == "Failed sign-in for mihai.pop@example.com, reported by vpn"
    assert success.severity == SecuritySeverity.INFO
    assert success.user_id == user.id
    assert success.created_at == later

    api_key = db_session.scalar(select(ApiKey))
    assert api_key is not None and api_key.last_used_at is not None


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "Bearer ",
        "Bearer not-a-key",
        "Bearer sck_00000000_secret",
        "Basic c2NrOg==",
    ],
)
def test_requests_without_a_valid_key_are_refused(
    client: TestClient,
    db_session: Session,
    key: str,
    authorization: str | None,
) -> None:
    headers = {"Authorization": authorization} if authorization else {}
    response = client.post(
        "/ingest/events", json={"events": [event()]}, headers=headers
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}
    assert ingested(db_session) == []


def test_a_wrong_secret_with_a_real_prefix_is_refused(
    client: TestClient,
    key: str,
) -> None:
    scheme, prefix, _ = key.split("_", 2)
    response = ingest(client, f"{scheme}_{prefix}_wrongsecret", [event()])
    assert response.status_code == 401


def test_revoked_and_expired_keys_stop_working(
    client: TestClient,
    db_session: Session,
    key: str,
) -> None:
    api_key = db_session.scalar(select(ApiKey))
    assert api_key is not None
    db_session.execute(
        update(ApiKey).values(expires_at=func.now() - timedelta(seconds=1))
    )
    db_session.commit()
    assert ingest(client, key, [event()]).status_code == 401

    db_session.execute(
        update(ApiKey).values(
            expires_at=func.now() + timedelta(days=1), revoked_at=func.now()
        )
    )
    db_session.commit()
    assert ingest(client, key, [event()]).status_code == 401


def test_a_user_token_is_not_an_api_key(client: TestClient, key: str) -> None:
    email = register(client, "someone")
    token = client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]

    assert ingest(client, token, [event()]).status_code == 401


@pytest.mark.parametrize(
    "bad_event",
    [
        event("user_role_changed"),
        event(severity="incident"),
        event(source="backend"),
        event(occurred_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat()),
        event(occurred_at=(datetime.now(UTC) - timedelta(days=400)).isoformat()),
        event(occurred_at="2026-10-08T10:00:00"),
        event(email="not-an-email"),
        event(ip_address="999.1.1.1"),
        event(user_agent="x" * 256),
    ],
)
def test_invalid_events_are_refused(
    client: TestClient,
    db_session: Session,
    key: str,
    bad_event: dict,
) -> None:
    response = ingest(client, key, [event(), bad_event])

    assert response.status_code == 422
    # The request is all or nothing.
    assert ingested(db_session) == []


@pytest.mark.parametrize("count", [0, 501])
def test_batch_size_is_bounded(client: TestClient, key: str, count: int) -> None:
    assert ingest(client, key, [event()] * count).status_code == 422


def test_ingested_events_go_through_the_detection_rules(
    client: TestClient,
    db_session: Session,
    key: str,
) -> None:
    spray = [
        event(email=f"victim{index}@example.com", ip_address="203.0.113.50")
        for index in range(settings.detection_spray_min_accounts)
    ]

    response = ingest(client, key, spray)

    # The sender is not told what the rules caught.
    assert response.json() == {"accepted": len(spray)}
    db_session.expire_all()
    alert = db_session.scalar(
        select(SecurityEvent).where(
            SecurityEvent.event_type == SecurityEventType.PASSWORD_SPRAY_DETECTED
        )
    )
    assert alert is not None
    assert alert.ip_address == "203.0.113.50"


def test_reported_failures_never_lock_this_application(
    client: TestClient,
    key: str,
) -> None:
    email = register(client, "mihai.pop")
    failures = [event(email=email)] * (settings.login_max_failed_attempts + 2)
    assert ingest(client, key, failures).status_code == 202

    # This application's own count starts from zero: none of these locks.
    for _ in range(settings.login_max_failed_attempts - 1):
        wrong = client.post(
            "/auth/login", json={"email": email, "password": "wrongpassword"}
        )
        assert wrong.status_code == 401

    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200


def test_reported_successes_never_reset_this_applications_count(
    client: TestClient,
    key: str,
) -> None:
    # Otherwise a stolen key could keep a brute-force attack under the limit.
    email = register(client, "mihai.pop")
    wrong = {"email": email, "password": "wrongpassword"}
    for _ in range(settings.login_max_failed_attempts - 1):
        assert client.post("/auth/login", json=wrong).status_code == 401
    occurred_at = datetime.now(UTC).isoformat()
    success = event("login_success", email=email, occurred_at=occurred_at)
    assert ingest(client, key, [success]).status_code == 202

    assert client.post("/auth/login", json=wrong).status_code == 429


def test_ingested_events_are_counted_by_source(client: TestClient, key: str) -> None:
    metric = "sentinelcore_ingested_events_total"
    before = REGISTRY.get_sample_value(metric, {"source": "vpn"}) or 0

    ingest(client, key, [event(), event("login_success")])

    assert REGISTRY.get_sample_value(metric, {"source": "vpn"}) == before + 2


@pytest.fixture()
def browser_client(db_session: Session) -> Generator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, headers={"User-Agent": UA}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_this_application_records_the_user_agent_of_sign_ins(
    browser_client: TestClient,
    db_session: Session,
) -> None:
    email = register(browser_client, "mihai.pop")
    browser_client.post("/auth/login", json={"email": email, "password": "wrong-one"})
    browser_client.post("/auth/login", json={"email": email, "password": PASSWORD})

    db_session.expire_all()
    sign_ins = db_session.scalars(
        select(SecurityEvent).where(
            SecurityEvent.event_type.in_(
                [SecurityEventType.LOGIN_FAILED, SecurityEventType.LOGIN_SUCCESS]
            )
        )
    ).all()
    assert [event.user_agent for event in sign_ins] == [UA, UA]
