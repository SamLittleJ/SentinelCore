"""Row-level security: PostgreSQL keeps each organization's rows to that
organization, behind the application's own filters (test_tenant_isolation.py).

These tests use the API's database role. Some take an application filter away
on purpose, to show that the database still holds the boundary."""

from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, make_url, select, text, update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

import app.api.routes.auth as auth_routes
import app.api.routes.ingest as ingest_routes
import app.api.routes.security as security_routes
from app import cli
from app.api.deps import get_db
from app.core.config import settings
from app.core.row_security import (
    APP_ROLE,
    EVERYTHING_SETTING,
    ORGANIZATION_SETTING,
    restrict_rows,
)
from app.main import app
from app.models.api_key import ApiKey
from app.models.api_key_usage import ApiKeyUsage
from app.models.audit_log import AuditLog
from app.models.invitation import Invitation
from app.models.organization import Organization
from app.models.security_event import SecurityEvent, SecurityEventType, SecuritySeverity
from app.models.user import User
from app.models.user_session import UserSession
from app.services.tenancy import EVERYTHING, Scope
from tests.conftest import (
    TEST_DATABASE_URL,
    OwnerSessionLocal,
    TestingSessionLocal,
    serve_requests_from,
)
from tests.test_organizations import headers_for, ingest, new_key, sign_in
from tests.test_tenant_isolation import (  # noqa: F401  Fixtures.
    RECORD_LISTINGS,
    Platform,
    invite,
    items,
    organizations_in,
    platform,
    records_in_both,
)

# Each table under a policy, and how a row names its organization. A session
# names it through its account.
TABLES: dict[type, Callable] = {
    Organization: lambda: select(Organization.id),
    User: lambda: select(User.organization_id),
    UserSession: lambda: select(User.organization_id).join(
        UserSession, UserSession.user_id == User.id
    ),
    SecurityEvent: lambda: select(SecurityEvent.organization_id),
    AuditLog: lambda: select(AuditLog.organization_id),
    ApiKey: lambda: select(ApiKey.organization_id),
    Invitation: lambda: select(Invitation.organization_id),
    ApiKeyUsage: lambda: select(ApiKeyUsage.organization_id),
}
# How many rows each table has, whoever may see them.
ROW_COUNT = "SELECT count(*) FROM {}"


def organizations_seen(db: Session, model: type) -> set[int | None]:
    return set(db.scalars(TABLES[model]()).all())


def rows_in(model: type) -> int:
    with OwnerSessionLocal() as owner:
        return owner.scalar(text(ROW_COUNT.format(model.__tablename__))) or 0


@pytest.fixture()
def records(
    client: TestClient,
    platform: Platform,  # noqa: F811
    records_in_both: None,  # noqa: F811
) -> Platform:
    """Rows of both organizations, and of the platform, in every table; a
    Globex sign-in gives Globex a session too, and a batch from each
    organization's key its hourly count."""
    headers_for(client, "gus")
    for org_id, email in ((platform.acme, "ada"), (platform.globex, "gus")):
        key = new_key(client, platform.owner, org_id)
        assert ingest(client, key, sign_in(f"{email}@example.com")).status_code == 202
    assert all(rows_in(model) for model in TABLES)
    return platform


# The database on its own


@pytest.mark.parametrize("model", TABLES, ids=lambda model: model.__tablename__)
def test_a_session_that_names_no_one_sees_no_rows(
    records: Platform, model: type
) -> None:
    with TestingSessionLocal() as db:
        assert organizations_seen(db, model) == set()
        assert db.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("model", TABLES, ids=lambda model: model.__tablename__)
def test_an_organization_sees_only_its_own_rows(records: Platform, model: type) -> None:
    with TestingSessionLocal() as db:
        restrict_rows(db, Scope(organization_id=records.acme))
        assert organizations_seen(db, model) == {records.acme}


@pytest.mark.parametrize("model", TABLES, ids=lambda model: model.__tablename__)
def test_everything_shows_every_organization(records: Platform, model: type) -> None:
    with TestingSessionLocal() as db:
        restrict_rows(db, EVERYTHING)
        assert {records.acme, records.globex} <= organizations_seen(db, model)
        assert db.scalar(select(func.count()).select_from(model)) == rows_in(model)


def test_the_scope_outlives_a_commit(records: Platform) -> None:
    with TestingSessionLocal() as db:
        restrict_rows(db, Scope(organization_id=records.acme))
        db.commit()
        assert organizations_seen(db, User) == {records.acme}
        db.commit()
        assert organizations_seen(db, User) == {records.acme}


def an_event(organization_id: int | None) -> SecurityEvent:
    return SecurityEvent(
        event_type=SecurityEventType.LOGIN_FAILED,
        severity=SecuritySeverity.WARN,
        organization_id=organization_id,
        message="Written across the boundary",
    )


@pytest.mark.parametrize("target", ["globex", "platform"])
def test_an_organization_cannot_write_rows_of_another(
    records: Platform, target: str
) -> None:
    other = records.globex if target == "globex" else None
    with TestingSessionLocal() as db:
        restrict_rows(db, Scope(organization_id=records.acme))
        db.add(an_event(other))
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.commit()


def test_an_organization_cannot_change_rows_of_another(records: Platform) -> None:
    with TestingSessionLocal() as db:
        restrict_rows(db, Scope(organization_id=records.acme))
        db.execute(
            update(User).where(User.id == records.ids["gina"]).values(is_active=False)
        )
        db.commit()
        with OwnerSessionLocal() as owner:
            gina = owner.get(User, records.ids["gina"])
            assert gina is not None and gina.is_active

        # Nor move its own rows into another organization.
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.execute(
                update(User)
                .where(User.id == records.ids["alice"])
                .values(organization_id=records.globex)
            )


@pytest.mark.parametrize("model", [SecurityEvent, AuditLog])
@pytest.mark.parametrize("change", [update, delete])
def test_the_api_cannot_rewrite_history(
    records: Platform, model: type, change: Callable
) -> None:
    statement = change(model)
    if change is update:
        statement = statement.values(message="Rewritten")
    with TestingSessionLocal() as db:
        restrict_rows(db, EVERYTHING)
        with pytest.raises(ProgrammingError, match="permission denied"):
            db.execute(statement)


def test_the_api_role_cannot_bypass_row_security(db_session: Session) -> None:
    role = db_session.execute(
        text(
            "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles "
            "WHERE rolname = current_user"
        )
    ).one()
    assert tuple(role) == (APP_ROLE, False, False)

    with pytest.raises(ProgrammingError, match="permission denied"):
        db_session.execute(text("SELECT * FROM alembic_version"))


# The database behind the application


@pytest.mark.usefixtures("records_in_both")
@pytest.mark.parametrize("path", RECORD_LISTINGS)
def test_the_database_holds_the_boundary_when_a_listing_forgets_it(
    client: TestClient,
    platform: Platform,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.setattr(Scope, "conditions", lambda self, column: [])

    assert organizations_in(client.get(path, headers=platform.ada)) == {platform.acme}
    everything = organizations_in(client.get(path, headers=platform.owner))
    assert {platform.acme, platform.globex} <= everything


def test_the_database_holds_the_boundary_when_a_lookup_forgets_it(
    client: TestClient,
    platform: Platform,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Scope, "includes", lambda self, organization_id: True)

    gina = client.get(f"/admin/users/{platform.ids['gina']}", headers=platform.ada)
    assert gina.status_code == 404
    alice = client.get(f"/admin/users/{platform.ids['alice']}", headers=platform.ada)
    assert alice.status_code == 200


def scope_named(db: Session) -> tuple[str, str]:
    """The settings the policies read, in the current transaction."""
    named = db.execute(
        text("SELECT current_setting(:everything, true), current_setting(:org, true)"),
        {"everything": EVERYTHING_SETTING, "org": ORGANIZATION_SETTING},
    ).one()
    return (named[0] or "", named[1] or "")


def spy_on(
    monkeypatch: pytest.MonkeyPatch, module: object, name: str
) -> list[tuple[str, str]]:
    """Record the scope the database is given each time `module.name` runs."""
    seen: list[tuple[str, str]] = []
    original = getattr(module, name)

    def spy(db: Session, *args, **kwargs):
        seen.append(scope_named(db))
        return original(db, *args, **kwargs)

    monkeypatch.setattr(module, name, spy)
    return seen


def test_a_request_names_who_is_asking(
    client: TestClient,
    platform: Platform,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = spy_on(monkeypatch, security_routes, "list_security_events")

    client.get("/security/events", headers=platform.ada)
    client.get("/security/events", headers=platform.owner)
    client.get(
        "/security/events",
        params={"organization_id": platform.globex},
        headers=platform.owner,
    )

    # The owner's filter narrows the listing, not what the database shows.
    assert seen == [("", str(platform.acme)), ("on", ""), ("on", "")]


def test_sign_in_sees_every_account(
    client: TestClient,
    platform: Platform,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = spy_on(monkeypatch, auth_routes, "authenticate_user")

    response = client.post(
        "/auth/login", json={"email": "gina@example.com", "password": "testpassword"}
    )

    assert response.status_code == 200
    assert seen == [("on", "")]


def test_an_ingestion_key_works_within_its_organization(
    client: TestClient,
    platform: Platform,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = new_key(client, platform.owner, platform.acme)
    seen = spy_on(monkeypatch, ingest_routes, "ingest_events")

    assert ingest(client, key, sign_in("alice@example.com")).status_code == 202
    assert seen == [("", str(platform.acme))]


# Invitations, now that an admin sees only their organization's


def accept(client: TestClient, token: str):
    return client.post(
        "/auth/invitations/accept",
        json={"token": token, "username": "newcomer", "password": "a-long-password"},
    )


def test_an_admin_inviting_an_email_of_another_organization_learns_nothing(
    client: TestClient,
    platform: Platform,  # noqa: F811
) -> None:
    response = client.post(
        "/admin/invitations",
        json={"email": "gina@example.com", "role": "user"},
        headers=platform.ada,
    )
    assert response.status_code == 201, response.text

    # The person invited, who has the address, learns it has an account.
    assert accept(client, response.json()["token"]).status_code == 404

    # The owner sees every account, so they are told at once.
    owners = client.post(
        "/admin/invitations",
        json={
            "email": "gina@example.com",
            "role": "user",
            "organization_id": platform.acme,
        },
        headers=platform.owner,
    )
    assert owners.status_code == 409


def test_an_invitation_leaves_another_organizations_invitation_alone(
    client: TestClient,
    platform: Platform,  # noqa: F811
    db_session: Session,
) -> None:
    globex = invite(client, platform.owner, "both@example.com", platform.globex)

    response = client.post(
        "/admin/invitations",
        json={"email": "both@example.com", "role": "user"},
        headers=platform.ada,
    )

    assert response.status_code == 201, response.text
    db_session.expire_all()
    left = db_session.get(Invitation, globex["id"])
    assert left is not None and left.revoked_at is None

    # The first accepted takes the email; the other stops working.
    assert accept(client, response.json()["token"]).status_code == 201


# Health and setup


def test_readiness_fails_when_the_api_could_bypass_row_security(
    client: TestClient,
) -> None:
    assert client.get("/health/ready").status_code == 200

    owner = OwnerSessionLocal()
    app.dependency_overrides[get_db] = serve_requests_from(owner)
    try:
        response = client.get("/health/ready")
    finally:
        owner.close()

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unsafe role"}


# The command that lets the API's role sign in

CLI_ROLE = "sentinelcore_cli_test"
CLI_PASSWORD = "cli-test-password"  # nosec B105  A throwaway role's.


@pytest.fixture()
def cli_role(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[str]:
    """A throwaway role, so the test never touches the real one's password."""
    with OwnerSessionLocal() as owner:
        owner.execute(text(f"DROP ROLE IF EXISTS {CLI_ROLE}"))
        owner.execute(text(f"CREATE ROLE {CLI_ROLE} NOLOGIN"))
        owner.commit()
    url = (
        make_url(TEST_DATABASE_URL)
        .set(username=CLI_ROLE, password=CLI_PASSWORD)
        .render_as_string(hide_password=False)
    )
    monkeypatch.setattr(settings, "database_url", url)
    monkeypatch.setattr(settings, "migrations_database_url", TEST_DATABASE_URL)
    yield url
    with OwnerSessionLocal() as owner:
        owner.execute(text(f"DROP ROLE IF EXISTS {CLI_ROLE}"))
        owner.commit()


def test_the_cli_lets_the_api_role_sign_in_with_its_password(
    cli_role: str, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["grant-api-login"])

    engine = create_engine(cli_role)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_user")) == CLI_ROLE
    finally:
        engine.dispose()
    assert CLI_PASSWORD not in capsys.readouterr().out


def test_the_cli_refuses_a_role_that_bypasses_row_security(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setattr(settings, "database_url", TEST_DATABASE_URL)
    monkeypatch.setattr(settings, "migrations_database_url", TEST_DATABASE_URL)

    with pytest.raises(SystemExit, match="bypasses row-level security"):
        cli.main(["grant-api-login"])
