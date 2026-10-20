"""The test database, and the application's sessions on it.

The schema is the migrations' own, built once per run, so the tests see the
row-level security policies and privileges production has. The tables are
emptied before each test.

Two kinds of connection reach it, as in production:
- the owner of the tables (TEST_DATABASE_URL), who builds and empties them
  and, in `rewriting_history`, changes history that the API may not;
- the API's role, `sentinelcore_app`, which the policies bind. Its sessions
  sign in as the owner and take that role at once, so the tests need no
  second password.

A request starts with no scope, as in production, and sees no rows until it
says who is asking. Test code itself, which seeds and inspects, sees
everything.

The audit chains are checked after every test that used the database, so a
way of writing audit records that skips the seal fails the test that took it.
"""

import os

# A fixed key, so the tests never depend on the local .env. Set before the
# settings are read; an environment variable wins over .env.
TEST_AUDIT_CHAIN_KEY = "test-audit-chain-key-for-sentinelcore-tests"
os.environ.setdefault("AUDIT_CHAIN_KEY", TEST_AUDIT_CHAIN_KEY)

from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.core.config import settings
from app.core.row_security import APP_ROLE, restrict_rows
from app.main import app, create_app
from app.services.audit_chain_service import verify_chains
from app.services.tenancy import SYSTEM

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/sentinelcore_test",
)

if "sentinelcore_test" not in TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL must point to a test database to prevent data loss."
    )

BACKEND = Path(__file__).resolve().parent.parent

owner_engine = create_engine(TEST_DATABASE_URL)
# `role` set at sign-in, like SET ROLE: the policies and privileges of
# APP_ROLE apply from the first statement.
test_engine = create_engine(
    TEST_DATABASE_URL, connect_args={"options": f"-c role={APP_ROLE}"}
)

# The API's sessions: no scope until they are given one.
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
OwnerSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=owner_engine)


def system_session() -> Session:
    """A session of the API's role that sees every row, for test code that
    seeds or inspects the database."""
    db = TestingSessionLocal()
    restrict_rows(db, SYSTEM)
    return db


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    with owner_engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        config = Config()
        config.set_main_option("script_location", str(BACKEND / "migrations"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


@pytest.fixture()
def db_session(schema: None, request: pytest.FixtureRequest) -> Generator[Session]:
    with owner_engine.begin() as connection:
        tables = connection.scalars(
            text(
                "SELECT quote_ident(tablename) FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        ).all()
        connection.execute(
            text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
        )

    db = system_session()
    try:
        yield db
    finally:
        db.close()

    if request.node.get_closest_marker("breaks_audit_chain") is None:
        with system_session() as check:
            broken = [chain for chain in verify_chains(check) if not chain.intact]
        assert not broken, f"Audit chains broken by the test: {broken}"


@contextmanager
def rewriting_history(db_session: Session) -> Iterator[Session]:
    """A session of the tables' owner, for test code that moves events in
    time or deletes them, which the API's role may not. Its changes are
    committed, and `db_session` reads them afresh."""
    with OwnerSessionLocal() as owner:
        yield owner
        owner.commit()
    db_session.expire_all()


def serve_requests_from(db_session: Session) -> Callable[[], Generator[Session]]:
    """A `get_db` override that serves every request from `db_session`.

    Each request starts with no scope, as with a fresh session in
    production, and leaves the session to the test seeing everything again.
    """

    def override_get_db() -> Generator[Session]:
        restrict_rows(db_session, None)
        try:
            yield db_session
        finally:
            if not db_session.is_active:  # A request that failed mid-write.
                db_session.rollback()
            restrict_rows(db_session, SYSTEM)

    return override_get_db


def build_app(**changes: object) -> FastAPI:
    """An application of its own, built from the settings with `changes`.

    `app` is built once, from the local `.env`; a test that needs a setting
    either way builds its own instead.
    """
    return create_app(settings.model_copy(update=changes))


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient]:
    app.dependency_overrides[get_db] = serve_requests_from(db_session)
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
