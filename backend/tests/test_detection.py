import logging
from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.security_event import (
    MITRE_TECHNIQUES,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.models.user import User, UserRole
from app.services import detection_service

PASSWORD = "testpassword"
ATTACKER_IP = "203.0.113.9"


@pytest.fixture()
def attacker(db_session: Session) -> Generator[TestClient]:
    """A client whose requests come from ATTACKER_IP. The default test client
    has no IP address, so rules keyed on addresses never fire for it."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, client=(ATTACKER_IP, 50000)) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client: TestClient, username: str) -> str:
    email = f"{username}@example.com"
    response = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    return email


def login(client: TestClient, email: str, password: str = PASSWORD) -> int:
    response = client.post("/auth/login", json={"email": email, "password": password})
    return response.status_code


def fail_logins_for(client: TestClient, emails: list[str]) -> None:
    for email in emails:
        assert login(client, email, password="wrongpassword") == 401


def emails(count: int, start: int = 0) -> list[str]:
    return [f"victim{index}@example.com" for index in range(start, start + count)]


def alerts(db_session: Session, alert_type: SecurityEventType) -> list[SecurityEvent]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(SecurityEvent)
            .where(SecurityEvent.event_type == alert_type)
            .order_by(SecurityEvent.id)
        ).all()
    )


def shift_events_back(db_session: Session, delta: timedelta) -> None:
    db_session.execute(
        update(SecurityEvent).values(created_at=SecurityEvent.created_at - delta)
    )
    db_session.commit()


def user_by_email(db_session: Session, email: str) -> User:
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def owner_token(client: TestClient, db_session: Session) -> str:
    email = register(client, "owneruser")
    user_by_email(db_session, email).role = UserRole.OWNER
    db_session.commit()
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    return response.json()["access_token"]


# Password spray (T1110.003)


def test_failures_for_many_emails_from_one_address_raise_a_spray_incident(
    attacker: TestClient,
    db_session: Session,
) -> None:
    fail_logins_for(attacker, emails(settings.detection_spray_min_accounts - 1))
    assert alerts(db_session, SecurityEventType.PASSWORD_SPRAY_DETECTED) == []

    fail_logins_for(attacker, emails(1, start=100))

    [alert] = alerts(db_session, SecurityEventType.PASSWORD_SPRAY_DETECTED)
    assert alert.severity == SecuritySeverity.INCIDENT
    assert alert.ip_address == ATTACKER_IP
    assert alert.source == "detection"
    assert alert.user_id is None
    assert alert.email is None
    assert alert.mitre_technique == "T1110.003"
    assert alert.message == (
        f"Password spray from {ATTACKER_IP}: failed sign-ins for "
        f"{settings.detection_spray_min_accounts} different emails within "
        f"{settings.detection_spray_window_minutes} minutes"
    )


def test_a_continuing_spray_alerts_again_only_after_enough_new_emails(
    attacker: TestClient,
    db_session: Session,
) -> None:
    threshold = settings.detection_spray_min_accounts
    fail_logins_for(attacker, emails(threshold))
    fail_logins_for(attacker, emails(threshold - 1, start=100))
    assert len(alerts(db_session, SecurityEventType.PASSWORD_SPRAY_DETECTED)) == 1

    fail_logins_for(attacker, emails(1, start=200))
    assert len(alerts(db_session, SecurityEventType.PASSWORD_SPRAY_DETECTED)) == 2


def test_repeated_failures_for_one_email_are_not_a_spray(
    attacker: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Brute force on one email is the other rule's job.
    monkeypatch.setattr(settings, "detection_spray_min_accounts", 2)
    fail_logins_for(attacker, ["victim@example.com"] * 4)

    assert alerts(db_session, SecurityEventType.PASSWORD_SPRAY_DETECTED) == []


def test_spray_counts_only_failures_inside_the_window(
    attacker: TestClient,
    db_session: Session,
) -> None:
    threshold = settings.detection_spray_min_accounts
    fail_logins_for(attacker, emails(threshold - 1))
    shift_events_back(
        db_session, timedelta(minutes=settings.detection_spray_window_minutes + 1)
    )

    fail_logins_for(attacker, emails(1, start=100))

    assert alerts(db_session, SecurityEventType.PASSWORD_SPRAY_DETECTED) == []


def test_spray_counts_each_address_separately(
    attacker: TestClient,
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "detection_spray_min_accounts", 3)
    fail_logins_for(attacker, emails(2))
    # The default test client has no address at all.
    fail_logins_for(client, emails(5, start=100))

    assert alerts(db_session, SecurityEventType.PASSWORD_SPRAY_DETECTED) == []


def test_spray_thresholds_come_from_settings(
    attacker: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "detection_spray_min_accounts", 3)
    monkeypatch.setattr(settings, "detection_spray_window_minutes", 60)

    fail_logins_for(attacker, emails(3))

    [alert] = alerts(db_session, SecurityEventType.PASSWORD_SPRAY_DETECTED)
    assert "for 3 different emails within 60 minutes" in alert.message


# Dormant account (T1078)


def make_dormant(
    db_session: Session, email: str, days: int, *, signed_in: bool
) -> User:
    """Ages the account by `days` and, with `signed_in`, records its last
    sign-in that long ago."""
    user = user_by_email(db_session, email)
    long_ago = func.now() - timedelta(days=days)
    db_session.execute(
        update(User).where(User.id == user.id).values(created_at=long_ago)
    )
    if signed_in:
        db_session.add(
            SecurityEvent(
                event_type=SecurityEventType.LOGIN_SUCCESS,
                severity=SecuritySeverity.INFO,
                user_id=user.id,
                email=email,
                message="Successful login",
                created_at=long_ago,
            )
        )
    db_session.commit()
    return user


def test_a_sign_in_after_a_long_silence_is_flagged(
    attacker: TestClient,
    db_session: Session,
) -> None:
    email = register(attacker, "sleeper")
    days = settings.detection_dormant_days + 1
    user = make_dormant(db_session, email, days, signed_in=True)

    assert login(attacker, email) == 200

    [alert] = alerts(db_session, SecurityEventType.DORMANT_ACCOUNT_LOGIN)
    assert alert.severity == SecuritySeverity.WARN
    assert alert.user_id == user.id
    assert alert.email == email
    assert alert.ip_address == ATTACKER_IP
    assert alert.mitre_technique == "T1078"
    assert (
        alert.message
        == f"Sign-in to user_id={user.id} {days} days after the previous one"
    )


def test_the_first_sign_in_of_an_old_account_is_flagged(
    attacker: TestClient,
    db_session: Session,
) -> None:
    email = register(attacker, "sleeper")
    days = settings.detection_dormant_days + 10
    user = make_dormant(db_session, email, days, signed_in=False)

    assert login(attacker, email) == 200

    [alert] = alerts(db_session, SecurityEventType.DORMANT_ACCOUNT_LOGIN)
    assert alert.message == (
        f"Sign-in to user_id={user.id} {days} days after the account's creation"
    )


def test_regular_sign_ins_are_not_flagged(
    attacker: TestClient,
    db_session: Session,
) -> None:
    recent = register(attacker, "regular")
    make_dormant(
        db_session, recent, settings.detection_dormant_days - 1, signed_in=True
    )
    brand_new = register(attacker, "newcomer")

    assert login(attacker, recent) == 200
    assert login(attacker, brand_new) == 200
    # The sign-in that ended the silence is now the previous one.
    assert login(attacker, recent) == 200

    assert alerts(db_session, SecurityEventType.DORMANT_ACCOUNT_LOGIN) == []


def test_an_old_account_in_regular_use_is_not_flagged(
    attacker: TestClient,
    db_session: Session,
) -> None:
    email = register(attacker, "veteran")
    # Created long ago, but signed in recently: the silence is short.
    make_dormant(
        db_session, email, settings.detection_dormant_days * 3, signed_in=False
    )
    user = user_by_email(db_session, email)
    db_session.add(
        SecurityEvent(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            severity=SecuritySeverity.INFO,
            user_id=user.id,
            email=email,
            message="Successful login",
            created_at=func.now() - timedelta(days=2),
        )
    )
    db_session.commit()

    assert login(attacker, email) == 200

    assert alerts(db_session, SecurityEventType.DORMANT_ACCOUNT_LOGIN) == []


def test_the_account_sees_its_dormant_sign_in(
    attacker: TestClient,
    db_session: Session,
) -> None:
    email = register(attacker, "sleeper")
    make_dormant(db_session, email, settings.detection_dormant_days + 1, signed_in=True)
    token = attacker.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]

    response = attacker.get(
        "/users/me/activity", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    types = [item["event_type"] for item in response.json()["items"]]
    assert "dormant_account_login" in types


# Privileged role granted (T1098)


@pytest.mark.parametrize(
    ("new_role", "flagged"),
    [
        (UserRole.ADMIN, True),
        (UserRole.SECURITY_ANALYST, True),
        (UserRole.USER, False),
    ],
)
def test_granting_a_role_that_reaches_every_account_is_flagged(
    client: TestClient,
    db_session: Session,
    new_role: UserRole,
    flagged: bool,
) -> None:
    token = owner_token(client, db_session)
    target_email = register(client, "promoted")
    target = user_by_email(db_session, target_email)
    if new_role == UserRole.USER:
        target.role = UserRole.ADMIN
        db_session.commit()
    owner = user_by_email(db_session, "owneruser@example.com")

    response = client.patch(
        f"/admin/users/{target.id}/role",
        json={"role": new_role.value},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    found = alerts(db_session, SecurityEventType.PRIVILEGED_ROLE_GRANTED)
    if not flagged:
        assert found == []
        return
    [alert] = found
    assert alert.severity == SecuritySeverity.WARN
    assert alert.user_id == owner.id
    assert alert.target_user_id == target.id
    assert alert.email == "owneruser@example.com"
    assert alert.mitre_technique == "T1098"
    assert alert.message == f"user_id={target.id} was granted the {new_role.value} role"


# The engine


def test_a_failing_rule_never_fails_the_action_that_triggered_it(
    attacker: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(db: Session, event: SecurityEvent) -> None:
        raise RuntimeError("rule bug")

    monkeypatch.setattr(
        detection_service,
        "RULES",
        (
            detection_service.Rule(
                alert_type=SecurityEventType.PASSWORD_SPRAY_DETECTED,
                triggers=frozenset({SecurityEventType.LOGIN_SUCCESS}),
                evaluate=broken,
            ),
        ),
    )
    email = register(attacker, "someone")

    with caplog.at_level(logging.ERROR):
        assert login(attacker, email) == 200

    assert alerts(db_session, SecurityEventType.PASSWORD_SPRAY_DETECTED) == []
    assert any(record.getMessage() == "Detection failed" for record in caplog.records)


def test_no_rule_watches_an_alert() -> None:
    # An alert that triggered a rule could raise alerts without end.
    alert_types = {rule.alert_type for rule in detection_service.RULES}
    for rule in detection_service.RULES:
        assert not rule.triggers & alert_types
        assert rule.alert_type in MITRE_TECHNIQUES


def test_alerts_are_counted_in_metrics(
    attacker: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metric = "sentinelcore_security_events_total"
    labels = {"event_type": "password_spray_detected", "severity": "incident"}
    before = REGISTRY.get_sample_value(metric, labels) or 0
    monkeypatch.setattr(settings, "detection_spray_min_accounts", 2)

    fail_logins_for(attacker, emails(2))

    after = REGISTRY.get_sample_value(metric, labels)
    assert after == before + 1


def test_the_event_log_names_the_technique_of_each_detection(
    attacker: TestClient,
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "detection_spray_min_accounts", 2)
    fail_logins_for(attacker, emails(2))
    token = owner_token(client, db_session)

    response = client.get(
        "/security/events", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    techniques = {
        item["event_type"]: item["mitre_technique"] for item in response.json()["items"]
    }
    assert techniques["password_spray_detected"] == "T1110.003"
    assert techniques["login_failed"] is None
