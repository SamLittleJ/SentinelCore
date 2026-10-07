import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes import auth
from app.core.security import DUMMY_PASSWORD_HASH, hash_password
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import SecurityEvent, SecurityEventType
from app.models.user import User
from app.services import user_service


def test_register_creates_user(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "testpassword",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "testuser@example.com"
    assert "hashed_password" not in data


def test_register_duplicate_email_returns_400(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "testpassword",
        },
    )

    response = client.post(
        "/auth/register",
        json={
            "username": "testuser2",
            "email": "testuser@example.com",
            "password": "testpassword2",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_login_success_returns_token(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "testpassword",
        },
    )

    response = client.post(
        "/auth/login",
        json={"email": "testuser@example.com", "password": "testpassword"},
    )

    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password_returns_401(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "testpassword",
        },
    )

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
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "testpassword",
        },
    )
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


@pytest.mark.parametrize(
    ("second_user", "expected_detail"),
    [
        (
            {"username": "otheruser", "email": "testuser@example.com"},
            "Email already registered",
        ),
        (
            {"username": "testuser", "email": "other@example.com"},
            "Username already taken",
        ),
    ],
)
def test_register_duplicate_that_passes_prechecks_returns_400(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    second_user: dict[str, str],
    expected_detail: str,
) -> None:
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "testpassword",
        },
    )

    # Simulate a concurrent registration: the pre-checks see no existing user,
    # so only the database unique indexes can reject the duplicate.
    monkeypatch.setattr(auth, "get_user_by_email", lambda db, email: None)
    monkeypatch.setattr(auth, "get_user_by_username", lambda db, username: None)

    response = client.post(
        "/auth/register",
        json={**second_user, "password": "testpassword"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


VALID_REGISTRATION = {
    "username": "testuser",
    "email": "testuser@example.com",
    "password": "testpassword",
}


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("username", "ab", "string_too_short"),
        ("username", "u" * 51, "string_too_long"),
        ("username", "has space", "string_pattern_mismatch"),
        ("username", "bad!char", "string_pattern_mismatch"),
        ("username", "țară", "string_pattern_mismatch"),
        ("password", "x" * 11, "string_too_short"),
        ("password", "x" * 129, "string_too_long"),
        ("email", "not-an-email", "value_error"),
    ],
)
def test_register_with_invalid_input_returns_422(
    client: TestClient,
    db_session: Session,
    field: str,
    value: str,
    error_type: str,
) -> None:
    response = client.post(
        "/auth/register",
        json={**VALID_REGISTRATION, field: value},
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", field]
    assert error["type"] == error_type
    assert db_session.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("username", "abc"),
        ("username", "u" * 50),
        ("username", "dot.dash-under_score1"),
        ("password", "x" * 12),
        ("password", "x" * 128),
    ],
)
def test_register_accepts_boundary_values(
    client: TestClient,
    field: str,
    value: str,
) -> None:
    response = client.post(
        "/auth/register",
        json={**VALID_REGISTRATION, field: value},
    )

    assert response.status_code == 201


def test_register_stores_email_and_username_lowercase(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": "TestUser",
            "email": "TestUser@Example.COM",
            "password": "testpassword",
        },
    )

    assert response.status_code == 201
    assert response.json()["username"] == "testuser"
    assert response.json()["email"] == "testuser@example.com"

    user = db_session.scalar(select(User))
    assert user is not None
    assert user.username == "testuser"
    assert user.email == "testuser@example.com"


@pytest.mark.parametrize(
    ("second_user", "expected_detail"),
    [
        (
            {"username": "otheruser", "email": "TESTUSER@example.com"},
            "Email already registered",
        ),
        (
            {"username": "TestUser", "email": "other@example.com"},
            "Username already taken",
        ),
    ],
)
def test_register_duplicate_with_different_case_returns_400(
    client: TestClient,
    second_user: dict[str, str],
    expected_detail: str,
) -> None:
    client.post("/auth/register", json=VALID_REGISTRATION)

    response = client.post(
        "/auth/register",
        json={**second_user, "password": "testpassword"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail


def test_login_email_is_case_insensitive(client: TestClient) -> None:
    client.post("/auth/register", json=VALID_REGISTRATION)

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
    client.post("/auth/register", json=VALID_REGISTRATION)
    user = db_session.scalar(select(User))
    assert user is not None
    user.hashed_password = hash_password("short")
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": "testuser@example.com", "password": "short"},
    )

    assert response.status_code == 200
