"""Isolation between organizations: every read shows a member their own
organization only, a record of another one answers as a missing one, and the
detection rules count within one organization."""

from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.audit_log import AuditEventType, AuditLog
from app.models.invitation import Invitation
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole
from tests.accounts import create_account, organization_id
from tests.conftest import serve_requests_from
from tests.test_organizations import headers_for, ingest, new_key, sign_in

ATTACKER_IP = "203.0.113.9"
MISSING_ID = 999_999


@dataclass
class Platform:
    """Two organizations and the platform owner. Acme has an admin (ada), an
    analyst (ana) and a user (alice); Globex an admin (gus) and a user
    (gina)."""

    acme: int
    globex: int
    ids: dict[str, int]
    owner: dict[str, str]
    ada: dict[str, str]
    ana: dict[str, str]


@pytest.fixture()
def platform(client: TestClient, db_session: Session) -> Platform:
    ids = {"owner": create_account("owner", role=UserRole.OWNER)}
    for username, role, organization in (
        ("ada", UserRole.ADMIN, "acme"),
        ("ana", UserRole.SECURITY_ANALYST, "acme"),
        ("alice", UserRole.USER, "acme"),
        ("gus", UserRole.ADMIN, "globex"),
        ("gina", UserRole.USER, "globex"),
    ):
        ids[username] = create_account(username, role=role, organization=organization)
    return Platform(
        acme=organization_id(db_session, "acme"),
        globex=organization_id(db_session, "globex"),
        ids=ids,
        owner=headers_for(client, "owner"),
        ada=headers_for(client, "ada"),
        ana=headers_for(client, "ana"),
    )


@pytest.fixture()
def attacker(db_session: Session) -> Generator[TestClient]:
    """A client whose requests come from ATTACKER_IP, so the spray rule,
    which is keyed on addresses, can fire."""
    app.dependency_overrides[get_db] = serve_requests_from(db_session)
    with TestClient(app, client=(ATTACKER_IP, 50000)) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def invite(client: TestClient, owner: dict, email: str, org_id: int) -> dict:
    response = client.post(
        "/admin/invitations",
        json={"email": email, "role": "user", "organization_id": org_id},
        headers=owner,
    )
    assert response.status_code == 201, response.text
    return response.json()["invitation"]


def items(response) -> list[dict]:
    assert response.status_code == 200, response.text
    body = response.json()
    return body["items"] if isinstance(body, dict) else body


def organizations_in(response) -> set[int | None]:
    return {item["organization_id"] for item in items(response)}


def fail_login(client: TestClient, email: str) -> None:
    response = client.post(
        "/auth/login", json={"email": email, "password": "wrongpassword"}
    )
    assert response.status_code == 401, response.text


def spray_alerts(db_session: Session) -> list[SecurityEvent]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(SecurityEvent)
            .where(
                SecurityEvent.event_type == SecurityEventType.PASSWORD_SPRAY_DETECTED
            )
            .order_by(SecurityEvent.id)
        )
    )


def owners_reads(db_session: Session, owner_id: int) -> list[int | None]:
    """The organization of each audit record of the owner's reads, in order."""
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(AuditLog.organization_id)
            .where(
                AuditLog.user_id == owner_id,
                AuditLog.event_type.in_(
                    [
                        AuditEventType.USERS_VIEWED,
                        AuditEventType.SECURITY_EVENTS_VIEWED,
                        AuditEventType.AUDIT_LOGS_VIEWED,
                        AuditEventType.INVITATIONS_VIEWED,
                        AuditEventType.API_KEYS_VIEWED,
                    ]
                ),
            )
            .order_by(AuditLog.id)
        )
    )


# Listings

RECORD_LISTINGS = [
    "/security/events",
    "/admin/audit-logs",
    "/admin/users",
    "/admin/invitations",
    "/admin/api-keys",
]


@pytest.fixture()
def records_in_both(client: TestClient, platform: Platform) -> None:
    """An invitation and an API key in each organization, besides the
    accounts, their events and audit records."""
    for org_id, name in ((platform.acme, "acme"), (platform.globex, "globex")):
        invite(client, platform.owner, f"new-{name}@example.com", org_id)
        new_key(client, platform.owner, org_id)


@pytest.mark.usefixtures("records_in_both")
@pytest.mark.parametrize("path", RECORD_LISTINGS)
@pytest.mark.parametrize("reader", ["ada", "ana"])
def test_a_member_lists_only_their_own_organizations_records(
    client: TestClient, platform: Platform, path: str, reader: str
) -> None:
    response = client.get(path, headers=getattr(platform, reader))
    assert organizations_in(response) == {platform.acme}


@pytest.mark.usefixtures("records_in_both")
@pytest.mark.parametrize("path", RECORD_LISTINGS)
def test_the_owner_lists_every_organization_or_the_one_named(
    client: TestClient, platform: Platform, path: str
) -> None:
    everything = organizations_in(client.get(path, headers=platform.owner))
    assert {platform.acme, platform.globex} <= everything

    named = client.get(
        path, params={"organization_id": platform.globex}, headers=platform.owner
    )
    assert organizations_in(named) == {platform.globex}


def test_a_members_user_list_leaves_out_the_owner_and_other_organizations(
    client: TestClient, platform: Platform
) -> None:
    users = items(client.get("/admin/users", headers=platform.ada))
    assert {user["username"] for user in users} == {"ada", "ana", "alice"}


@pytest.mark.parametrize("path", [*RECORD_LISTINGS, "/security/summary"])
@pytest.mark.parametrize("reader", ["ada", "ana"])
def test_only_the_owner_may_name_an_organization(
    client: TestClient, platform: Platform, path: str, reader: str
) -> None:
    # Even their own: the parameter is the owner's alone.
    response = client.get(
        path,
        params={"organization_id": platform.acme},
        headers=getattr(platform, reader),
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.parametrize("path", [*RECORD_LISTINGS, "/security/summary"])
def test_the_owner_naming_an_unknown_organization_gets_a_404(
    client: TestClient, platform: Platform, path: str
) -> None:
    response = client.get(
        path, params={"organization_id": MISSING_ID}, headers=platform.owner
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def summary_counts(client: TestClient, headers: dict, **params) -> dict:
    """The summary without the times it was measured at."""
    response = client.get("/security/summary", params=params, headers=headers)
    assert response.status_code == 200, response.text
    summary = response.json()
    del summary["generated_at"]
    for windows in ("hourly", "daily"):
        summary[windows] = [bucket["counts"] for bucket in summary[windows]]
    return summary


def test_nothing_in_another_organization_changes_the_summary(
    client: TestClient, db_session: Session, platform: Platform
) -> None:
    before = summary_counts(client, platform.ada)

    # In Globex, something for every figure: a failure from an address, a
    # lockout, a detection, a locked and an inactive account.
    for event_type, severity, source in (
        (SecurityEventType.LOGIN_FAILED, SecuritySeverity.WARN, "backend"),
        (SecurityEventType.BRUTE_FORCE_DETECTED, SecuritySeverity.INCIDENT, "backend"),
        (SecurityEventType.PASSWORD_SPRAY_DETECTED, SecuritySeverity.WARN, "detection"),
    ):
        db_session.add(
            SecurityEvent(
                event_type=event_type,
                severity=severity,
                source=source,
                email="gina@example.com",
                ip_address="192.0.2.1",
                organization_id=platform.globex,
                message="seeded",
            )
        )
    gina = db_session.get(User, platform.ids["gina"])
    assert gina is not None
    gina.locked_until = datetime.now(UTC) + timedelta(hours=1)
    gina.is_active = False
    db_session.commit()

    assert summary_counts(client, platform.ada) == before
    assert before["users_total"] == 3
    # Ada and Ana joined with privileged roles (T1098); Globex's incident
    # and spray would raise the level and add a technique.
    assert before["threat_level"] == "warn"

    globex = summary_counts(client, platform.owner, organization_id=platform.globex)
    assert globex["users_total"] == 2
    assert globex["users_inactive"] == 1
    assert globex["accounts_locked"] == 1
    assert globex["failed_logins_24h"] == 1
    assert globex["locked_logins"] == 1
    assert globex["threat_level"] == "incident"

    everything = summary_counts(client, platform.owner)
    assert everything["users_total"] == 6
    assert everything["failed_logins_24h"] == 1


def test_an_organization_without_detections_stays_calm_beside_others(
    client: TestClient, db_session: Session, platform: Platform
) -> None:
    # Acme and Globex have detections: their admins joined with a
    # privileged role (T1098). Initech, with one user, has none.
    create_account("ivan", organization="initech")

    initech = summary_counts(
        client, platform.owner, organization_id=organization_id(db_session, "initech")
    )
    assert initech["users_total"] == 1
    assert initech["threat_level"] == "calm"
    assert initech["latest_detection"] is None
    assert initech["techniques_7d"] == []
    assert sum(bucket["warn"] for bucket in initech["daily"]) == 0


@pytest.mark.parametrize(
    ("path", "model"),
    [("/security/events", SecurityEvent), ("/admin/audit-logs", AuditLog)],
)
def test_a_cursor_from_another_organization_answers_as_a_missing_one(
    client: TestClient,
    db_session: Session,
    platform: Platform,
    path: str,
    model: type[SecurityEvent | AuditLog],
) -> None:
    # Globex's newest record, after every one of Acme's: as a cursor, it
    # would page through Acme's records older than it, telling when it was.
    other = db_session.scalar(
        select(func.max(model.id)).where(model.organization_id == platform.globex)
    )

    missing = client.get(path, params={"before_id": MISSING_ID}, headers=platform.ada)
    from_other = client.get(path, params={"before_id": other}, headers=platform.ada)

    assert items(missing) == []
    assert items(from_other) == []


# Records of another organization

ACCOUNT_ACTIONS = [
    ("GET", "", None),
    ("GET", "/activity", None),
    ("PATCH", "/status", {"is_active": False}),
    ("POST", "/revoke-sessions", {"reason": "Suspected compromise"}),
    ("POST", "/lock", {"duration_hours": 1, "reason": "Suspected compromise"}),
    ("POST", "/unlock", None),
]


@pytest.mark.parametrize(("method", "suffix", "body"), ACCOUNT_ACTIONS)
@pytest.mark.parametrize("target", ["gina", "owner"])
def test_another_organizations_account_answers_as_a_missing_one(
    client: TestClient,
    db_session: Session,
    platform: Platform,
    method: str,
    suffix: str,
    body: dict | None,
    target: str,
) -> None:
    def request(user_id: int):
        return client.request(
            method,
            f"/admin/users/{user_id}{suffix}",
            json=body,
            headers=platform.ada,
        )

    missing = request(MISSING_ID)
    other = request(platform.ids[target])

    assert missing.status_code == 404
    assert (other.status_code, other.json()) == (missing.status_code, missing.json())
    db_session.expire_all()
    account = db_session.get(User, platform.ids[target])
    assert account is not None
    assert account.is_active
    assert account.locked_until is None


def test_another_organizations_invitation_answers_as_a_missing_one(
    client: TestClient, db_session: Session, platform: Platform
) -> None:
    invitation = invite(client, platform.owner, "new@example.com", platform.globex)

    missing = client.post(
        f"/admin/invitations/{MISSING_ID}/revoke", headers=platform.ada
    )
    other = client.post(
        f"/admin/invitations/{invitation['id']}/revoke", headers=platform.ada
    )

    assert missing.status_code == 404
    assert (other.status_code, other.json()) == (missing.status_code, missing.json())
    db_session.expire_all()
    stored = db_session.get(Invitation, invitation["id"])
    assert stored is not None
    assert stored.revoked_at is None


def test_an_account_shows_no_sign_ins_another_organization_reported_for_its_email(
    client: TestClient, platform: Platform
) -> None:
    # Globex's systems report a failure for an address that is an Acme account.
    key = new_key(client, platform.owner, platform.globex)
    assert ingest(client, key, sign_in("alice@example.com", succeeded=False)).json()
    fail_login(client, "alice@example.com")  # Acme's own, which does count.

    activity = items(
        client.get(
            f"/admin/users/{platform.ids['alice']}/activity", headers=platform.ada
        )
    )
    failures = [e for e in activity if e["event_type"] == "login_failed"]
    assert [e["source"] for e in failures] == ["backend"]

    alice = headers_for(client, "alice")
    own = items(client.get("/users/me/activity", headers=alice))
    assert [e["event_type"] for e in own].count("login_failed") == 1


# The owner's reads in the organizations' audit logs


def test_the_owners_listing_is_audited_in_each_organization_it_showed(
    client: TestClient, db_session: Session, platform: Platform
) -> None:
    owner_id = platform.ids["owner"]

    # The owner, an account of no organization, is in the list too.
    client.get("/admin/users", headers=platform.owner)
    assert sorted(owners_reads(db_session, owner_id), key=str) == sorted(
        [platform.acme, platform.globex, None], key=str
    )

    client.get(
        "/admin/users",
        params={"organization_id": platform.globex},
        headers=platform.owner,
    )
    assert owners_reads(db_session, owner_id)[3:] == [platform.globex]

    # An empty page shows no organization: the read stays on the platform.
    client.get("/admin/invitations", headers=platform.owner)
    assert owners_reads(db_session, owner_id)[4:] == [None]


def test_an_organizations_audit_log_shows_the_owner_reading_it(
    client: TestClient, platform: Platform
) -> None:
    client.get("/admin/users", headers=platform.owner)

    logs = items(
        client.get(
            "/admin/audit-logs",
            params={"event_type": "users_viewed", "user_id": platform.ids["owner"]},
            headers=platform.ada,
        )
    )
    assert len(logs) == 1
    assert logs[0]["organization_id"] == platform.acme


# Detection within one organization


@pytest.fixture()
def spray_threshold_of_two(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "detection_spray_min_accounts", 2)


@pytest.mark.usefixtures("spray_threshold_of_two")
def test_a_spray_counts_the_emails_of_one_organization(
    attacker: TestClient, db_session: Session, platform: Platform
) -> None:
    fail_login(attacker, "alice@example.com")
    fail_login(attacker, "gina@example.com")
    assert spray_alerts(db_session) == []

    fail_login(attacker, "ada@example.com")
    [alert] = spray_alerts(db_session)
    assert alert.organization_id == platform.acme


@pytest.mark.usefixtures("spray_threshold_of_two")
def test_a_spray_on_emails_no_account_has_is_the_platforms(
    attacker: TestClient, db_session: Session, platform: Platform
) -> None:
    fail_login(attacker, "alice@example.com")
    fail_login(attacker, "nobody1@example.com")
    assert spray_alerts(db_session) == []

    fail_login(attacker, "nobody2@example.com")
    [alert] = spray_alerts(db_session)
    assert alert.organization_id is None


@pytest.mark.usefixtures("spray_threshold_of_two")
def test_another_organizations_spray_alert_does_not_restart_the_count(
    attacker: TestClient, db_session: Session, platform: Platform
) -> None:
    fail_login(attacker, "alice@example.com")
    fail_login(attacker, "gina@example.com")
    fail_login(attacker, "gus@example.com")
    assert [a.organization_id for a in spray_alerts(db_session)] == [platform.globex]

    # Alice's failure came before Globex's alert and still counts for Acme.
    fail_login(attacker, "ada@example.com")
    assert [a.organization_id for a in spray_alerts(db_session)] == [
        platform.globex,
        platform.acme,
    ]
