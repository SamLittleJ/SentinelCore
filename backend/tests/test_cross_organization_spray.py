"""The platform rule for a password spray split across organizations (T-40).

Each organization's spray rule counts only its own emails, so an address
that fails a few emails in each stays below every threshold. This rule counts
this application's own failures from one address across all of them.
"""

from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import app
from app.models.security_event import (
    DETECTION_SOURCE,
    MITRE_TECHNIQUES,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import UserRole
from app.services.detection_service import counts_in
from tests.accounts import create_account, organization_id
from tests.conftest import rewriting_history, system_session

ADDRESS = "203.0.113.30"
OTHER_ADDRESS = "198.51.100.30"
PASSWORD = "testpassword"
THRESHOLD = 4
CROSS = SecurityEventType.CROSS_ORGANIZATION_SPRAY_DETECTED
SPRAY = SecurityEventType.PASSWORD_SPRAY_DETECTED


@pytest.fixture(autouse=True)
def threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """A spray of four emails, so the tests need few accounts."""
    monkeypatch.setattr(settings, "detection_spray_min_accounts", THRESHOLD)


@pytest.fixture()
def from_address(client: TestClient) -> Callable[[str], TestClient]:
    """Clients whose requests come from a given address. `client` serves
    their requests from the test's database session."""

    def make(host: str) -> TestClient:
        return TestClient(app, client=(host, 50000))

    return make


@pytest.fixture()
def members() -> dict[str, list[str]]:
    """Four accounts in Acme and four in Globex, by organization slug."""
    found: dict[str, list[str]] = {}
    for slug in ("acme", "globex"):
        for index in range(THRESHOLD):
            username = f"{slug}{index}"
            create_account(username, organization=slug)
            found.setdefault(slug, []).append(f"{username}@example.com")
    return found


def fail(client: TestClient, emails: list[str]) -> None:
    for email in emails:
        response = client.post(
            "/auth/login", json={"email": email, "password": "wrongpassword"}
        )
        assert response.status_code == 401, response.text


def unknown(count: int, start: int = 0) -> list[str]:
    return [f"nobody{index}@example.com" for index in range(start, start + count)]


def alerts(db_session: Session, alert_type: SecurityEventType) -> list[SecurityEvent]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(SecurityEvent)
            .where(SecurityEvent.event_type == alert_type)
            .order_by(SecurityEvent.id)
        ).all()
    )


def test_a_spray_split_across_organizations_raises_a_platform_incident(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
) -> None:
    attacker = from_address(ADDRESS)
    fail(attacker, members["acme"][:2] + members["globex"][:1])
    assert alerts(db_session, CROSS) == []

    fail(attacker, members["globex"][1:2])

    [alert] = alerts(db_session, CROSS)
    assert alert.organization_id is None
    assert alert.severity == SecuritySeverity.INCIDENT
    assert alert.source == DETECTION_SOURCE
    assert alert.ip_address == ADDRESS
    assert alert.email is None
    assert alert.user_id is None
    assert alert.message == (
        f"Password spray across organizations from {ADDRESS}: failed sign-ins "
        "for 4 different emails within 15 minutes, in 2 organizations"
    )
    # Neither organization reached its own threshold.
    assert alerts(db_session, SPRAY) == []


def test_the_alert_is_a_password_spray_technique() -> None:
    assert MITRE_TECHNIQUES[CROSS] == "T1110.003"


def test_a_spray_inside_one_organization_is_left_to_its_own_rule(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
) -> None:
    fail(from_address(ADDRESS), members["acme"])

    assert alerts(db_session, CROSS) == []
    [alert] = alerts(db_session, SPRAY)
    assert alert.organization_id is not None


def test_a_spray_on_emails_no_account_has_is_left_to_the_platforms_rule(
    from_address: Callable[[str], TestClient], db_session: Session
) -> None:
    fail(from_address(ADDRESS), unknown(THRESHOLD))

    assert alerts(db_session, CROSS) == []
    [alert] = alerts(db_session, SPRAY)
    assert alert.organization_id is None


def test_emails_no_account_has_count_as_a_place_of_their_own(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
) -> None:
    fail(from_address(ADDRESS), members["acme"][:2] + unknown(2))

    [alert] = alerts(db_session, CROSS)
    assert alert.message.endswith(
        "for 4 different emails within 15 minutes, "
        "in 1 organization and 2 with no account"
    )


def test_an_organizations_own_alert_does_not_hide_the_platforms(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
) -> None:
    """The organization learns of its own spray; only the owner learns that
    the address also tried another organization."""
    fail(from_address(ADDRESS), members["acme"] + members["globex"][:1])

    with system_session() as db:
        acme = organization_id(db, "acme")
    assert [alert.organization_id for alert in alerts(db_session, SPRAY)] == [acme]
    [alert] = alerts(db_session, CROSS)
    assert "for 5 different emails" in alert.message


def test_each_address_counts_separately(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
) -> None:
    fail(from_address(ADDRESS), members["acme"][:2])
    fail(from_address(OTHER_ADDRESS), members["globex"][:2])

    assert alerts(db_session, CROSS) == []


def test_ipv6_addresses_of_one_network_count_together(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
) -> None:
    fail(from_address("2001:db8:0:1::1"), members["acme"][:1])
    fail(from_address("2001:db8:0:1::2"), members["acme"][1:2])
    fail(from_address("2001:db8:0:1:ffff::3"), members["globex"][:1])
    # Another /64 network of the same provider counts on its own.
    fail(from_address("2001:db8:0:2::1"), members["globex"][1:2])
    assert alerts(db_session, CROSS) == []

    fail(from_address("2001:db8:0:1::4"), members["globex"][2:3])

    [alert] = alerts(db_session, CROSS)
    assert alert.ip_address == "2001:db8:0:1::4"
    assert alert.message.startswith(
        "Password spray across organizations from 2001:db8:0:1::/64:"
    )


def test_an_ipv4_client_of_an_ipv6_socket_counts_as_its_ipv4_address(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
) -> None:
    fail(from_address(ADDRESS), members["acme"][:2])
    fail(from_address(f"::ffff:{ADDRESS}"), members["globex"][:2])

    [alert] = alerts(db_session, CROSS)
    assert alert.message.startswith(
        f"Password spray across organizations from {ADDRESS}:"
    )


def test_only_failures_inside_the_window_count(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
) -> None:
    attacker = from_address(ADDRESS)
    fail(attacker, members["acme"][:2] + members["globex"][:1])
    window = timedelta(minutes=settings.detection_spray_window_minutes)
    with rewriting_history(db_session) as owner:
        owner.execute(
            update(SecurityEvent).values(
                created_at=SecurityEvent.created_at - window - timedelta(seconds=1)
            )
        )

    fail(attacker, members["globex"][1:2])

    assert alerts(db_session, CROSS) == []


def test_a_continuing_spray_alerts_again_only_after_enough_new_emails(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
) -> None:
    attacker = from_address(ADDRESS)
    fail(attacker, members["acme"][:2] + members["globex"][:2])
    assert len(alerts(db_session, CROSS)) == 1

    fail(attacker, members["acme"][2:] + members["globex"][2:3])
    assert len(alerts(db_session, CROSS)) == 1

    fail(attacker, members["globex"][3:])
    assert len(alerts(db_session, CROSS)) == 2


def test_failures_reported_by_ingestion_do_not_count(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
) -> None:
    """Another system's logs may name private addresses, which mean different
    machines in different organizations, and a tenant could forge them."""
    with system_session() as db:
        db.add_all(
            SecurityEvent(
                event_type=SecurityEventType.LOGIN_FAILED,
                severity=SecuritySeverity.WARN,
                organization_id=organization_id(db, slug),
                email=email,
                ip_address=ADDRESS,
                source="okta",
                message="Failed sign-in reported by Okta",
            )
            for slug, email in (
                ("acme", members["acme"][0]),
                ("acme", members["acme"][1]),
                ("globex", members["globex"][0]),
            )
        )
        db.commit()

    fail(from_address(ADDRESS), members["globex"][1:2])

    assert alerts(db_session, CROSS) == []


def test_an_event_naming_no_valid_address_does_not_break_the_rule(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
) -> None:
    """Other systems' events may name anything as their address."""
    with system_session() as db:
        db.add(
            SecurityEvent(
                event_type=SecurityEventType.LOGIN_FAILED,
                severity=SecuritySeverity.WARN,
                organization_id=organization_id(db, "acme"),
                email=members["acme"][0],
                ip_address="not-an-address",
                source="okta",
                message="Failed sign-in reported by Okta",
            )
        )
        db.commit()

    fail(from_address(ADDRESS), members["acme"][:2] + members["globex"][:2])

    assert len(alerts(db_session, CROSS)) == 1


def test_an_address_filter_skips_values_that_are_no_address(
    db_session: Session,
) -> None:
    """The database may judge the address before the other conditions, so
    the filter itself must not fail on what other systems sent."""
    with system_session() as db:
        db.add_all(
            SecurityEvent(
                event_type=SecurityEventType.LOGIN_FAILED,
                severity=SecuritySeverity.WARN,
                ip_address=address,
                source="okta",
                message="Failed sign-in reported by Okta",
            )
            for address in ("not-an-address", ADDRESS, f"::ffff:{ADDRESS}")
        )
        db.commit()
        matching = db.scalar(select(func.count()).where(counts_in(ADDRESS)))

    assert matching == 2


def test_a_failure_without_an_address_is_not_judged(
    client: TestClient, db_session: Session, members: dict[str, list[str]]
) -> None:
    # The default test client has no address.
    fail(client, members["acme"][:2] + members["globex"][:2])

    assert alerts(db_session, CROSS) == []


def test_the_threshold_comes_from_the_spray_setting(
    from_address: Callable[[str], TestClient],
    db_session: Session,
    members: dict[str, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "detection_spray_min_accounts", 2)

    fail(from_address(ADDRESS), members["acme"][:1] + members["globex"][:1])

    assert len(alerts(db_session, CROSS)) == 1


def owner_headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"email": f"{username}@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_only_the_platform_owner_sees_the_alert(
    client: TestClient,
    from_address: Callable[[str], TestClient],
    members: dict[str, list[str]],
) -> None:
    create_account("owner", role=UserRole.OWNER)
    create_account("ada", role=UserRole.ADMIN, organization="acme")
    fail(from_address(ADDRESS), members["acme"][:2] + members["globex"][:2])
    query = {"event_type": CROSS.value}

    owner = client.get(
        "/security/events", params=query, headers=owner_headers(client, "owner")
    )
    admin = client.get(
        "/security/events", params=query, headers=owner_headers(client, "ada")
    )

    assert owner.status_code == 200, owner.text
    assert [item["event_type"] for item in owner.json()["items"]] == [CROSS.value]
    assert admin.status_code == 200, admin.text
    assert admin.json()["items"] == []
