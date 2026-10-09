import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cli, main
from app.core.config import settings
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole
from app.models.user_session import UserSession
from app.services import session_cleanup
from app.services.session_service import delete_stale_sessions
from tests.accounts import create_account
from tests.conftest import TestingSessionLocal

PASSWORD = "testpassword"


def create_user(
    client: TestClient,
    db_session: Session,
    username: str,
    role: UserRole = UserRole.USER,
) -> User:
    create_account(username, password=PASSWORD)

    user = db_session.scalar(select(User).where(User.username == username))
    assert user is not None
    user.role = role
    db_session.commit()
    return user


def login(client: TestClient, username: str) -> str:
    response = client.post(
        "/auth/login",
        json={"email": f"{username}@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def me_status(client: TestClient, token: str) -> int:
    return client.get("/users/me", headers=bearer(token)).status_code


def add_session(
    db_session: Session,
    user: User,
    expires_days_ago: float | None = None,
    revoked_days_ago: float | None = None,
) -> uuid.UUID:
    now = datetime.now(UTC)
    session = UserSession(
        user_id=user.id,
        created_at=now - timedelta(days=60),
        expires_at=(
            now - timedelta(days=expires_days_ago)
            if expires_days_ago is not None
            else now + timedelta(minutes=30)
        ),
        revoked_at=(
            now - timedelta(days=revoked_days_ago)
            if revoked_days_ago is not None
            else None
        ),
    )
    db_session.add(session)
    db_session.commit()
    return session.id


# Cleanup of stale sessions


def test_delete_stale_sessions_keeps_active_and_recent_sessions(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(client, db_session, "testuser")
    retention = settings.session_retention_days

    active = add_session(db_session, user)
    recently_expired = add_session(db_session, user, expires_days_ago=retention - 1)
    recently_revoked = add_session(db_session, user, revoked_days_ago=retention - 1)
    old_expired = add_session(db_session, user, expires_days_ago=retention + 1)
    old_revoked = add_session(db_session, user, revoked_days_ago=retention + 1)

    deleted = delete_stale_sessions(db_session, retention)

    remaining = set(db_session.scalars(select(UserSession.id)).all())
    assert deleted == 2
    assert remaining == {active, recently_expired, recently_revoked}
    assert old_expired not in remaining and old_revoked not in remaining


def test_run_session_cleanup_counts_and_logs_deletions(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(session_cleanup, "SessionLocal", TestingSessionLocal)
    user = create_user(client, db_session, "testuser")
    add_session(db_session, user, expires_days_ago=settings.session_retention_days + 5)
    before = REGISTRY.get_sample_value("sentinelcore_sessions_deleted_total") or 0.0

    with caplog.at_level(logging.INFO, logger="app.services.session_cleanup"):
        deleted = session_cleanup.run_session_cleanup()

    assert deleted == 1
    assert REGISTRY.get_sample_value("sentinelcore_sessions_deleted_total") == (
        before + 1
    )
    record = next(r for r in caplog.records if r.name == session_cleanup.__name__)
    assert record.getMessage() == "Session cleanup completed"
    assert record.__dict__["deleted_sessions"] == 1


def test_periodic_cleanup_keeps_running_after_a_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sleeps: list[float] = []
    runs: list[str] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) > 3:
            raise asyncio.CancelledError

    def fake_cleanup() -> int:
        runs.append("run")
        if len(runs) == 1:
            raise RuntimeError("database unavailable")
        return 0

    monkeypatch.setattr(session_cleanup.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(session_cleanup, "run_session_cleanup", fake_cleanup)

    with (
        caplog.at_level(logging.ERROR, logger="app.services.session_cleanup"),
        pytest.raises(asyncio.CancelledError),
    ):
        asyncio.run(session_cleanup.run_session_cleanup_periodically(15))

    assert sleeps == [900, 900, 900, 900]
    assert len(runs) == 3
    assert "Session cleanup failed" in caplog.text


@pytest.mark.parametrize(
    ("interval_minutes", "expect_task"),
    [(0, False), (15, True)],
)
def test_lifespan_starts_and_cancels_the_cleanup_task(
    monkeypatch: pytest.MonkeyPatch,
    interval_minutes: int,
    expect_task: bool,
) -> None:
    events: list[str] = []

    async def fake_periodic(minutes: int) -> None:
        events.append(f"started:{minutes}")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            events.append("cancelled")
            raise

    monkeypatch.setattr(settings, "session_cleanup_interval_minutes", interval_minutes)
    monkeypatch.setattr(main, "run_session_cleanup_periodically", fake_periodic)

    with TestClient(main.app) as test_client:
        test_client.get("/health")

    assert events == (["started:15", "cancelled"] if expect_task else [])


def test_cli_cleanup_sessions(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "run_session_cleanup", lambda: 3)

    cli.main(["cleanup-sessions"])

    assert capsys.readouterr().out.strip() == "Deleted 3 stale session(s)."


def test_cli_requires_a_command() -> None:
    with pytest.raises(SystemExit):
        cli.main([])


# Operator revocation of another user's sessions

REASON = "Sign-ins from an unknown country"

# Roles as event messages name them.
ROLE_NAMES = {
    UserRole.ADMIN: "Admin",
    UserRole.OWNER: "Owner",
    UserRole.SECURITY_ANALYST: "Security analyst",
}


def revoke(client: TestClient, user_id: int, token: str, reason: str = REASON):
    return client.post(
        f"/admin/users/{user_id}/revoke-sessions",
        json={"reason": reason},
        headers=bearer(token),
    )


def test_revoke_user_sessions_without_token_returns_401(client: TestClient) -> None:
    response = client.post("/admin/users/1/revoke-sessions", json={"reason": REASON})

    assert response.status_code == 401


def test_revoke_user_sessions_requires_an_operator(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "actor")
    target = create_user(client, db_session, "target")
    target_token = login(client, "target")

    response = revoke(client, target.id, login(client, "actor"))

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
    assert me_status(client, target_token) == 200


@pytest.mark.parametrize(
    ("actor_role", "target_role"),
    [
        (UserRole.ADMIN, UserRole.USER),
        (UserRole.ADMIN, UserRole.SECURITY_ANALYST),
        # Containment is reversible, so admins and analysts may contain admins.
        (UserRole.ADMIN, UserRole.ADMIN),
        (UserRole.OWNER, UserRole.ADMIN),
        (UserRole.SECURITY_ANALYST, UserRole.USER),
        (UserRole.SECURITY_ANALYST, UserRole.SECURITY_ANALYST),
        (UserRole.SECURITY_ANALYST, UserRole.ADMIN),
    ],
)
def test_revoke_user_sessions_signs_the_user_out_everywhere(
    client: TestClient,
    db_session: Session,
    actor_role: UserRole,
    target_role: UserRole,
) -> None:
    actor = create_user(client, db_session, "actor", actor_role)
    target = create_user(client, db_session, "target", target_role)
    target_tokens = [login(client, "target") for _ in range(2)]
    actor_token = login(client, "actor")

    response = revoke(client, target.id, actor_token, reason=f"  {REASON}  ")

    assert response.status_code == 200
    assert response.json() == {"revoked_sessions": 2}
    assert [me_status(client, token) for token in target_tokens] == [401, 401]
    # The account stays active, and the actor's own session is untouched.
    assert me_status(client, login(client, "target")) == 200
    assert me_status(client, actor_token) == 200

    # The reason is stored trimmed.
    expected_message = (
        f"{ROLE_NAMES[actor_role]} revoked 2 session(s) "
        f"for user_id={target.id}. Reason: {REASON}"
    )
    audit_log = db_session.scalar(
        select(AuditLog).where(
            AuditLog.event_type == AuditEventType.ALL_SESSIONS_REVOKED
        )
    )
    security_event = db_session.scalar(
        select(SecurityEvent).where(
            SecurityEvent.event_type == SecurityEventType.USER_SESSIONS_REVOKED
        )
    )
    assert audit_log is not None and security_event is not None
    assert audit_log.user_id == actor.id
    assert audit_log.target_user_id == target.id
    assert audit_log.message == expected_message
    assert security_event.user_id == actor.id
    assert security_event.target_user_id == target.id
    assert security_event.severity == SecuritySeverity.INFO
    assert security_event.message == expected_message


def test_revoke_user_sessions_with_no_active_sessions(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "actor", UserRole.ADMIN)
    target = create_user(client, db_session, "target")

    response = revoke(client, target.id, login(client, "actor"))

    assert response.status_code == 200
    assert response.json() == {"revoked_sessions": 0}


@pytest.mark.parametrize("body", [{}, {"reason": "  ab  "}, {"reason": "x" * 501}])
def test_revoke_user_sessions_requires_a_reason(
    client: TestClient,
    db_session: Session,
    body: dict,
) -> None:
    create_user(client, db_session, "actor", UserRole.ADMIN)
    target = create_user(client, db_session, "target")
    target_token = login(client, "target")

    response = client.post(
        f"/admin/users/{target.id}/revoke-sessions",
        json=body,
        headers=bearer(login(client, "actor")),
    )

    assert response.status_code == 422
    assert me_status(client, target_token) == 200


@pytest.mark.parametrize(
    ("actor_role", "target_is_actor", "target_role", "expected_detail"),
    [
        (
            UserRole.ADMIN,
            True,
            UserRole.ADMIN,
            "Use /auth/logout-all to revoke your own sessions",
        ),
        (
            UserRole.SECURITY_ANALYST,
            True,
            UserRole.SECURITY_ANALYST,
            "Use /auth/logout-all to revoke your own sessions",
        ),
        (
            UserRole.OWNER,
            True,
            UserRole.OWNER,
            "Use /auth/logout-all to revoke your own sessions",
        ),
        (
            UserRole.ADMIN,
            False,
            UserRole.OWNER,
            "Cannot revoke the sessions of an owner",
        ),
        (
            UserRole.SECURITY_ANALYST,
            False,
            UserRole.OWNER,
            "Cannot revoke the sessions of an owner",
        ),
        (
            UserRole.OWNER,
            False,
            UserRole.OWNER,
            "Cannot revoke the sessions of an owner",
        ),
    ],
)
def test_revoke_user_sessions_restrictions(
    client: TestClient,
    db_session: Session,
    actor_role: UserRole,
    target_is_actor: bool,
    target_role: UserRole,
    expected_detail: str,
) -> None:
    actor = create_user(client, db_session, "actor", actor_role)
    actor_token = login(client, "actor")
    if target_is_actor:
        target, target_token = actor, actor_token
    else:
        target = create_user(client, db_session, "target", target_role)
        target_token = login(client, "target")

    response = revoke(client, target.id, actor_token)

    assert response.status_code == 403
    assert response.json()["detail"] == expected_detail
    assert me_status(client, target_token) == 200
    assert (
        db_session.scalar(
            select(SecurityEvent.id).where(
                SecurityEvent.event_type == SecurityEventType.USER_SESSIONS_REVOKED
            )
        )
        is None
    )


def test_revoke_sessions_of_unknown_user_returns_404(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, db_session, "actor", UserRole.OWNER)

    response = revoke(client, 999999, login(client, "actor"))

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
