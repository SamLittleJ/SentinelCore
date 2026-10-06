import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import SecurityEvent, SecurityEventType, SecuritySeverity
from app.models.user import User, UserRole


def register_user(
    client: TestClient,
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = "testpassword",
) -> None:
    response = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )

    assert response.status_code == 201


def login_user(
    client: TestClient, email: str = "test@example.com", password: str = "testpassword"
) -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 200

    data = response.json()
    return data["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def promote_user_to_admin(db_session: Session, email: str) -> None:
    user = db_session.scalar(select(User).where(User.email == email))

    assert user is not None

    user.role = UserRole.ADMIN
    db_session.commit()


def test_users_me_with_valid_token_returns_current_user(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.get(
        "/users/me",
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "hashed_password" not in data


def test_users_me_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/users/me")

    assert response.status_code == 401


def test_users_me_with_token_of_deactivated_user_returns_403(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    token = login_user(client)

    user = db_session.scalar(select(User).where(User.email == "test@example.com"))
    assert user is not None
    user.is_active = False
    db_session.commit()

    response = client.get(
        "/users/me",
        headers=auth_headers(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user"


def test_admin_only_with_regular_user_returns_403(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.get(
        "/users/admin-only",
        headers=auth_headers(token),
    )

    assert response.status_code == 403


def test_admin_only_with_admin_user_returns_200(
    client: TestClient, db_session: Session
) -> None:
    register_user(client)
    promote_user_to_admin(db_session, "test@example.com")
    token = login_user(client)

    response = client.get(
        "/users/admin-only",
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    data = response.json()
    assert data["username"] == "testuser"
    assert data["role"] == "admin"


def test_audit_logs_endpoint_with_admin_returns_200(
    client: TestClient, db_session: Session
) -> None:
    register_user(client)
    promote_user_to_admin(db_session, "test@example.com")
    token = login_user(client)

    response = client.get(
        "/admin/audit-logs?limit=20",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_security_events_endpoint_with_admin_returns_200(
    client: TestClient, db_session: Session
) -> None:
    register_user(client)
    promote_user_to_admin(db_session, "test@example.com")
    token = login_user(client)

    response = client.get(
        "/security/events?limit=20",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_admin_users_with_regular_user_returns_403(client: TestClient) -> None:
    register_user(client)
    token = login_user(client)

    response = client.get(
        "/admin/users",
        headers=auth_headers(token),
    )

    assert response.status_code == 403


def test_admin_users_with_admin_user_returns_users(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    promote_user_to_admin(db_session, "test@example.com")
    token = login_user(client)

    response = client.get(
        "/admin/users",
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["email"] == "test@example.com"
    assert data[0]["username"] == "testuser"
    assert "hashed_password" not in data[0]


def get_user_id_by_email(db_session: Session, email: str) -> int:
    user = db_session.scalar(select(User.id).where(User.email == email))

    assert user is not None

    return user


def test_admin_user_detail_with_reqular_user_returns_403(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    user_id = get_user_id_by_email(db_session, "test@example.com")
    token = login_user(client)

    response = client.get(
        f"/admin/users/{user_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 403


def test_admin_user_detail_with_admin_user_returns_user(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    user_id = get_user_id_by_email(db_session, "test@example.com")
    promote_user_to_admin(db_session, "test@example.com")
    token = login_user(client)

    response = client.get(
        f"/admin/users/{user_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert "hashed_password" not in data


def test_admin_user_detail_with_unknown_user_returns_404(
    client: TestClient,
    db_session: Session,
) -> None:
    register_user(client)
    promote_user_to_admin(db_session, "test@example.com")
    token = login_user(client)

    response = client.get(
        "/admin/users/9999",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def set_user_role(
    db_session: Session,
    email: str,
    role: UserRole,
) -> None:
    user = db_session.scalar(select(User).where(User.email == email))

    assert user is not None

    user.role = role
    db_session.commit()


def test_change_user_role_without_token_returns_401(
    client: TestClient,
) -> None:
    response = client.patch(
        "/admin/users/9999/role",
        json={"role": "admin"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [UserRole.USER, UserRole.ADMIN, UserRole.SECURITY_ANALYST],
)
def test_change_user_role_without_owner_returns_403(
    client: TestClient,
    db_session: Session,
    role: UserRole,
) -> None:
    register_user(client)
    set_user_role(db_session, "test@example.com", role)

    register_user(
        client,
        username="targetuser",
        email="target@example.com",
    )
    target_id = get_user_id_by_email(db_session, "target@example.com")
    token = login_user(client)

    response = client.patch(
        f"/admin/users/{target_id}/role",
        json={"role": "admin"},
        headers=auth_headers(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"

    db_session.expire_all()
    target_user = db_session.get(User, target_id)

    assert target_user is not None
    assert target_user.role == UserRole.USER


@pytest.mark.parametrize(
    ("initial_role", "new_role"),
    [
        (UserRole.USER, UserRole.ADMIN),
        (UserRole.ADMIN, UserRole.USER),
        (UserRole.USER, UserRole.SECURITY_ANALYST),
    ],
)
def test_owner_changes_user_role_and_records_events(
    client: TestClient,
    db_session: Session,
    initial_role: UserRole,
    new_role: UserRole,
) -> None:
    register_user(
        client,
        username="owneruser",
        email="owner@example.com",
    )
    set_user_role(db_session, "owner@example.com", UserRole.OWNER)
    owner_id = get_user_id_by_email(db_session, "owner@example.com")

    register_user(client)
    set_user_role(db_session, "test@example.com", initial_role)
    target_id = get_user_id_by_email(db_session, "test@example.com")

    token = login_user(client, email="owner@example.com")

    response = client.patch(
        f"/admin/users/{target_id}/role",
        json={"role": new_role.value},
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == target_id
    assert data["role"] == new_role.value
    assert "hashed_password" not in data

    db_session.expire_all()
    target_user = db_session.get(User, target_id)

    assert target_user is not None
    assert target_user.role == new_role

    expected_message = (
        f"Owner changed role for user_id={target_id} "
        f"from {initial_role.value} to {new_role.value}"
    )

    audit_logs = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.ADMIN_ENDPOINT_ACCESSED
            )
        ).all()
    )

    assert len(audit_logs) == 1
    assert audit_logs[0].user_id == owner_id
    assert audit_logs[0].email == "owner@example.com"
    assert audit_logs[0].message == expected_message

    security_events = list(
        db_session.scalars(
            select(SecurityEvent).where(
                SecurityEvent.event_type == SecurityEventType.ADMIN_ACCESS
            )
        ).all()
    )

    assert len(security_events) == 1
    assert security_events[0].user_id == owner_id
    assert security_events[0].email == "owner@example.com"
    assert security_events[0].severity == SecuritySeverity.INFO
    assert security_events[0].message == expected_message


@pytest.mark.parametrize(
    ("target_is_actor", "initial_role", "new_role", "expected_detail"),
    [
        (
            True,
            UserRole.OWNER,
            UserRole.USER,
            "Owners cannot change their own role",
        ),
        (
            False,
            UserRole.OWNER,
            UserRole.ADMIN,
            "Cannot change the role of an owner",
        ),
        (
            False,
            UserRole.USER,
            UserRole.OWNER,
            "Cannot promote a user to owner",
        ),
    ],
)
def test_owner_role_restrictions_leave_target_unchanged(
    client: TestClient,
    db_session: Session,
    target_is_actor: bool,
    initial_role: UserRole,
    new_role: UserRole,
    expected_detail: str,
) -> None:
    register_user(
        client,
        username="owneruser",
        email="owner@example.com",
    )
    set_user_role(db_session, "owner@example.com", UserRole.OWNER)
    owner_id = get_user_id_by_email(db_session, "owner@example.com")

    if target_is_actor:
        target_id = owner_id
    else:
        register_user(client)
        set_user_role(db_session, "test@example.com", initial_role)
        target_id = get_user_id_by_email(db_session, "test@example.com")

    token = login_user(client, email="owner@example.com")

    response = client.patch(
        f"/admin/users/{target_id}/role",
        json={"role": new_role.value},
        headers=auth_headers(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == expected_detail

    db_session.expire_all()
    target_user = db_session.get(User, target_id)

    assert target_user is not None
    assert target_user.role == initial_role

    audit_log_id = db_session.scalar(
        select(AuditLog.id).where(
            AuditLog.event_type == AuditEventType.ADMIN_ENDPOINT_ACCESSED
        )
    )
    security_event_id = db_session.scalar(
        select(SecurityEvent.id).where(
            SecurityEvent.event_type == SecurityEventType.ADMIN_ACCESS
        )
    )

    assert audit_log_id is None
    assert security_event_id is None


@pytest.fixture()
def owner_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    register_user(client, username="owneruser", email="owner@example.com")
    set_user_role(db_session, "owner@example.com", UserRole.OWNER)
    token = login_user(client, email="owner@example.com")
    return auth_headers(token)


def assert_no_role_change_events(db_session: Session) -> None:
    audit_log_id = db_session.scalar(
        select(AuditLog.id).where(
            AuditLog.event_type == AuditEventType.ADMIN_ENDPOINT_ACCESSED
        )
    )
    security_event_id = db_session.scalar(
        select(SecurityEvent.id).where(
            SecurityEvent.event_type == SecurityEventType.ADMIN_ACCESS
        )
    )
    assert audit_log_id is None
    assert security_event_id is None


def test_change_user_role_with_unknown_target_returns_404(
    client: TestClient,
    db_session: Session,
    owner_headers: dict[str, str],
) -> None:
    response = client.patch(
        "/admin/users/999999/role",
        json={"role": "admin"},
        headers=owner_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
    assert_no_role_change_events(db_session)


def test_change_user_role_with_invalid_role_returns_422(
    client: TestClient,
    db_session: Session,
    owner_headers: dict[str, str],
) -> None:
    register_user(client)
    target_id = get_user_id_by_email(db_session, "test@example.com")

    response = client.patch(
        f"/admin/users/{target_id}/role",
        json={"role": "manager"},
        headers=owner_headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "role"]

    db_session.expire_all()
    target_user = db_session.get(User, target_id)
    assert target_user is not None
    assert target_user.role == UserRole.USER
    assert_no_role_change_events(db_session)


def test_change_user_role_to_same_role_creates_no_change_events(
    client: TestClient,
    db_session: Session,
    owner_headers: dict[str, str],
) -> None:
    register_user(client)
    target_id = get_user_id_by_email(db_session, "test@example.com")

    response = client.patch(
        f"/admin/users/{target_id}/role",
        json={"role": "user"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == target_id
    assert response.json()["role"] == "user"
    assert "hashed_password" not in response.json()

    db_session.expire_all()
    target_user = db_session.get(User, target_id)
    assert target_user is not None
    assert target_user.role == UserRole.USER
    assert_no_role_change_events(db_session)
