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
    assert isinstance(response.json()["items"], list)
    assert "next_cursor" in response.json()


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
    assert isinstance(response.json()["items"], list)
    assert "next_cursor" in response.json()


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
    assert data["next_cursor"] is None
    assert len(data["items"]) == 1
    assert data["items"][0]["email"] == "test@example.com"
    assert data["items"][0]["username"] == "testuser"
    assert "hashed_password" not in data["items"][0]


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
                AuditLog.event_type == AuditEventType.USER_ROLE_CHANGED
            )
        ).all()
    )

    assert len(audit_logs) == 1
    assert audit_logs[0].user_id == owner_id
    assert audit_logs[0].target_user_id == target_id
    assert audit_logs[0].email == "owner@example.com"
    assert audit_logs[0].message == expected_message

    security_events = list(
        db_session.scalars(
            select(SecurityEvent).where(
                SecurityEvent.event_type == SecurityEventType.USER_ROLE_CHANGED
            )
        ).all()
    )

    assert len(security_events) == 1
    assert security_events[0].user_id == owner_id
    assert security_events[0].target_user_id == target_id
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
            AuditLog.event_type == AuditEventType.USER_ROLE_CHANGED
        )
    )
    security_event_id = db_session.scalar(
        select(SecurityEvent.id).where(
            SecurityEvent.event_type == SecurityEventType.USER_ROLE_CHANGED
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
            AuditLog.event_type == AuditEventType.USER_ROLE_CHANGED
        )
    )
    security_event_id = db_session.scalar(
        select(SecurityEvent.id).where(
            SecurityEvent.event_type == SecurityEventType.USER_ROLE_CHANGED
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


@pytest.mark.parametrize("operation", ["role", "status"])
def test_user_change_commit_failure_rolls_back_change_and_events(
    client: TestClient,
    db_session: Session,
    owner_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    register_user(client)
    target_id = get_user_id_by_email(db_session, "test@example.com")

    # Flush first so the change and events reach the open transaction, as they
    # would in a commit that fails at the database. Only a rollback undoes them.
    def failing_commit() -> None:
        db_session.flush()
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    body = {"role": "admin"} if operation == "role" else {"is_active": False}
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        client.patch(
            f"/admin/users/{target_id}/{operation}",
            json=body,
            headers=owner_headers,
        )

    monkeypatch.undo()
    db_session.expire_all()
    target_user = db_session.get(User, target_id)
    assert target_user is not None
    assert target_user.role == UserRole.USER
    assert target_user.is_active is True
    assert_no_user_change_events(db_session)


def create_user_with_role(
    client: TestClient,
    db_session: Session,
    username: str,
    role: UserRole,
    is_active: bool = True,
) -> int:
    email = f"{username}@example.com"
    register_user(client, username=username, email=email)
    set_user_role(db_session, email, role)

    user_id = get_user_id_by_email(db_session, email)
    if not is_active:
        user = db_session.get(User, user_id)
        assert user is not None
        user.is_active = False
        db_session.commit()

    return user_id


def assert_no_user_change_events(db_session: Session) -> None:
    change_audit_types = (
        AuditEventType.USER_ROLE_CHANGED,
        AuditEventType.USER_ACTIVATED,
        AuditEventType.USER_DEACTIVATED,
    )
    change_security_types = (
        SecurityEventType.USER_ROLE_CHANGED,
        SecurityEventType.USER_ACTIVATED,
        SecurityEventType.USER_DEACTIVATED,
    )

    audit_log_id = db_session.scalar(
        select(AuditLog.id).where(AuditLog.event_type.in_(change_audit_types))
    )
    security_event_id = db_session.scalar(
        select(SecurityEvent.id).where(
            SecurityEvent.event_type.in_(change_security_types)
        )
    )
    assert audit_log_id is None
    assert security_event_id is None


def test_change_user_status_without_token_returns_401(client: TestClient) -> None:
    response = client.patch(
        "/admin/users/9999/status",
        json={"is_active": False},
    )

    assert response.status_code == 401


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.SECURITY_ANALYST])
def test_change_user_status_without_admin_or_owner_returns_403(
    client: TestClient,
    db_session: Session,
    role: UserRole,
) -> None:
    create_user_with_role(client, db_session, "actor", role)
    target_id = create_user_with_role(client, db_session, "target", UserRole.USER)
    token = login_user(client, email="actor@example.com")

    response = client.patch(
        f"/admin/users/{target_id}/status",
        json={"is_active": False},
        headers=auth_headers(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"

    db_session.expire_all()
    target_user = db_session.get(User, target_id)
    assert target_user is not None
    assert target_user.is_active is True
    assert_no_user_change_events(db_session)


@pytest.mark.parametrize(
    ("actor_role", "target_role", "initially_active", "new_is_active"),
    [
        (UserRole.ADMIN, UserRole.USER, True, False),
        (UserRole.ADMIN, UserRole.SECURITY_ANALYST, True, False),
        (UserRole.ADMIN, UserRole.USER, False, True),
        (UserRole.OWNER, UserRole.ADMIN, True, False),
        (UserRole.OWNER, UserRole.ADMIN, False, True),
    ],
)
def test_change_user_status_updates_target_and_records_events(
    client: TestClient,
    db_session: Session,
    actor_role: UserRole,
    target_role: UserRole,
    initially_active: bool,
    new_is_active: bool,
) -> None:
    actor_id = create_user_with_role(client, db_session, "actor", actor_role)
    target_id = create_user_with_role(
        client, db_session, "target", target_role, is_active=initially_active
    )
    token = login_user(client, email="actor@example.com")

    response = client.patch(
        f"/admin/users/{target_id}/status",
        json={"is_active": new_is_active},
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == target_id
    assert data["is_active"] is new_is_active
    assert "hashed_password" not in data

    db_session.expire_all()
    target_user = db_session.get(User, target_id)
    assert target_user is not None
    assert target_user.is_active is new_is_active

    action = "activated" if new_is_active else "deactivated"
    expected_message = f"{actor_role.value.capitalize()} {action} user_id={target_id}"
    audit_type = (
        AuditEventType.USER_ACTIVATED
        if new_is_active
        else AuditEventType.USER_DEACTIVATED
    )
    security_type = (
        SecurityEventType.USER_ACTIVATED
        if new_is_active
        else SecurityEventType.USER_DEACTIVATED
    )

    audit_logs = list(
        db_session.scalars(
            select(AuditLog).where(AuditLog.event_type == audit_type)
        ).all()
    )
    assert len(audit_logs) == 1
    assert audit_logs[0].user_id == actor_id
    assert audit_logs[0].target_user_id == target_id
    assert audit_logs[0].email == "actor@example.com"
    assert audit_logs[0].message == expected_message

    security_events = list(
        db_session.scalars(
            select(SecurityEvent).where(SecurityEvent.event_type == security_type)
        ).all()
    )
    assert len(security_events) == 1
    assert security_events[0].user_id == actor_id
    assert security_events[0].target_user_id == target_id
    assert security_events[0].email == "actor@example.com"
    assert security_events[0].severity == SecuritySeverity.INFO
    assert security_events[0].message == expected_message


@pytest.mark.parametrize(
    ("actor_role", "target_is_actor", "target_role", "expected_detail"),
    [
        (
            UserRole.ADMIN,
            True,
            UserRole.ADMIN,
            "Users cannot change their own status",
        ),
        (
            UserRole.OWNER,
            True,
            UserRole.OWNER,
            "Users cannot change their own status",
        ),
        (
            UserRole.ADMIN,
            False,
            UserRole.OWNER,
            "Cannot change the status of an owner",
        ),
        (
            UserRole.OWNER,
            False,
            UserRole.OWNER,
            "Cannot change the status of an owner",
        ),
        (
            UserRole.ADMIN,
            False,
            UserRole.ADMIN,
            "Only an owner can change the status of an admin",
        ),
    ],
)
def test_change_user_status_restrictions_leave_target_unchanged(
    client: TestClient,
    db_session: Session,
    actor_role: UserRole,
    target_is_actor: bool,
    target_role: UserRole,
    expected_detail: str,
) -> None:
    actor_id = create_user_with_role(client, db_session, "actor", actor_role)
    if target_is_actor:
        target_id = actor_id
    else:
        target_id = create_user_with_role(client, db_session, "target", target_role)
    token = login_user(client, email="actor@example.com")

    response = client.patch(
        f"/admin/users/{target_id}/status",
        json={"is_active": False},
        headers=auth_headers(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == expected_detail

    db_session.expire_all()
    target_user = db_session.get(User, target_id)
    assert target_user is not None
    assert target_user.is_active is True
    assert_no_user_change_events(db_session)


def test_change_user_status_with_unknown_target_returns_404(
    client: TestClient,
    db_session: Session,
    owner_headers: dict[str, str],
) -> None:
    response = client.patch(
        "/admin/users/999999/status",
        json={"is_active": False},
        headers=owner_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
    assert_no_user_change_events(db_session)


@pytest.mark.parametrize("value", ["false", 0, None])
def test_change_user_status_with_non_boolean_returns_422(
    client: TestClient,
    db_session: Session,
    owner_headers: dict[str, str],
    value: object,
) -> None:
    register_user(client)
    target_id = get_user_id_by_email(db_session, "test@example.com")

    response = client.patch(
        f"/admin/users/{target_id}/status",
        json={"is_active": value},
        headers=owner_headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "is_active"]

    db_session.expire_all()
    target_user = db_session.get(User, target_id)
    assert target_user is not None
    assert target_user.is_active is True
    assert_no_user_change_events(db_session)


def test_change_user_status_to_same_status_creates_no_change_events(
    client: TestClient,
    db_session: Session,
    owner_headers: dict[str, str],
) -> None:
    register_user(client)
    target_id = get_user_id_by_email(db_session, "test@example.com")

    response = client.patch(
        f"/admin/users/{target_id}/status",
        json={"is_active": True},
        headers=owner_headers,
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is True
    assert_no_user_change_events(db_session)


def test_deactivated_user_loses_access_immediately(
    client: TestClient,
    db_session: Session,
    owner_headers: dict[str, str],
) -> None:
    register_user(client)
    target_id = get_user_id_by_email(db_session, "test@example.com")
    target_token = login_user(client)

    response = client.patch(
        f"/admin/users/{target_id}/status",
        json={"is_active": False},
        headers=owner_headers,
    )
    assert response.status_code == 200

    me_response = client.get("/users/me", headers=auth_headers(target_token))
    assert me_response.status_code == 403
    assert me_response.json()["detail"] == "Inactive user"

    login_response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "testpassword"},
    )
    assert login_response.status_code == 403
    assert login_response.json()["detail"] == "Inactive user"
