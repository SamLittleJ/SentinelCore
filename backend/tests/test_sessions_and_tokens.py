import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.models.audit_log import AuditEventType, AuditLog
from app.models.user import User, UserRole
from app.models.user_session import UserSession

PASSWORD = "testpassword"


def register(client: TestClient, username: str = "testuser") -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201


def login(
    client: TestClient,
    username: str = "testuser",
    user_agent: str = "pytest-agent",
) -> str:
    response = client.post(
        "/auth/login",
        json={"email": f"{username}@example.com", "password": PASSWORD},
        headers={"User-Agent": user_agent},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def me_status(client: TestClient, token: str) -> int:
    return client.get("/users/me", headers=bearer(token)).status_code


def get_user(db_session: Session, username: str = "testuser") -> User:
    user = db_session.scalar(select(User).where(User.username == username))
    assert user is not None
    return user


def sign(claims: dict[str, object], key: str | None = None, algorithm="HS256") -> str:
    return jwt.encode(claims, key or settings.secret_key, algorithm=algorithm)


def valid_claims(user_id: int, session_id: uuid.UUID) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user_id),
        "jti": str(session_id),
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }


# Token contents


def test_login_token_identifies_user_and_session(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    response = client.post(
        "/auth/login",
        json={"email": "testuser@example.com", "password": PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.access_token_expire_minutes * 60

    claims = jwt.decode(
        body["access_token"],
        settings.secret_key,
        algorithms=[settings.algorithm],
        audience=settings.jwt_audience,
    )
    user = get_user(db_session)
    session = db_session.get(UserSession, uuid.UUID(claims["jti"]))

    assert claims["iss"] == settings.jwt_issuer
    assert claims["sub"] == str(user.id)
    assert session is not None
    assert session.user_id == user.id
    assert claims["exp"] - claims["iat"] == settings.access_token_expire_minutes * 60


def _claims_variants(user_id: int, session_id: uuid.UUID) -> dict[str, str]:
    claims = valid_claims(user_id, session_id)

    def without(name: str) -> dict[str, object]:
        return {key: value for key, value in claims.items() if key != name}

    now = datetime.now(UTC)
    return {
        "wrong key": sign(claims, key="another-secret-key-that-is-long-enough"),
        "wrong issuer": sign({**claims, "iss": "someone-else"}),
        "wrong audience": sign({**claims, "aud": "another-api"}),
        "missing jti": sign(without("jti")),
        "missing sub": sign(without("sub")),
        "missing iat": sign(without("iat")),
        "non-numeric sub": sign({**claims, "sub": "testuser@example.com"}),
        "non-uuid jti": sign({**claims, "jti": "not-a-uuid"}),
        "expired": sign(
            {
                **claims,
                "iat": now - timedelta(hours=2),
                "exp": now - timedelta(hours=1),
            }
        ),
        "other algorithm": sign(claims, algorithm="HS512"),
        "unsigned": jwt.encode(claims, key=None, algorithm="none"),
        "legacy email token": sign(
            {"sub": "testuser@example.com", "exp": now + timedelta(minutes=5)}
        ),
        "unknown session": sign({**claims, "jti": str(uuid.uuid4())}),
    }


@pytest.mark.parametrize(
    "variant",
    [
        "wrong key",
        "wrong issuer",
        "wrong audience",
        "missing jti",
        "missing sub",
        "missing iat",
        "non-numeric sub",
        "non-uuid jti",
        "expired",
        "other algorithm",
        "unsigned",
        "legacy email token",
        "unknown session",
    ],
)
def test_invalid_tokens_are_rejected(
    client: TestClient,
    db_session: Session,
    variant: str,
) -> None:
    register(client)
    token = login(client)
    claims = jwt.decode(token, options={"verify_signature": False})
    user = get_user(db_session)

    forged = _claims_variants(user.id, uuid.UUID(claims["jti"]))[variant]
    response = client.get("/users/me", headers=bearer(forged))

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    # The genuine token keeps working.
    assert me_status(client, token) == 200


def test_session_of_another_user_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client, "alice")
    register(client, "bob")
    bob_token = login(client, "bob")
    bob_session_id = jwt.decode(bob_token, options={"verify_signature": False})["jti"]

    forged = sign(valid_claims(get_user(db_session, "alice").id, bob_session_id))

    assert me_status(client, forged) == 401


# Settings


@pytest.mark.parametrize("secret_key", ["short", "x" * 31])
def test_short_secret_key_is_rejected(secret_key: str) -> None:
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        Settings(database_url="postgresql://unused", secret_key=secret_key)


@pytest.mark.parametrize("algorithm", ["none", "RS256"])
def test_only_hmac_algorithms_are_allowed(algorithm: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql://unused",
            secret_key="x" * 32,
            algorithm=algorithm,  # type: ignore[arg-type]
        )


# Sessions


def test_login_creates_a_session_listed_with_current_flag(
    client: TestClient,
) -> None:
    register(client)
    first = login(client, user_agent="laptop-browser")
    second = login(client, user_agent="phone-app")

    response = client.get("/users/me/sessions", headers=bearer(second))

    assert response.status_code == 200
    sessions = response.json()
    assert [s["user_agent"] for s in sessions] == ["phone-app", "laptop-browser"]
    assert [s["current"] for s in sessions] == [True, False]
    assert me_status(client, first) == 200


def test_logout_revokes_only_the_current_session(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    first = login(client)
    second = login(client)

    response = client.post("/auth/logout", headers=bearer(first))

    assert response.status_code == 204
    assert me_status(client, first) == 401
    assert me_status(client, second) == 200

    messages = db_session.scalars(
        select(AuditLog.message).where(
            AuditLog.event_type == AuditEventType.SESSION_REVOKED
        )
    ).all()
    assert len(messages) == 1
    assert messages[0] is not None
    assert messages[0].startswith("User logged out, session_id=")


def test_logout_all_revokes_every_session(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    tokens = [login(client) for _ in range(3)]

    response = client.post("/auth/logout-all", headers=bearer(tokens[0]))

    assert response.status_code == 204
    assert [me_status(client, token) for token in tokens] == [401, 401, 401]
    assert db_session.scalar(
        select(AuditLog.id).where(
            AuditLog.event_type == AuditEventType.ALL_SESSIONS_REVOKED
        )
    )


def test_user_can_revoke_one_of_their_other_sessions(
    client: TestClient,
) -> None:
    register(client)
    current = login(client)
    other = login(client)
    other_id = jwt.decode(other, options={"verify_signature": False})["jti"]

    response = client.delete(f"/users/me/sessions/{other_id}", headers=bearer(current))

    assert response.status_code == 204
    assert me_status(client, other) == 401
    assert me_status(client, current) == 200


def test_sessions_of_other_users_cannot_be_revoked(
    client: TestClient,
) -> None:
    register(client, "alice")
    register(client, "bob")
    alice = login(client, "alice")
    bob = login(client, "bob")
    bob_session_id = jwt.decode(bob, options={"verify_signature": False})["jti"]

    response = client.delete(
        f"/users/me/sessions/{bob_session_id}", headers=bearer(alice)
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"
    assert me_status(client, bob) == 200


@pytest.mark.parametrize(
    ("session_id", "expected_status"),
    [(str(uuid.uuid4()), 404), ("not-a-uuid", 422)],
)
def test_revoking_unknown_or_malformed_session_id(
    client: TestClient,
    session_id: str,
    expected_status: int,
) -> None:
    register(client)
    token = login(client)

    response = client.delete(f"/users/me/sessions/{session_id}", headers=bearer(token))

    assert response.status_code == expected_status


def test_expired_session_is_rejected_and_not_listed(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    expired = login(client)
    current = login(client)
    expired_id = uuid.UUID(
        jwt.decode(expired, options={"verify_signature": False})["jti"]
    )

    db_session.execute(
        update(UserSession)
        .where(UserSession.id == expired_id)
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    db_session.commit()

    assert me_status(client, expired) == 401
    current_id = jwt.decode(current, options={"verify_signature": False})["jti"]
    listed = client.get("/users/me/sessions", headers=bearer(current)).json()
    assert [session["id"] for session in listed] == [current_id]


def test_deactivation_revokes_sessions_and_reactivation_does_not_restore_them(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client, "owneruser")
    owner = get_user(db_session, "owneruser")
    owner.role = UserRole.OWNER
    db_session.commit()
    owner_token = login(client, "owneruser")

    register(client)
    target = get_user(db_session)
    target_token = login(client)

    for is_active in (False, True):
        response = client.patch(
            f"/admin/users/{target.id}/status",
            json={"is_active": is_active},
            headers=bearer(owner_token),
        )
        assert response.status_code == 200

    db_session.expire_all()
    sessions = db_session.scalars(
        select(UserSession).where(UserSession.user_id == target.id)
    ).all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is not None
    assert me_status(client, target_token) == 401
    # A fresh login works after reactivation.
    assert me_status(client, login(client)) == 200


# OAuth2 form login (Swagger UI)


def test_oauth2_form_login_issues_a_working_token(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/auth/token",
        data={"username": "TestUser@Example.com", "password": PASSWORD},
    )

    assert response.status_code == 200
    assert me_status(client, response.json()["access_token"]) == 200


def test_oauth2_form_login_shares_brute_force_protection(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "login_max_failed_attempts", 2)
    register(client)

    statuses = [
        client.post(
            "/auth/token",
            data={"username": "testuser@example.com", "password": "wrongpassword"},
        ).status_code
        for _ in range(2)
    ]
    json_login = client.post(
        "/auth/login",
        json={"email": "testuser@example.com", "password": PASSWORD},
    )

    assert statuses == [401, 429]
    assert json_login.status_code == 429


def test_oauth2_form_login_rejects_invalid_email(client: TestClient) -> None:
    response = client.post(
        "/auth/token",
        data={"username": "not-an-email", "password": PASSWORD},
    )

    assert response.status_code == 422


def test_openapi_points_swagger_to_the_form_login(client: TestClient) -> None:
    schemes = client.get("/openapi.json").json()["components"]["securitySchemes"]

    assert schemes["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"] == (
        "/auth/token"
    )
