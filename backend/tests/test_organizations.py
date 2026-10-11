"""Organizations: managed by the platform owner alone, and the organization
every new record is written into."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditEventType, AuditLog
from app.models.organization import Organization
from app.models.security_event import SecurityEvent, SecurityEventType
from app.models.user import User, UserRole
from tests.accounts import PASSWORD, create_account, organization_id

ACME = {"name": "Acme", "slug": "acme"}


def log_in(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def headers_for(client: TestClient, username: str) -> dict[str, str]:
    response = log_in(client, f"{username}@example.com")
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def owner(client: TestClient) -> dict[str, str]:
    create_account("owner", role=UserRole.OWNER)
    return headers_for(client, "owner")


def create_organization(client: TestClient, owner: dict, **body) -> dict:
    response = client.post("/admin/organizations", json={**ACME, **body}, headers=owner)
    assert response.status_code == 201, response.text
    return response.json()


def events_of(db: Session, event_type: SecurityEventType) -> list[SecurityEvent]:
    return list(
        db.scalars(
            select(SecurityEvent)
            .where(SecurityEvent.event_type == event_type)
            .order_by(SecurityEvent.id)
        )
    )


def audits_of(db: Session, event_type: AuditEventType) -> list[AuditLog]:
    return list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.event_type == event_type)
            .order_by(AuditLog.id)
        )
    )


def new_key(client: TestClient, owner: dict, org_id: int) -> str:
    response = client.post(
        "/admin/api-keys",
        json={
            "name": "Corporate VPN",
            "source": "vpn",
            "expires_in_days": 30,
            "organization_id": org_id,
        },
        headers=owner,
    )
    assert response.status_code == 201, response.text
    return response.json()["key"]


def ingest(client: TestClient, key: str, *events: dict):
    return client.post(
        "/ingest/events",
        json={"events": list(events)},
        headers={"Authorization": f"Bearer {key}"},
    )


def sign_in(email: str, succeeded: bool = True, ip: str = "198.51.100.7") -> dict:
    return {
        "event_type": "login_success" if succeeded else "login_failed",
        "occurred_at": datetime.now(UTC).isoformat(),
        "email": email,
        "ip_address": ip,
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Firefox/140.0",
    }


# Managing organizations


@pytest.mark.parametrize(
    "role", [UserRole.ADMIN, UserRole.SECURITY_ANALYST, UserRole.USER]
)
def test_only_the_owner_manages_organizations(
    client: TestClient, db_session: Session, role: UserRole
) -> None:
    create_account("member", role=role)
    member = headers_for(client, "member")
    org_id = organization_id(db_session)

    assert client.get("/admin/organizations", headers=member).status_code == 403
    assert (
        client.post("/admin/organizations", json=ACME, headers=member).status_code
        == 403
    )
    for action in ("suspend", "reactivate"):
        assert (
            client.post(
                f"/admin/organizations/{org_id}/{action}", headers=member
            ).status_code
            == 403
        )
    assert (
        client.patch(
            f"/admin/organizations/{org_id}", json={"name": "Mine"}, headers=member
        ).status_code
        == 403
    )


def test_the_owner_creates_an_organization_it_owns_the_record_of(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    created = create_organization(client, owner)

    assert created["name"] == "Acme"
    assert created["slug"] == "acme"
    assert created["members"] == 0
    assert created["suspended_at"] is None
    # Its members will see in their logs that the platform created it.
    [event] = events_of(db_session, SecurityEventType.ORGANIZATION_CREATED)
    [audit] = audits_of(db_session, AuditEventType.ORGANIZATION_CREATED)
    assert event.organization_id == audit.organization_id == created["id"]

    listed = client.get("/admin/organizations", headers=owner)
    assert listed.status_code == 200
    assert [org["slug"] for org in listed.json()] == ["acme"]
    # Listing is the platform's own read.
    [viewed] = audits_of(db_session, AuditEventType.ORGANIZATIONS_VIEWED)
    assert viewed.organization_id is None


@pytest.mark.parametrize(
    "body",
    [{"name": "Acme"}, {"slug": "acme"}, {"name": "Acme", "slug": "acme"}],
)
def test_names_and_slugs_are_unique(
    client: TestClient, owner: dict, body: dict
) -> None:
    create_organization(client, owner)
    other = {"name": "Other", "slug": "other", **body}

    response = client.post("/admin/organizations", json=other, headers=owner)

    assert response.status_code == 409


@pytest.mark.parametrize(
    "slug", ["a", "Acme", "acme corp", "-acme", "acme-", "acme--eu", "x" * 41]
)
def test_a_slug_is_short_lowercase_and_hyphenated(
    client: TestClient, owner: dict, slug: str
) -> None:
    response = client.post(
        "/admin/organizations", json={"name": "Acme", "slug": slug}, headers=owner
    )

    assert response.status_code == 422


def test_renaming_keeps_the_slug(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    created = create_organization(client, owner)
    create_organization(client, owner, name="Globex", slug="globex")
    url = f"/admin/organizations/{created['id']}"

    renamed = client.patch(url, json={"name": "Acme Corp"}, headers=owner)

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Acme Corp"
    assert renamed.json()["slug"] == "acme"
    [event] = events_of(db_session, SecurityEventType.ORGANIZATION_RENAMED)
    assert event.organization_id == created["id"]
    slug_change = client.patch(
        url, json={"name": "Acme Two", "slug": "acme-corp"}, headers=owner
    )
    taken_name = client.patch(url, json={"name": "Globex"}, headers=owner)
    unknown = client.patch(
        "/admin/organizations/9999", json={"name": "Initech"}, headers=owner
    )
    assert slug_change.status_code == 422
    assert taken_name.status_code == 409
    assert unknown.status_code == 404
    # The refused rename left nothing half done.
    assert client.get("/admin/organizations", headers=owner).status_code == 200


# Suspension


def test_suspension_signs_members_out_and_refuses_them_as_deactivated(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    create_account("member")
    create_account("deactivated")
    member = headers_for(client, "member")
    deactivated = db_session.scalar(select(User).where(User.username == "deactivated"))
    assert deactivated is not None
    deactivated.is_active = False
    db_session.commit()
    deactivated_answer = log_in(client, "deactivated@example.com")
    org_id = organization_id(db_session)

    suspended = client.post(f"/admin/organizations/{org_id}/suspend", headers=owner)

    assert suspended.status_code == 200
    assert suspended.json()["suspended_at"] is not None
    # The session in use stops working at once.
    assert client.get("/users/me", headers=member).status_code == 403
    # Signing in gets exactly what a deactivated account gets.
    refused = log_in(client, "member@example.com")
    assert refused.status_code == deactivated_answer.status_code == 403
    assert refused.json() == deactivated_answer.json()
    [event] = events_of(db_session, SecurityEventType.ORGANIZATION_SUSPENDED)
    assert event.organization_id == org_id
    assert "closed 1 session(s)" in event.message

    reactivated = client.post(
        f"/admin/organizations/{org_id}/reactivate", headers=owner
    )
    assert reactivated.json()["suspended_at"] is None
    assert log_in(client, "member@example.com").status_code == 200


def test_a_suspended_organizations_keys_look_unknown(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    create_account("member")
    org_id = organization_id(db_session)
    key = new_key(client, owner, org_id)
    assert ingest(client, key, sign_in("member@example.com")).status_code == 202

    client.post(f"/admin/organizations/{org_id}/suspend", headers=owner)

    refused = ingest(client, key, sign_in("member@example.com"))
    unknown = ingest(client, "sck_unknown0_" + "x" * 40, sign_in("a@example.com"))
    assert refused.status_code == unknown.status_code == 401
    assert refused.json() == unknown.json()


def test_a_suspended_organizations_invitations_stop_working(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    org_id = organization_id(db_session)
    token = client.post(
        "/admin/invitations",
        json={"email": "new@example.com", "role": "user", "organization_id": org_id},
        headers=owner,
    ).json()["token"]
    unknown = client.post(
        "/auth/invitations/preview", json={"token": "sci_unknown0_" + "x" * 40}
    )

    client.post(f"/admin/organizations/{org_id}/suspend", headers=owner)

    refused = client.post("/auth/invitations/preview", json={"token": token})
    assert refused.status_code == unknown.status_code == 404
    assert refused.json() == unknown.json()


def test_nothing_new_is_made_in_a_suspended_organization(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    org_id = organization_id(db_session)
    client.post(f"/admin/organizations/{org_id}/suspend", headers=owner)

    invitation = client.post(
        "/admin/invitations",
        json={"email": "new@example.com", "role": "user", "organization_id": org_id},
        headers=owner,
    )
    key = client.post(
        "/admin/api-keys",
        json={
            "name": "Corporate VPN",
            "source": "vpn",
            "expires_in_days": 30,
            "organization_id": org_id,
        },
        headers=owner,
    )
    assert invitation.status_code == key.status_code == 409


# Which organization an invitation is for


def test_the_owner_names_the_organization_and_the_account_joins_it(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    acme = create_organization(client, owner)["id"]

    missing = client.post(
        "/admin/invitations",
        json={"email": "new@example.com", "role": "admin"},
        headers=owner,
    )
    unknown = client.post(
        "/admin/invitations",
        json={"email": "new@example.com", "role": "admin", "organization_id": 9999},
        headers=owner,
    )
    created = client.post(
        "/admin/invitations",
        json={"email": "new@example.com", "role": "admin", "organization_id": acme},
        headers=owner,
    )
    accepted = client.post(
        "/auth/invitations/accept",
        json={
            "token": created.json()["token"],
            "username": "newadmin",
            "password": "a-long-enough-password",
        },
    )

    assert missing.status_code == 422
    assert unknown.status_code == 404
    assert created.status_code == 201
    assert created.json()["invitation"]["organization_id"] == acme
    assert accepted.status_code == 201
    account = db_session.get(User, accepted.json()["id"])
    assert account is not None and account.organization_id == acme
    [invited] = events_of(db_session, SecurityEventType.INVITATION_CREATED)
    [joined] = [
        event
        for event in events_of(db_session, SecurityEventType.USER_REGISTERED)
        if event.email == "new@example.com"
    ]
    assert invited.organization_id == joined.organization_id == acme


def test_an_admin_invites_into_their_own_organization_only(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    acme = create_organization(client, owner)["id"]
    create_account("admin", role=UserRole.ADMIN)
    admin = headers_for(client, "admin")
    own = organization_id(db_session)

    naming_another = client.post(
        "/admin/invitations",
        json={"email": "new@example.com", "role": "user", "organization_id": acme},
        headers=admin,
    )
    naming_own = client.post(
        "/admin/invitations",
        json={"email": "new@example.com", "role": "user", "organization_id": own},
        headers=admin,
    )
    plain = client.post(
        "/admin/invitations",
        json={"email": "new@example.com", "role": "user"},
        headers=admin,
    )

    assert naming_another.status_code == naming_own.status_code == 403
    assert plain.status_code == 201
    assert plain.json()["invitation"]["organization_id"] == own


# Which organization each event belongs to


def test_sign_ins_belong_to_the_account_or_to_the_platform(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    create_account("member")
    org_id = organization_id(db_session)
    headers_for(client, "member")
    log_in(client, "member@example.com", "wrong-password")
    log_in(client, "nobody@example.com", "wrong-password")

    by_email = {
        event.email: event.organization_id
        for event in events_of(db_session, SecurityEventType.LOGIN_SUCCESS)
    }
    failed = {
        event.email: event.organization_id
        for event in events_of(db_session, SecurityEventType.LOGIN_FAILED)
    }
    assert by_email == {"owner@example.com": None, "member@example.com": org_id}
    assert failed == {"member@example.com": org_id, "nobody@example.com": None}


def test_the_owners_action_on_an_account_belongs_to_its_organization(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    member_id = create_account("member")
    org_id = organization_id(db_session)

    response = client.patch(
        f"/admin/users/{member_id}/role",
        json={"role": "security_analyst"},
        headers=owner,
    )

    assert response.status_code == 200
    [changed] = events_of(db_session, SecurityEventType.USER_ROLE_CHANGED)
    [alert] = events_of(db_session, SecurityEventType.PRIVILEGED_ROLE_GRANTED)
    [audit] = audits_of(db_session, AuditEventType.USER_ROLE_CHANGED)
    assert changed.organization_id == alert.organization_id == org_id
    assert audit.organization_id == org_id


def test_the_owner_reading_an_account_shows_in_its_organizations_audit(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    member_id = create_account("member")
    org_id = organization_id(db_session)

    assert client.get(f"/admin/users/{member_id}", headers=owner).status_code == 200

    [viewed] = audits_of(db_session, AuditEventType.USERS_VIEWED)
    assert viewed.user_id != member_id
    assert viewed.target_user_id == member_id
    assert viewed.organization_id == org_id


def test_a_lockout_belongs_to_the_account_or_to_the_platform(
    client: TestClient, db_session: Session
) -> None:
    create_account("member")
    org_id = organization_id(db_session)
    for email in ("member@example.com", "nobody@example.com"):
        for _ in range(5):
            log_in(client, email, "wrong-password")

    lockouts = {
        event.email: event.organization_id
        for event in events_of(db_session, SecurityEventType.BRUTE_FORCE_DETECTED)
    }
    assert lockouts == {"member@example.com": org_id, "nobody@example.com": None}


def test_ingested_events_and_their_alerts_belong_to_the_keys_organization(
    client: TestClient, db_session: Session, owner: dict
) -> None:
    create_account("member")
    acme = create_organization(client, owner)["id"]
    key = new_key(client, owner, acme)

    # A spray from one address over ten emails, one of them another
    # organization's account.
    events = [sign_in(f"guess{n}@example.com", False) for n in range(9)]
    events.append(sign_in("member@example.com", False))
    events.append(sign_in("member@example.com", True))
    assert ingest(client, key, *events).status_code == 202

    ingested = db_session.scalars(
        select(SecurityEvent).where(SecurityEvent.source == "vpn")
    ).all()
    assert {event.organization_id for event in ingested} == {acme}
    # A key never links an event to another organization's account.
    assert {event.user_id for event in ingested} == {None}
    [spray] = events_of(db_session, SecurityEventType.PASSWORD_SPRAY_DETECTED)
    assert spray.organization_id == acme
    [created] = events_of(db_session, SecurityEventType.API_KEY_CREATED)
    assert created.organization_id == acme


# What the database itself refuses


def test_the_owner_has_no_organization_and_everyone_else_one(
    db_session: Session,
) -> None:
    org_id = organization_id(db_session)
    owner = User(
        username="owner2",
        email="owner2@example.com",
        hashed_password="x",
        role=UserRole.OWNER,
        organization_id=org_id,
    )
    db_session.add(owner)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    member = User(
        username="member2",
        email="member2@example.com",
        hashed_password="x",
        role=UserRole.USER,
    )
    db_session.add(member)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.scalar(select(Organization).where(Organization.id == org_id))
