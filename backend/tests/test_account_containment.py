"""Temporary account locks, used by operators to contain a suspected
compromise. Session revocation by operators is tested with the session tests."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole

PASSWORD = "testpassword"
REASON = "Valid password used from a new country"

# Roles as event messages name them.
ROLE_NAMES = {
    UserRole.ADMIN: "Admin",
    UserRole.OWNER: "Owner",
    UserRole.SECURITY_ANALYST: "Security analyst",
}


def create_user(
    client: TestClient,
    db_session: Session,
    username: str,
    role: UserRole = UserRole.USER,
) -> User:
    email = f"{username}@example.com"
    response = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201

    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = role
    db_session.commit()
    return user


def login_response(client: TestClient, username: str, password: str = PASSWORD):
    return client.post(
        "/auth/login",
        json={"email": f"{username}@example.com", "password": password},
    )


def login(client: TestClient, username: str) -> dict[str, str]:
    response = login_response(client, username)
    assert response.status_code == 200, response.json()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def lock(
    client: TestClient,
    user_id: int,
    headers: dict[str, str],
    duration_hours: int = 24,
    reason: str = REASON,
):
    return client.post(
        f"/admin/users/{user_id}/lock",
        json={"duration_hours": duration_hours, "reason": reason},
        headers=headers,
    )


def unlock(client: TestClient, user_id: int, headers: dict[str, str]):
    return client.post(f"/admin/users/{user_id}/unlock", headers=headers)


def database_now(db_session: Session):
    return db_session.execute(select(func.now())).scalar_one()


def clear_events(db_session: Session) -> None:
    db_session.execute(delete(AuditLog))
    db_session.execute(delete(SecurityEvent))
    db_session.commit()


def security_events(
    db_session: Session, event_type: SecurityEventType
) -> list[SecurityEvent]:
    return list(
        db_session.scalars(
            select(SecurityEvent).where(SecurityEvent.event_type == event_type)
        )
    )


def audit_logs(db_session: Session, event_type: AuditEventType) -> list[AuditLog]:
    return list(
        db_session.scalars(select(AuditLog).where(AuditLog.event_type == event_type))
    )


def test_lock_without_token_returns_401(client: TestClient) -> None:
    response = client.post(
        "/admin/users/1/lock", json={"duration_hours": 1, "reason": REASON}
    )

    assert response.status_code == 401


def test_regular_user_cannot_lock_or_unlock(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "regular")
    target = create_user(client, db_session, "target")
    headers = login(client, "regular")

    assert lock(client, target.id, headers).status_code == 403
    assert unlock(client, target.id, headers).status_code == 403
    assert login_response(client, "target").status_code == 200


@pytest.mark.parametrize(
    ("actor_role", "target_role"),
    [
        (UserRole.SECURITY_ANALYST, UserRole.USER),
        (UserRole.SECURITY_ANALYST, UserRole.ADMIN),
        (UserRole.ADMIN, UserRole.ADMIN),
        (UserRole.OWNER, UserRole.SECURITY_ANALYST),
    ],
)
def test_lock_signs_the_account_out_and_refuses_logins(
    client: TestClient,
    db_session: Session,
    actor_role: UserRole,
    target_role: UserRole,
) -> None:
    actor = create_user(client, db_session, "actor", actor_role)
    target = create_user(client, db_session, "target", target_role)
    target_headers = login(client, "target")
    actor_headers = login(client, "actor")
    clear_events(db_session)
    before = database_now(db_session)

    response = lock(client, target.id, actor_headers, duration_hours=6)

    assert response.status_code == 200
    locked_until = db_session.scalar(
        select(User.locked_until).where(User.id == target.id)
    )
    assert locked_until is not None
    assert (
        before + timedelta(hours=6)
        <= locked_until
        <= database_now(db_session) + timedelta(hours=6)
    )
    assert response.json()["locked_until"] is not None

    # Signed out everywhere, and a login with the right password is refused.
    assert client.get("/users/me", headers=target_headers).status_code == 401
    refused = login_response(client, "target")
    assert refused.status_code == 403
    assert refused.json()["detail"] == "Account temporarily locked"
    # The end of the lock is not revealed.
    assert "Retry-After" not in refused.headers
    # A wrong password answers as usual, revealing nothing about the lock.
    assert login_response(client, "target", "wrong-password").status_code == 401

    expected_message = (
        f"{ROLE_NAMES[actor_role]} locked user_id={target.id} for "
        f"6 hour(s) and revoked 1 session(s). Reason: {REASON}"
    )
    [locked_event] = security_events(db_session, SecurityEventType.ACCOUNT_LOCKED)
    assert locked_event.severity == SecuritySeverity.INCIDENT
    assert locked_event.user_id == actor.id
    assert locked_event.target_user_id == target.id
    assert locked_event.message == expected_message
    [locked_log] = audit_logs(db_session, AuditEventType.ACCOUNT_LOCKED)
    assert (locked_log.user_id, locked_log.target_user_id) == (actor.id, target.id)
    assert locked_log.message == expected_message

    # The attempt with the right password is a signal worth reviewing.
    [blocked] = security_events(db_session, SecurityEventType.LOGIN_BLOCKED)
    assert blocked.user_id == target.id
    assert blocked.severity == SecuritySeverity.WARN
    assert len(audit_logs(db_session, AuditEventType.LOGIN_BLOCKED)) == 1


@pytest.mark.parametrize(
    ("actor_role", "target_is_actor", "target_role", "expected_detail"),
    [
        (
            UserRole.SECURITY_ANALYST,
            True,
            UserRole.SECURITY_ANALYST,
            "Users cannot lock their own account",
        ),
        (UserRole.ADMIN, True, UserRole.ADMIN, "Users cannot lock their own account"),
        (
            UserRole.SECURITY_ANALYST,
            False,
            UserRole.OWNER,
            "Cannot lock an owner",
        ),
        (UserRole.OWNER, False, UserRole.OWNER, "Cannot lock an owner"),
    ],
)
def test_lock_restrictions(
    client: TestClient,
    db_session: Session,
    actor_role: UserRole,
    target_is_actor: bool,
    target_role: UserRole,
    expected_detail: str,
) -> None:
    actor = create_user(client, db_session, "actor", actor_role)
    target = (
        actor
        if target_is_actor
        else create_user(client, db_session, "target", target_role)
    )

    response = lock(client, target.id, login(client, "actor"))

    assert response.status_code == 403
    assert response.json()["detail"] == expected_detail
    db_session.expire_all()
    stored = db_session.get(User, target.id)
    assert stored is not None
    assert stored.locked_until is None
    assert security_events(db_session, SecurityEventType.ACCOUNT_LOCKED) == []


@pytest.mark.parametrize(
    "body",
    [
        {"duration_hours": 0, "reason": REASON},
        {"duration_hours": 169, "reason": REASON},
        {"duration_hours": 24},
        # Too short once trimmed.
        {"duration_hours": 24, "reason": "  no  "},
        {"reason": REASON},
    ],
)
def test_lock_validates_duration_and_reason(
    client: TestClient,
    db_session: Session,
    body: dict,
) -> None:
    create_user(client, db_session, "actor", UserRole.SECURITY_ANALYST)
    target = create_user(client, db_session, "target")

    response = client.post(
        f"/admin/users/{target.id}/lock",
        json=body,
        headers=login(client, "actor"),
    )

    assert response.status_code == 422
    assert login_response(client, "target").status_code == 200


def test_lock_of_unknown_user_returns_404(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "actor", UserRole.SECURITY_ANALYST)

    response = lock(client, 999999, login(client, "actor"))

    assert response.status_code == 404


def test_expired_lock_no_longer_refuses_logins(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "actor", UserRole.SECURITY_ANALYST)
    target = create_user(client, db_session, "target")
    assert lock(client, target.id, login(client, "actor")).status_code == 200

    target.locked_until = database_now(db_session) - timedelta(seconds=1)
    db_session.commit()

    assert login_response(client, "target").status_code == 200


def test_locking_again_replaces_the_end_time(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "actor", UserRole.SECURITY_ANALYST)
    target = create_user(client, db_session, "target")
    headers = login(client, "actor")

    first = lock(client, target.id, headers, duration_hours=168).json()
    second = lock(client, target.id, headers, duration_hours=1).json()

    assert second["locked_until"] < first["locked_until"]
    assert len(security_events(db_session, SecurityEventType.ACCOUNT_LOCKED)) == 2


@pytest.mark.parametrize("actor_role", [UserRole.ADMIN, UserRole.OWNER])
def test_admins_lift_a_lock_early(
    client: TestClient,
    db_session: Session,
    actor_role: UserRole,
) -> None:
    create_user(client, db_session, "analyst", UserRole.SECURITY_ANALYST)
    actor = create_user(client, db_session, "actor", actor_role)
    target = create_user(client, db_session, "target")
    assert lock(client, target.id, login(client, "analyst")).status_code == 200

    response = unlock(client, target.id, login(client, "actor"))

    assert response.status_code == 200
    assert response.json()["locked_until"] is None
    assert login_response(client, "target").status_code == 200

    [unlocked] = security_events(db_session, SecurityEventType.ACCOUNT_UNLOCKED)
    assert unlocked.severity == SecuritySeverity.INFO
    assert (unlocked.user_id, unlocked.target_user_id) == (actor.id, target.id)
    assert unlocked.message == (
        f"{ROLE_NAMES[actor_role]} unlocked user_id={target.id}"
    )
    assert len(audit_logs(db_session, AuditEventType.ACCOUNT_UNLOCKED)) == 1


def test_analysts_lock_but_do_not_unlock(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "analyst", UserRole.SECURITY_ANALYST)
    target = create_user(client, db_session, "target")
    headers = login(client, "analyst")
    assert lock(client, target.id, headers).status_code == 200

    response = unlock(client, target.id, headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
    assert login_response(client, "target").status_code == 403


def test_unlocking_an_account_that_is_not_locked_changes_nothing(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "actor", UserRole.ADMIN)
    never_locked = create_user(client, db_session, "never")
    expired = create_user(client, db_session, "expired")
    expired.locked_until = database_now(db_session) - timedelta(hours=1)
    db_session.commit()
    headers = login(client, "actor")

    assert unlock(client, never_locked.id, headers).status_code == 200
    assert unlock(client, expired.id, headers).status_code == 200
    assert security_events(db_session, SecurityEventType.ACCOUNT_UNLOCKED) == []


def test_unlock_restrictions(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "admin", UserRole.ADMIN)
    owner = create_user(client, db_session, "owner", UserRole.OWNER)
    admin_headers = login(client, "admin")
    admin = db_session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None

    own = unlock(client, admin.id, admin_headers)
    of_owner = unlock(client, owner.id, admin_headers)

    assert own.status_code == 403
    assert own.json()["detail"] == "Users cannot unlock their own account"
    assert of_owner.status_code == 403
    assert of_owner.json()["detail"] == "Owners cannot be locked"


def test_a_session_created_during_a_lock_is_refused(
    client: TestClient,
    db_session: Session,
) -> None:
    """A login that raced with the lock leaves a session the lock did not
    revoke; requests with it are refused while the lock lasts."""
    target = create_user(client, db_session, "target")
    headers = login(client, "target")

    target.locked_until = database_now(db_session) + timedelta(hours=1)
    db_session.commit()

    response = client.get("/users/me", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Account temporarily locked"


def test_the_locked_account_sees_the_lock_in_its_activity(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "analyst", UserRole.SECURITY_ANALYST)
    create_user(client, db_session, "admin", UserRole.ADMIN)
    target = create_user(client, db_session, "target")
    assert lock(client, target.id, login(client, "analyst")).status_code == 200
    assert unlock(client, target.id, login(client, "admin")).status_code == 200

    response = client.get("/users/me/activity", headers=login(client, "target"))

    items = {item["event_type"]: item for item in response.json()["items"]}
    for event_type in ("account_locked", "account_unlocked"):
        assert items[event_type]["as_target"] is True
        assert items[event_type]["ip_address"] is None


def test_operators_find_and_count_locked_accounts(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "analyst", UserRole.SECURITY_ANALYST)
    locked = create_user(client, db_session, "locked")
    expired = create_user(client, db_session, "expired")
    headers = login(client, "analyst")
    assert lock(client, locked.id, headers).status_code == 200
    expired.locked_until = database_now(db_session) - timedelta(minutes=1)
    db_session.commit()

    def usernames(locked_filter: str) -> set[str]:
        response = client.get(
            "/admin/users", params={"locked": locked_filter}, headers=headers
        )
        return {user["username"] for user in response.json()["items"]}

    assert usernames("true") == {"locked"}
    assert usernames("false") == {"analyst", "expired"}

    summary = client.get("/security/summary", headers=headers).json()
    assert summary["accounts_locked"] == 1
