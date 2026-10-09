import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import DUMMY_PASSWORD_HASH, hash_password
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import SecurityEvent, SecurityEventType
from app.models.user import User
from app.services import user_service
from tests.accounts import create_account


def test_login_success_returns_token(client: TestClient) -> None:
    create_account()

    response = client.post(
        "/auth/login",
        json={"email": "testuser@example.com", "password": "testpassword"},
    )

    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password_returns_401(client: TestClient) -> None:
    create_account()

    response = client.post(
        "/auth/login",
        json={"email": "testuser@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_unknown_email_returns_401_and_still_verifies_a_hash(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified_hashes: list[str] = []
    real_verify_password = user_service.verify_password

    def spy_verify_password(password: str, hashed_password: str) -> bool:
        verified_hashes.append(hashed_password)
        return real_verify_password(password, hashed_password)

    monkeypatch.setattr(user_service, "verify_password", spy_verify_password)

    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "testpassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
    assert verified_hashes == [DUMMY_PASSWORD_HASH]


def test_login_inactive_user_returns_403_and_records_failed_login(
    client: TestClient,
    db_session: Session,
) -> None:
    create_account()
    user = db_session.scalar(select(User).where(User.email == "testuser@example.com"))
    assert user is not None
    user.is_active = False
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": "testuser@example.com", "password": "testpassword"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user"
    assert "access_token" not in response.json()

    expected_message = "Login attempt for inactive user: testuser@example.com"
    audit_messages = db_session.scalars(
        select(AuditLog.message).where(
            AuditLog.event_type == AuditEventType.LOGIN_FAILED
        )
    ).all()
    security_messages = db_session.scalars(
        select(SecurityEvent.message).where(
            SecurityEvent.event_type == SecurityEventType.LOGIN_FAILED
        )
    ).all()

    assert audit_messages == [expected_message]
    assert security_messages == [expected_message]


def test_login_email_is_case_insensitive(client: TestClient) -> None:
    create_account()

    response = client.post(
        "/auth/login",
        json={"email": "TestUser@EXAMPLE.com", "password": "testpassword"},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_oversized_password_returns_422(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": "testuser@example.com", "password": "x" * 129},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "password"]


def test_login_does_not_enforce_new_password_minimum(
    client: TestClient,
    db_session: Session,
) -> None:
    # Accounts created before the password policy may have shorter passwords.
    create_account()
    user = db_session.scalar(select(User))
    assert user is not None
    user.hashed_password = hash_password("short")
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": "testuser@example.com", "password": "short"},
    )

    assert response.status_code == 200


def test_there_is_no_public_sign_up(client: TestClient, db_session: Session) -> None:
    # Accounts join through invitations (test_invitations.py).
    response = client.post(
        "/auth/register",
        json={
            "username": "stranger",
            "email": "stranger@example.com",
            "password": "testpassword",
        },
    )

    assert response.status_code == 404
    assert db_session.scalar(select(func.count()).select_from(User)) == 0
