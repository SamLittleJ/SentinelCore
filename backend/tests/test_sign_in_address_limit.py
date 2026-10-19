"""The limit on failed sign-ins per address (services/sign_in_limit_service.py).

Requests come from addresses of their own: TestClient's default host,
"testclient", is not an IP address, so it counts as an unknown address."""

import threading
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.metrics import LOGIN_REFUSED
from app.core.row_security import restrict_rows
from app.main import app
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    BACKEND_SOURCE,
    MITRE_TECHNIQUES,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.sign_in_address_limit import SignInAddressLimit
from app.models.user_session import UserSession
from app.services.session_cleanup import run_session_cleanup
from app.services.sign_in_limit_service import (
    UNKNOWN_ADDRESS,
    address_key,
    delete_full_buckets,
    take_attempt,
)
from app.services.tenancy import Scope
from tests.accounts import create_account
from tests.conftest import TestingSessionLocal, system_session

ADDRESS = "203.0.113.7"
OTHER_ADDRESS = "198.51.100.20"
EMAIL = "testuser@example.com"
PASSWORD = "testpassword"
REFUSED_DETAIL = "Too many failed login attempts. Try again later."
# One token every ten minutes, by default.
SECONDS_PER_TOKEN = 3600 // 6


@pytest.fixture()
def from_address(client: TestClient) -> Callable[[str], TestClient]:
    """Clients whose requests come from a given address. `client` serves
    their requests from the test's database session."""

    def make(host: str) -> TestClient:
        return TestClient(app, client=(host, 50000))

    return make


@pytest.fixture()
def small_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    """Three failed attempts per address; the rate stays the default."""
    monkeypatch.setattr(settings, "login_address_burst", 3)


def sign_in(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def fail(client: TestClient, count: int, start: int = 0) -> list[int]:
    """Fail `count` sign-ins, each on an email no account has."""
    return [
        sign_in(client, f"nobody{index}@example.com", "wrongpassword").status_code
        for index in range(start, start + count)
    ]


def events_of(db_session: Session, event_type: SecurityEventType) -> list:
    return list(
        db_session.scalars(
            select(SecurityEvent).where(SecurityEvent.event_type == event_type)
        ).all()
    )


def event_count(db_session: Session) -> int:
    return db_session.scalar(select(func.count(SecurityEvent.id))) or 0


def move_refill_back(db_session: Session, seconds: int) -> None:
    db_session.execute(
        update(SignInAddressLimit).values(
            refilled_at=SignInAddressLimit.refilled_at - timedelta(seconds=seconds)
        )
    )
    db_session.commit()


# The address


def test_an_ipv4_address_counts_on_its_own() -> None:
    assert address_key("203.0.113.7") == "203.0.113.7"
    assert address_key("203.0.113.8") != address_key("203.0.113.7")


def test_an_ipv6_address_counts_with_its_64_network() -> None:
    assert address_key("2001:db8:1:2::5") == "2001:db8:1:2::/64"
    assert address_key("2001:db8:1:2:ffff:ffff:ffff:ffff") == "2001:db8:1:2::/64"
    assert address_key("2001:db8:1:3::5") == "2001:db8:1:3::/64"


def test_an_ipv4_client_of_an_ipv6_socket_counts_as_ipv4() -> None:
    assert address_key("::ffff:203.0.113.7") == "203.0.113.7"


def test_an_unknown_address_has_a_bucket_too() -> None:
    assert address_key(None) == UNKNOWN_ADDRESS


# The limit


def test_an_address_is_refused_once_its_failures_are_spent(
    from_address: Callable[[str], TestClient],
) -> None:
    client = from_address(ADDRESS)

    burst = settings.login_address_burst
    assert fail(client, burst) == [401] * burst

    response = sign_in(client, "nobody-more@example.com", "wrongpassword")
    assert response.status_code == 429
    # As the email's lockout answers: nothing tells the two apart.
    assert response.json()["detail"] == REFUSED_DETAIL
    assert 0 < int(response.headers["Retry-After"]) <= SECONDS_PER_TOKEN


def test_a_refused_attempt_is_not_checked_and_writes_no_event(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    small_bucket: None,
) -> None:
    create_account("testuser", EMAIL, PASSWORD)
    client = from_address(ADDRESS)
    fail(client, 3)
    events, refused = event_count(db_session), LOGIN_REFUSED._value.get()

    # Even the right password: the address is refused before it is checked.
    assert sign_in(client).status_code == 429
    assert fail(client, 2, start=3) == [429, 429]

    assert event_count(db_session) == events
    assert db_session.scalar(select(func.count(UserSession.id))) == 0
    assert LOGIN_REFUSED._value.get() == refused + 3


def test_the_failure_that_spends_the_last_attempt_is_recorded_once(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    small_bucket: None,
) -> None:
    client = from_address(ADDRESS)
    assert fail(client, 2) == [401, 401]
    assert events_of(db_session, SecurityEventType.LOGIN_ADDRESS_LIMITED) == []

    # The third failure still gets its own answer.
    assert fail(client, 1, start=2) == [401]
    fail(client, 3, start=3)

    (event,) = events_of(db_session, SecurityEventType.LOGIN_ADDRESS_LIMITED)
    assert event.severity == SecuritySeverity.WARN
    assert event.source == BACKEND_SOURCE
    # The platform's: an address is no organization's.
    assert event.organization_id is None
    assert event.ip_address == ADDRESS
    assert event.user_id is None and event.email is None
    assert ADDRESS in (event.message or "")
    assert event.occurred_at is not None

    (audit,) = db_session.scalars(
        select(AuditLog).where(
            AuditLog.event_type == AuditEventType.LOGIN_ADDRESS_LIMITED
        )
    ).all()
    assert audit.organization_id is None
    assert audit.ip_address == ADDRESS
    assert audit.message == event.message


def test_the_limit_stands_for_brute_force() -> None:
    assert MITRE_TECHNIQUES[SecurityEventType.LOGIN_ADDRESS_LIMITED] == "T1110"


def test_a_successful_sign_in_spends_nothing(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    small_bucket: None,
) -> None:
    create_account("testuser", EMAIL, PASSWORD)
    client = from_address(ADDRESS)
    assert fail(client, 2) == [401, 401]

    for _ in range(3):
        assert sign_in(client).status_code == 200

    # One failure was still left, and spending it limits the address.
    assert fail(client, 1, start=2) == [401]
    assert sign_in(client).status_code == 429
    assert len(events_of(db_session, SecurityEventType.LOGIN_ADDRESS_LIMITED)) == 1


def test_attempts_on_a_locked_email_spend_the_addresss_failures(
    from_address: Callable[[str], TestClient],
    db_session: Session,
) -> None:
    create_account("testuser", EMAIL, PASSWORD)
    client = from_address(ADDRESS)
    statuses = [
        sign_in(client, password="wrongpassword").status_code
        for _ in range(settings.login_address_burst)
    ]
    # Locked after five failures, then refused by the email's lockout.
    assert statuses[: settings.login_max_failed_attempts - 1] == [401] * 4
    assert set(statuses[settings.login_max_failed_attempts - 1 :]) == {429}
    blocked = len(events_of(db_session, SecurityEventType.LOGIN_BLOCKED))

    # The address is spent too, so it can no longer fill the event table.
    assert fail(client, 5) == [429] * 5
    assert len(events_of(db_session, SecurityEventType.LOGIN_BLOCKED)) == blocked


def test_each_address_has_its_own_failures(
    from_address: Callable[[str], TestClient], small_bucket: None
) -> None:
    fail(from_address(ADDRESS), 3)

    assert fail(from_address(OTHER_ADDRESS), 1) == [401]
    assert fail(from_address(ADDRESS), 1, start=3) == [429]


def test_ipv6_addresses_of_one_network_share_their_failures(
    from_address: Callable[[str], TestClient], small_bucket: None
) -> None:
    fail(from_address("2001:db8:1:2::5"), 3)

    assert fail(from_address("2001:db8:1:2::6"), 1, start=3) == [429]
    assert fail(from_address("2001:db8:1:3::5"), 1, start=4) == [401]


def test_requests_without_a_known_address_share_one_bucket(
    from_address: Callable[[str], TestClient], small_bucket: None
) -> None:
    fail(from_address("testclient"), 3)

    assert fail(from_address("not-an-address"), 1, start=3) == [429]


@pytest.mark.parametrize(
    "path, body",
    [
        ("/auth/token", {"data": {"username": EMAIL, "password": PASSWORD}}),
        ("/auth/session", {"json": {"email": EMAIL, "password": PASSWORD}}),
    ],
)
def test_every_sign_in_path_has_the_limit(
    from_address: Callable[[str], TestClient],
    small_bucket: None,
    path: str,
    body: dict,
) -> None:
    create_account("testuser", EMAIL, PASSWORD)
    client = from_address(ADDRESS)
    fail(client, 3)

    assert client.post(path, **body).status_code == 429


def test_the_spray_alert_comes_before_the_limit(
    from_address: Callable[[str], TestClient], db_session: Session
) -> None:
    fail(from_address(ADDRESS), settings.detection_spray_min_accounts)

    assert events_of(db_session, SecurityEventType.PASSWORD_SPRAY_DETECTED)
    assert events_of(db_session, SecurityEventType.LOGIN_ADDRESS_LIMITED) == []


# The bucket


def test_the_bucket_gives_one_failure_back_every_ten_minutes(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    small_bucket: None,
) -> None:
    client = from_address(ADDRESS)
    fail(client, 3)

    move_refill_back(db_session, SECONDS_PER_TOKEN)

    assert fail(client, 2, start=3) == [401, 429]


def test_the_bucket_never_holds_more_than_its_burst(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    small_bucket: None,
) -> None:
    client = from_address(ADDRESS)
    fail(client, 1)

    move_refill_back(db_session, 10 * 24 * 3600)

    assert fail(client, 4, start=1) == [401, 401, 401, 429]


def test_two_attempts_cannot_spend_the_same_failure(db_session: Session) -> None:
    take_attempt(db_session, ADDRESS)
    db_session.execute(update(SignInAddressLimit).values(tokens=1.0))
    db_session.commit()

    with system_session() as first:
        # The first attempt holds the row while it decides...
        first.execute(
            select(SignInAddressLimit)
            .where(SignInAddressLimit.address == ADDRESS)
            .with_for_update()
        )

        # ...when the second arrives.
        outcome: list[int] = []

        def second_attempt() -> None:
            with system_session() as second:
                outcome.append(take_attempt(second, ADDRESS).retry_after)

        second = threading.Thread(target=second_attempt)
        second.start()
        second.join(timeout=0.5)
        assert second.is_alive()

        # The first spends the last token. The second must have waited to read
        # the bucket, rather than read the token still there and spend it too.
        first.execute(update(SignInAddressLimit).values(tokens=0.0))
        first.commit()
        second.join(timeout=5)

    assert outcome and outcome[0] > 0


def test_the_buckets_clock_never_runs_backwards(db_session: Session) -> None:
    take_attempt(db_session, ADDRESS)
    later = db_session.scalar(select(func.now() + timedelta(seconds=10)))
    db_session.execute(update(SignInAddressLimit).values(tokens=0.0, refilled_at=later))
    db_session.commit()

    assert take_attempt(db_session, ADDRESS).retry_after > 0
    bucket = db_session.get(SignInAddressLimit, ADDRESS, populate_existing=True)
    assert bucket is not None and bucket.refilled_at == later


def test_the_cleanup_deletes_only_buckets_that_filled_up_again(
    db_session: Session,
) -> None:
    take_attempt(db_session, ADDRESS)
    take_attempt(db_session, OTHER_ADDRESS)
    full_after = 3600 * settings.login_address_burst // 6
    db_session.execute(
        update(SignInAddressLimit)
        .where(SignInAddressLimit.address == ADDRESS)
        .values(refilled_at=func.now() - timedelta(seconds=full_after + 1))
    )
    db_session.execute(
        update(SignInAddressLimit)
        .where(SignInAddressLimit.address == OTHER_ADDRESS)
        .values(refilled_at=func.now() - timedelta(seconds=full_after - 60))
    )
    db_session.commit()

    assert delete_full_buckets(db_session) == 1
    assert db_session.scalars(select(SignInAddressLimit.address)).all() == [
        OTHER_ADDRESS
    ]


def test_the_periodic_cleanup_deletes_full_buckets(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.session_cleanup as cleanup

    monkeypatch.setattr(cleanup, "SessionLocal", system_session)
    take_attempt(db_session, ADDRESS)
    move_refill_back(db_session, 10 * 24 * 3600)

    run_session_cleanup()

    assert db_session.scalars(select(SignInAddressLimit)).all() == []


def test_only_the_scope_that_sees_everything_reaches_the_buckets(
    db_session: Session,
) -> None:
    take_attempt(db_session, ADDRESS)

    with TestingSessionLocal() as db:
        assert db.scalars(select(SignInAddressLimit)).all() == []
        restrict_rows(db, Scope(organization_id=1))
        assert db.scalars(select(SignInAddressLimit)).all() == []
        db.add(
            SignInAddressLimit(
                address=OTHER_ADDRESS, tokens=1.0, refilled_at=func.now()
            )
        )
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.commit()


# The settings

URL, SECRET_KEY = "postgresql://unused", "x" * 32


def test_by_default_20_failures_then_6_an_hour() -> None:
    fields = Settings.model_fields
    assert fields["login_address_burst"].default == 20
    assert fields["login_address_failures_per_hour"].default == 6


def test_the_burst_leaves_room_for_the_spray_alert_and_the_lockout() -> None:
    valid: dict[str, Any] = {
        "login_address_burst": 11,
        "detection_spray_min_accounts": 10,
        "login_max_failed_attempts": 5,
    }
    Settings(database_url=URL, secret_key=SECRET_KEY, **valid)
    # The spray's threshold alone, then the lockout's alone.
    invalid: list[dict[str, Any]] = [
        {"login_address_burst": 10},
        {"login_max_failed_attempts": 12},
        {"login_address_burst": 0},
        {"login_address_failures_per_hour": 0},
    ]
    for changes in invalid:
        with pytest.raises(ValidationError):
            Settings(database_url=URL, secret_key=SECRET_KEY, **{**valid, **changes})
