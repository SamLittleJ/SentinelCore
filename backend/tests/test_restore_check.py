"""The check of a restored backup (`make backup-check`, docs/06-backups.md):
the restored copy's audit chains verify, each chain's last restored record
is in the live database with the same seal, and the append-only tables hold
rows, no more than live.

The restored copy is a second test database, migrated like the first; each
test fills it by copying the live rows, then changes it."""

from collections.abc import Iterator
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import (
    Integer,
    create_engine,
    delete,
    insert,
    make_url,
    select,
    text,
    update,
)
from sqlalchemy.orm import Session, sessionmaker

from app import cli
from app.core.database import Base
from app.models.audit_log import AuditEventType, AuditLog
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.services.audit_service import create_audit_log
from app.services.restore_check import compare_restore
from tests.accounts import organization_id
from tests.conftest import BACKEND, TEST_DATABASE_URL, OwnerSessionLocal

RESTORED_DATABASE = "sentinelcore_test_restore"
RESTORED_URL = make_url(TEST_DATABASE_URL).set(database=RESTORED_DATABASE)
restored_engine = create_engine(RESTORED_URL)
RestoredSession = sessionmaker(autoflush=False, bind=restored_engine)


@pytest.fixture(scope="module")
def restored_schema() -> Iterator[None]:
    server = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(
            text(f"DROP DATABASE IF EXISTS {RESTORED_DATABASE} WITH (FORCE)")
        )
        connection.execute(text(f"CREATE DATABASE {RESTORED_DATABASE}"))
    with restored_engine.begin() as connection:
        config = Config()
        config.set_main_option("script_location", str(BACKEND / "migrations"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield
    restored_engine.dispose()
    with server.connect() as connection:
        connection.execute(
            text(f"DROP DATABASE IF EXISTS {RESTORED_DATABASE} WITH (FORCE)")
        )
    server.dispose()


@pytest.fixture()
def restored(restored_schema: None, db_session: Session) -> Iterator[Session]:
    """The restored copy, empty; `db_session` empties the live one."""
    with restored_engine.begin() as connection:
        tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    with RestoredSession() as session:
        yield session


@pytest.fixture()
def live(db_session: Session) -> Iterator[Session]:
    """The live database as its owner, as `compare-restore` reads it."""
    with OwnerSessionLocal() as session:
        yield session


def copy_live_into(restored: Session) -> None:
    """A restore of a dump taken now: every row of every table."""
    with OwnerSessionLocal() as live:
        for table in Base.metadata.sorted_tables:
            rows: list[dict[str, Any]] = [
                dict(row._mapping) for row in live.execute(select(table))
            ]
            if rows:
                restored.execute(insert(table), rows)
    restored.commit()
    with restored_engine.begin() as connection:
        # Identities carry on from the copied rows, as after pg_restore.
        for table in Base.metadata.sorted_tables:
            if "id" in table.c and isinstance(table.c.id.type, Integer):
                connection.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                        f"coalesce(max(id), 1)) FROM {table.name}"
                    )
                )


def write(
    db: Session, organization: int | None, count: int, words: str = "Record"
) -> None:
    for index in range(count):
        create_audit_log(
            db,
            AuditEventType.ADMIN_ENDPOINT_ACCESSED,
            f"{words} {index} for a restore test",
            ip_address="203.0.113.5",
            organization_id=organization,
        )
    db.commit()


def security_event(db: Session) -> None:
    db.add(
        SecurityEvent(
            event_type=SecurityEventType.LOGIN_FAILED,
            severity=SecuritySeverity.WARN,
            source="backend",
            message="A failed sign-in for a restore test",
        )
    )
    db.commit()


@pytest.fixture()
def history(db_session: Session) -> int:
    """Live: Acme's chain of three records, the platform's of two, one
    security event."""
    acme = organization_id(db_session, "acme")
    write(db_session, acme, 3)
    write(db_session, None, 2)
    security_event(db_session)
    return acme


def test_a_copy_of_the_live_history_passes(
    history: int, live: Session, restored: Session
) -> None:
    copy_live_into(restored)

    report = compare_restore(live, restored)

    assert report.problems == []
    counts = {count.table: (count.restored, count.live) for count in report.counts}
    assert counts["audit_logs"] == (5, 5)
    assert counts["security_events"] == (1, 1)


def test_an_older_copy_passes_while_live_has_grown(
    history: int, db_session: Session, live: Session, restored: Session
) -> None:
    copy_live_into(restored)
    write(db_session, history, 2)
    security_event(db_session)

    assert compare_restore(live, restored).problems == []


def test_a_chain_from_another_database_fails(
    history: int, live: Session, restored: Session
) -> None:
    # Sealed with the same key, intact in itself, but not this history.
    acme = history
    copy_live_into(restored)
    restored.execute(delete(AuditLog).where(AuditLog.organization_id == acme))
    restored.commit()
    write(restored, acme, 3, words="Other")

    problems = compare_restore(live, restored).problems

    assert problems == [
        f"chain {acme}: record 3 is not in the live database with the same seal"
    ]


def test_more_restored_rows_than_live_fails(
    history: int, live: Session, restored: Session
) -> None:
    copy_live_into(restored)
    security_event(restored)

    problems = compare_restore(live, restored).problems

    assert problems == ["security_events: restored 2, live 1"]


def test_an_empty_restore_fails(history: int, live: Session, restored: Session) -> None:
    problems = compare_restore(live, restored).problems

    assert problems == ["audit_logs: restored 0", "security_events: restored 0"]


def test_a_broken_chain_in_the_copy_fails(
    history: int, live: Session, restored: Session
) -> None:
    copy_live_into(restored)
    restored.execute(
        update(AuditLog)
        .where(AuditLog.organization_id == history, AuditLog.chain_seq == 2)
        .values(message="Changed after the dump")
    )
    restored.commit()

    problems = compare_restore(live, restored).problems

    assert f"chain {history}: broken at record 2 (changed)" in problems


# The command


@pytest.fixture()
def cli_databases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli.settings, "migrations_database_url", TEST_DATABASE_URL, raising=False
    )


def test_the_command_prints_counts_and_succeeds(
    history: int,
    restored: Session,
    cli_databases: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    copy_live_into(restored)

    cli.main(["compare-restore", "--restored-database", RESTORED_DATABASE])

    out = capsys.readouterr().out
    assert "audit_logs: restored 5, live 5" in out
    assert "chain platform: 2 records, intact, same seal as live" in out
    assert out.rstrip().endswith("The restored copy matches the live history.")
    assert "203.0.113.5" not in out


def test_the_command_exits_with_1_on_a_problem(
    history: int,
    restored: Session,
    cli_databases: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_:
        cli.main(["compare-restore", "--restored-database", RESTORED_DATABASE])

    assert exit_.value.code == 1
    assert "audit_logs: restored 0" in capsys.readouterr().out
