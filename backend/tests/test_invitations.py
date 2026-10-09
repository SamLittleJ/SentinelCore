from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app import cli
from app.api.routes import invitations
from app.main import app
from app.models.audit_log import AuditEventType, AuditLog
from app.models.invitation import Invitation
from app.models.security_event import SecurityEvent, SecurityEventType
from app.models.user import User, UserRole
from app.services.invitation_service import accept_invitation, find_open_invitation
from tests.accounts import PASSWORD, create_account
from tests.conftest import TestingSessionLocal

NEW_PASSWORD = "a-new-password"  # nosec B105


def headers_for(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"email": f"{username}@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def operator(client: TestClient, role: UserRole) -> dict[str, str]:
    username = role.value.replace("_", "")
    create_account(username, role=role)
    return headers_for(client, username)


def invite(
    client: TestClient,
    headers: dict[str, str],
    email: str = "new.person@example.com",
    role: str = "user",
) -> str:
    response = client.post(
        "/admin/invitations", json={"email": email, "role": role}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


def accept(client: TestClient, token: str, username: str = "newperson"):
    return client.post(
        "/auth/invitations/accept",
        json={"token": token, "username": username, "password": NEW_PASSWORD},
    )


def preview(client: TestClient, token: str):
    return client.post("/auth/invitations/preview", json={"token": token})


def count(db: Session, model: type[User] | type[Invitation]) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


# Inviting


def test_the_owner_invites_and_the_token_is_shown_once(
    client: TestClient, db_session: Session
) -> None:
    owner = operator(client, UserRole.OWNER)

    response = client.post(
        "/admin/invitations",
        json={"email": "New.Person@Example.COM", "role": "admin"},
        headers=owner,
    )

    assert response.status_code == 201
    body = response.json()
    invitation = body["invitation"]
    token = body["token"]
    assert token.startswith(f"sci_{invitation['prefix']}_")
    assert invitation["email"] == "new.person@example.com"
    assert invitation["role"] == "admin"
    assert invitation["accepted_at"] is None
    assert "secret_hash" not in invitation

    # Only a hash of the secret is stored, and the list never shows the token.
    stored = db_session.scalar(select(Invitation))
    assert stored is not None
    assert token.split("_")[2] not in (stored.secret_hash, stored.prefix)
    listed = client.get("/admin/invitations", headers=owner)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [invitation["id"]]
    assert token not in listed.text

    messages = db_session.scalars(
        select(SecurityEvent.message).where(
            SecurityEvent.event_type == SecurityEventType.INVITATION_CREATED
        )
    ).all()
    assert messages == [
        f"Owner invited new.person@example.com as admin "
        f"(invitation {invitation['prefix']}), valid for 72 hours"
    ]
    audit_types = db_session.scalars(select(AuditLog.event_type)).all()
    assert AuditEventType.INVITATION_CREATED in audit_types
    assert AuditEventType.INVITATIONS_VIEWED in audit_types


def test_invitations_last_as_long_as_the_setting_says(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.invitation_expire_hours", 5)
    invite(client, operator(client, UserRole.OWNER))

    invitation = db_session.scalar(select(Invitation))
    assert invitation is not None
    assert invitation.expires_at - invitation.created_at == pytest.approx(
        timedelta(hours=5), abs=timedelta(seconds=5)
    )


@pytest.mark.parametrize(
    ("inviter", "role", "status_code"),
    [
        (UserRole.ADMIN, "user", 201),
        (UserRole.ADMIN, "security_analyst", 201),
        (UserRole.ADMIN, "admin", 403),
        (UserRole.OWNER, "admin", 201),
        (UserRole.OWNER, "owner", 422),
        (UserRole.SECURITY_ANALYST, "user", 403),
        (UserRole.USER, "user", 403),
    ],
)
def test_who_may_offer_which_role(
    client: TestClient,
    db_session: Session,
    inviter: UserRole,
    role: str,
    status_code: int,
) -> None:
    headers = operator(client, inviter)

    response = client.post(
        "/admin/invitations",
        json={"email": "new.person@example.com", "role": role},
        headers=headers,
    )

    assert response.status_code == status_code
    assert count(db_session, Invitation) == (1 if status_code == 201 else 0)


@pytest.mark.parametrize(
    ("role", "status_code"),
    [
        (UserRole.SECURITY_ANALYST, 200),
        (UserRole.ADMIN, 200),
        (UserRole.USER, 403),
    ],
)
def test_who_may_see_the_invitations(
    client: TestClient, role: UserRole, status_code: int
) -> None:
    response = client.get("/admin/invitations", headers=operator(client, role))

    assert response.status_code == status_code


def test_an_email_that_has_an_account_is_not_invited(
    client: TestClient, db_session: Session
) -> None:
    owner = operator(client, UserRole.OWNER)
    create_account("existing")

    response = client.post(
        "/admin/invitations",
        json={"email": "EXISTING@example.com", "role": "user"},
        headers=owner,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "An account with this email already exists"
    assert count(db_session, Invitation) == 0


def test_a_new_invitation_replaces_the_open_one(
    client: TestClient, db_session: Session
) -> None:
    owner = operator(client, UserRole.OWNER)
    first = invite(client, owner)
    second = invite(client, owner, role="security_analyst")

    assert preview(client, first).status_code == 404
    assert preview(client, second).json()["role"] == "security_analyst"
    message = db_session.scalars(
        select(SecurityEvent.message)
        .where(SecurityEvent.event_type == SecurityEventType.INVITATION_CREATED)
        .order_by(SecurityEvent.id.desc())
    ).first()
    assert message is not None
    assert message.endswith("; replaced 1 earlier invitation(s)")


def test_the_database_keeps_one_open_invitation_per_email(
    client: TestClient, db_session: Session
) -> None:
    # The last guard when two operators invite the same email at once.
    invite(client, operator(client, UserRole.OWNER))
    existing = db_session.scalar(select(Invitation))
    assert existing is not None

    with TestingSessionLocal() as other, pytest.raises(IntegrityError):
        other.add(
            Invitation(
                prefix="00000000",
                secret_hash="0" * 64,
                email=existing.email,
                role=UserRole.USER,
                created_by_id=existing.created_by_id,
                expires_at=existing.expires_at,
            )
        )
        other.commit()


# Accepting


def test_the_person_invited_previews_accepts_and_signs_in(
    client: TestClient, db_session: Session
) -> None:
    owner = operator(client, UserRole.OWNER)
    token = invite(client, owner, role="security_analyst")

    shown = preview(client, token)
    assert shown.status_code == 200
    assert set(shown.json()) == {"email", "role", "expires_at"}
    assert shown.json()["email"] == "new.person@example.com"

    with TestClient(app, client=("203.0.113.9", 50000)) as browser:
        response = browser.post(
            "/auth/invitations/accept",
            json={"token": token, "username": "New.Person", "password": NEW_PASSWORD},
        )

    assert response.status_code == 201
    account = response.json()
    assert account["username"] == "new.person"
    assert account["email"] == "new.person@example.com"
    assert account["role"] == "security_analyst"
    assert "hashed_password" not in account

    invitation = db_session.scalar(select(Invitation))
    assert invitation is not None
    db_session.refresh(invitation)
    assert invitation.accepted_at is not None
    assert invitation.accepted_user_id == account["id"]

    created = db_session.scalar(
        select(SecurityEvent).where(
            SecurityEvent.event_type == SecurityEventType.USER_REGISTERED,
            SecurityEvent.target_user_id == account["id"],
        )
    )
    assert created is not None
    assert created.ip_address == "203.0.113.9"
    assert created.message == (
        "Account created for new.person@example.com with the security_analyst "
        f"role, from invitation {invitation.prefix} by "
        f"user_id={invitation.created_by_id}"
    )

    signed_in = client.post(
        "/auth/login",
        json={"email": "new.person@example.com", "password": NEW_PASSWORD},
    )
    assert signed_in.status_code == 200


def test_an_invitation_works_once(client: TestClient, db_session: Session) -> None:
    token = invite(client, operator(client, UserRole.OWNER))

    assert accept(client, token).status_code == 201
    again = accept(client, token, username="someoneelse")

    assert again.status_code == 404
    assert count(db_session, User) == 2


def test_two_requests_cannot_use_one_invitation_at_once(client: TestClient) -> None:
    token = invite(client, operator(client, UserRole.OWNER))

    with TestingSessionLocal() as first, TestingSessionLocal() as second:
        # The first request holds the invitation while it creates the account.
        held = find_open_invitation(first, token, for_update=True)
        assert held is not None
        # The second waits for it; here it gives up quickly instead.
        second.execute(text("SET LOCAL lock_timeout = '200ms'"))
        with pytest.raises(OperationalError):
            find_open_invitation(second, token, for_update=True)
        second.rollback()

        accept_invitation(first, held, "first", NEW_PASSWORD)
        # Once the first is done, the invitation is spent.
        assert find_open_invitation(second, token, for_update=True) is None


def tampered(token: str) -> str:
    """`token` with the last character of its secret changed."""
    return token[:-1] + ("A" if token[-1] != "A" else "B")


def expire(db: Session) -> None:
    invitation = db.scalar(select(Invitation))
    assert invitation is not None
    invitation.expires_at = invitation.created_at - timedelta(seconds=1)
    db.commit()


def revoke_by_owner(client: TestClient, db: Session, owner: dict[str, str]) -> None:
    invitation = db.scalar(select(Invitation))
    assert invitation is not None
    response = client.post(f"/admin/invitations/{invitation.id}/revoke", headers=owner)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "spoil",
    ["unknown", "garbled", "wrong secret", "api key scheme", "expired", "revoked"],
)
def test_every_unusable_token_gets_the_same_answer(
    client: TestClient, db_session: Session, spoil: str
) -> None:
    owner = operator(client, UserRole.OWNER)
    token = invite(client, owner)
    if spoil == "unknown":
        token = "sci_00000000_" + token.split("_", 2)[2]
    elif spoil == "garbled":
        token = "not a token"
    elif spoil == "wrong secret":
        token = tampered(token)
    elif spoil == "api key scheme":
        token = "sck" + token[3:]
    elif spoil == "expired":
        expire(db_session)
    elif spoil == "revoked":
        revoke_by_owner(client, db_session, owner)

    for response in (preview(client, token), accept(client, token)):
        assert response.status_code == 404
        assert response.json() == {
            "detail": "This invitation is not valid. Ask for a new one."
        }
    assert count(db_session, User) == 1


@pytest.mark.parametrize("change", ["deactivated", "demoted"])
def test_an_invitation_is_worth_what_its_author_may_still_grant(
    client: TestClient, db_session: Session, change: str
) -> None:
    admin = operator(client, UserRole.ADMIN)
    token = invite(client, admin, role="security_analyst")
    author = db_session.scalar(select(User).where(User.username == "admin"))
    assert author is not None
    if change == "deactivated":
        author.is_active = False
    else:
        author.role = UserRole.SECURITY_ANALYST
    db_session.commit()

    assert preview(client, token).status_code == 404
    assert accept(client, token).status_code == 404


def test_a_taken_username_keeps_the_invitation(
    client: TestClient, db_session: Session
) -> None:
    token = invite(client, operator(client, UserRole.OWNER))
    create_account("taken")

    response = accept(client, token, username="Taken")

    assert response.status_code == 400
    assert response.json()["detail"] == "Username already taken"
    assert accept(client, token, username="free").status_code == 201


def test_an_email_that_got_an_account_since_spends_the_invitation(
    client: TestClient, db_session: Session
) -> None:
    token = invite(client, operator(client, UserRole.OWNER))
    create_account("other", email="new.person@example.com")

    assert accept(client, token).status_code == 404
    assert count(db_session, User) == 2


def test_an_email_taken_at_the_same_moment_spends_the_invitation(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = invite(client, operator(client, UserRole.OWNER))
    create_account("other", email="new.person@example.com")
    # The check before creating the account misses it, as in a race; the
    # unique index still refuses the email, with the same answer.
    monkeypatch.setattr(invitations, "get_user_by_email", lambda db, email: None)

    response = accept(client, token)

    assert response.status_code == 404
    assert (
        response.json()["detail"] == "This invitation is not valid. Ask for a new one."
    )
    assert count(db_session, User) == 2


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("username", "ab", "string_too_short"),
        ("username", "u" * 51, "string_too_long"),
        ("username", "has space", "string_pattern_mismatch"),
        ("username", "țară", "string_pattern_mismatch"),
        ("password", "x" * 11, "string_too_short"),
        ("password", "x" * 129, "string_too_long"),
        ("token", "x" * 201, "string_too_long"),
    ],
)
def test_accepting_checks_the_username_and_password(
    client: TestClient,
    db_session: Session,
    field: str,
    value: str,
    error_type: str,
) -> None:
    token = invite(client, operator(client, UserRole.OWNER))
    body = {"token": token, "username": "newperson", "password": NEW_PASSWORD}

    response = client.post("/auth/invitations/accept", json={**body, field: value})

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", field]
    assert error["type"] == error_type
    assert count(db_session, User) == 1


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
def test_accepting_takes_the_boundary_values(
    client: TestClient, field: str, value: str
) -> None:
    token = invite(client, operator(client, UserRole.OWNER))
    body = {"token": token, "username": "newperson", "password": NEW_PASSWORD}

    response = client.post("/auth/invitations/accept", json={**body, field: value})

    assert response.status_code == 201


@pytest.mark.parametrize(
    ("role", "alerts"), [("admin", 1), ("security_analyst", 1), ("user", 0)]
)
def test_joining_with_a_privileged_role_raises_the_t1098_alert(
    client: TestClient, db_session: Session, role: str, alerts: int
) -> None:
    token = invite(client, operator(client, UserRole.OWNER), role=role)

    account = accept(client, token).json()

    raised = db_session.scalars(
        select(SecurityEvent).where(
            SecurityEvent.event_type == SecurityEventType.PRIVILEGED_ROLE_GRANTED
        )
    ).all()
    assert len(raised) == alerts
    if raised:
        assert raised[0].target_user_id == account["id"]
        assert raised[0].message == (
            f"user_id={account['id']} was granted the {role} role"
        )


# Revoking


def test_admins_revoke_only_what_they_may_offer(
    client: TestClient, db_session: Session
) -> None:
    owner = operator(client, UserRole.OWNER)
    admin = operator(client, UserRole.ADMIN)
    invite(client, owner, email="future.admin@example.com", role="admin")
    invite(client, owner, email="future.user@example.com", role="user")
    ids = {
        invitation.email: invitation.id
        for invitation in db_session.scalars(select(Invitation))
    }

    refused = client.post(
        f"/admin/invitations/{ids['future.admin@example.com']}/revoke", headers=admin
    )
    revoked = client.post(
        f"/admin/invitations/{ids['future.user@example.com']}/revoke", headers=admin
    )

    assert refused.status_code == 403
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    assert (
        client.post("/admin/invitations/999/revoke", headers=admin).status_code == 404
    )
    messages = db_session.scalars(
        select(AuditLog.message).where(
            AuditLog.event_type == AuditEventType.INVITATION_REVOKED
        )
    ).all()
    assert len(messages) == 1
    assert (messages[0] or "").startswith("Admin revoked invitation ")


def test_revoking_a_used_invitation_changes_nothing(
    client: TestClient, db_session: Session
) -> None:
    owner = operator(client, UserRole.OWNER)
    accept(client, invite(client, owner))
    invitation = db_session.scalar(select(Invitation))
    assert invitation is not None

    response = client.post(f"/admin/invitations/{invitation.id}/revoke", headers=owner)

    assert response.status_code == 200
    assert response.json()["revoked_at"] is None
    assert response.json()["accepted_at"] is not None


# The first owner, from the command line


@pytest.fixture()
def cli_database(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "SessionLocal", TestingSessionLocal)
    monkeypatch.setenv(cli.OWNER_PASSWORD_ENV, "the-owner-password")


@pytest.mark.usefixtures("cli_database")
def test_the_cli_creates_the_first_owner(
    db_session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["create-owner", "--email", "Boss@Example.com", "--username", "Boss"])

    owner = db_session.scalar(select(User))
    assert owner is not None
    assert (owner.email, owner.username, owner.role) == (
        "boss@example.com",
        "boss",
        UserRole.OWNER,
    )
    assert f"Created the owner boss@example.com (user_id={owner.id})." in (
        capsys.readouterr().out
    )
    event = db_session.scalar(select(SecurityEvent))
    assert event is not None
    assert event.event_type == SecurityEventType.USER_REGISTERED
    assert event.message == (
        "Owner account created from the command line: boss@example.com"
    )


@pytest.mark.usefixtures("cli_database")
def test_the_cli_refuses_a_second_owner(db_session: Session) -> None:
    create_account("first", role=UserRole.OWNER)

    with pytest.raises(SystemExit, match="already has an owner"):
        cli.main(["create-owner", "--email", "boss@example.com", "--username", "boss"])

    assert count(db_session, User) == 1


@pytest.mark.usefixtures("cli_database")
def test_the_cli_refuses_a_taken_email(db_session: Session) -> None:
    create_account("boss")

    with pytest.raises(SystemExit, match="already exists"):
        cli.main(["create-owner", "--email", "boss@example.com", "--username", "boss2"])

    assert count(db_session, User) == 1


@pytest.mark.usefixtures("cli_database")
def test_the_cli_never_repeats_the_password(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(cli.OWNER_PASSWORD_ENV, "short-pw")

    with pytest.raises(SystemExit) as stopped:
        cli.main(["create-owner", "--email", "boss@example.com", "--username", "boss"])

    assert "password: String should have at least 12 characters" in str(stopped.value)
    assert "short-pw" not in str(stopped.value)
    assert count(db_session, User) == 0


@pytest.mark.usefixtures("cli_database")
def test_the_cli_asks_twice_without_the_variable(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(cli.OWNER_PASSWORD_ENV)
    answers = iter(["typed-password-1", "typed-password-2"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(answers))

    with pytest.raises(SystemExit, match="The passwords differ"):
        cli.main(["create-owner", "--email", "boss@example.com", "--username", "boss"])

    assert count(db_session, User) == 0
