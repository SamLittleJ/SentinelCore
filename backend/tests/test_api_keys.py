from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import SecurityEvent, SecurityEventType
from app.models.user import User, UserRole
from tests.accounts import create_account

PASSWORD = "testpassword"
NEW_KEY = {"name": "GitHub audit log", "source": "github", "expires_in_days": 90}


def headers_for(client: TestClient, db_session: Session, role: UserRole) -> dict:
    username = role.value.replace("_", "")
    email = f"{username}@example.com"
    create_account(username, email, PASSWORD)
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = role
    db_session.commit()
    token = client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def owner(client: TestClient, db_session: Session) -> dict:
    return headers_for(client, db_session, UserRole.OWNER)


def create_key(client: TestClient, owner: dict, **overrides) -> dict:
    response = client.post(
        "/admin/api-keys", json={**NEW_KEY, **overrides}, headers=owner
    )
    assert response.status_code == 201
    return response.json()


def test_the_owner_creates_a_key_shown_once_and_stored_as_a_hash(
    client: TestClient,
    db_session: Session,
    owner: dict,
) -> None:
    created = create_key(client, owner)

    key = created["key"]
    scheme, prefix, secret = key.split("_", 2)
    assert scheme == "sck"
    assert created["api_key"]["prefix"] == prefix
    assert created["api_key"]["name"] == "GitHub audit log"
    assert created["api_key"]["source"] == "github"
    assert created["api_key"]["revoked_at"] is None
    assert created["api_key"]["last_used_at"] is None
    assert "secret_hash" not in created["api_key"]
    expires_at = datetime.fromisoformat(created["api_key"]["expires_at"])
    remaining = expires_at - datetime.now(UTC)
    assert timedelta(days=89) < remaining <= timedelta(days=90)

    stored = db_session.scalar(select(ApiKey))
    assert stored is not None
    assert secret not in stored.secret_hash
    assert len(stored.secret_hash) == 64

    message = (
        f"Owner created API key {prefix} (GitHub audit log) for source github, "
        "valid for 90 days"
    )
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.event_type == AuditEventType.API_KEY_CREATED)
    )
    event = db_session.scalar(
        select(SecurityEvent).where(
            SecurityEvent.event_type == SecurityEventType.API_KEY_CREATED
        )
    )
    assert audit is not None and audit.message == message
    assert event is not None and event.message == message


def test_keys_are_listed_without_secrets_and_the_listing_is_audited(
    client: TestClient,
    db_session: Session,
    owner: dict,
) -> None:
    create_key(client, owner, name="First key", source="k8s-audit")
    create_key(client, owner, name="Second key")
    analyst = headers_for(client, db_session, UserRole.SECURITY_ANALYST)

    response = client.get("/admin/api-keys", headers=analyst)

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == ["Second key", "First key"]
    assert all(
        "key" not in item and "secret_hash" not in item for item in response.json()
    )
    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.event_type == AuditEventType.API_KEYS_VIEWED)
    ).all()
    assert len(audit) == 1


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.SECURITY_ANALYST])
def test_only_the_owner_issues_and_revokes_keys(
    client: TestClient,
    db_session: Session,
    owner: dict,
    role: UserRole,
) -> None:
    key_id = create_key(client, owner)["api_key"]["id"]
    operator = headers_for(client, db_session, role)

    assert (
        client.post("/admin/api-keys", json=NEW_KEY, headers=operator).status_code
        == 403
    )
    assert (
        client.post(f"/admin/api-keys/{key_id}/revoke", headers=operator).status_code
        == 403
    )


def test_regular_users_cannot_see_keys(client: TestClient, db_session: Session) -> None:
    user = headers_for(client, db_session, UserRole.USER)
    assert client.get("/admin/api-keys", headers=user).status_code == 403


@pytest.mark.parametrize(
    "overrides",
    [
        {"source": "backend"},
        {"source": "detection"},
        {"source": " Backend "},
        {"source": "has space"},
        {"source": "x"},
        {"expires_in_days": 45},
        {"expires_in_days": None},
        {"name": "ab"},
        {"scopes": ["all"]},
    ],
)
def test_invalid_keys_are_refused(
    client: TestClient,
    owner: dict,
    overrides: dict,
) -> None:
    response = client.post(
        "/admin/api-keys", json={**NEW_KEY, **overrides}, headers=owner
    )
    assert response.status_code == 422


def test_the_source_is_stored_lowercase(client: TestClient, owner: dict) -> None:
    assert (
        create_key(client, owner, source="  GitHub ")["api_key"]["source"] == "github"
    )


def test_the_owner_revokes_a_key_once(
    client: TestClient,
    db_session: Session,
    owner: dict,
) -> None:
    created = create_key(client, owner)
    key_id = created["api_key"]["id"]

    first = client.post(f"/admin/api-keys/{key_id}/revoke", headers=owner)
    second = client.post(f"/admin/api-keys/{key_id}/revoke", headers=owner)

    assert first.status_code == 200
    assert first.json()["revoked_at"] is not None
    assert second.json()["revoked_at"] == first.json()["revoked_at"]
    revoked = db_session.scalars(
        select(SecurityEvent).where(
            SecurityEvent.event_type == SecurityEventType.API_KEY_REVOKED
        )
    ).all()
    assert len(revoked) == 1
    prefix = created["api_key"]["prefix"]
    assert revoked[0].message == f"Owner revoked API key {prefix} (GitHub audit log)"


def test_revoking_an_unknown_key_returns_404(client: TestClient, owner: dict) -> None:
    assert client.post("/admin/api-keys/999/revoke", headers=owner).status_code == 404
