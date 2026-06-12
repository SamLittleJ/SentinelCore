from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

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
