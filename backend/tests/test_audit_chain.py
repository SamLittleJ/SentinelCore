"""The sealed audit history (T-45).

Each organization's audit records form a chain, and the platform's one more:
each record carries its place and an HMAC over its fields and the record
before it. The owner of the tables can still change any row, but cannot seal
it again without AUDIT_CHAIN_KEY, which the database never holds, so the
change shows when the chains are checked.
"""

import logging
import threading
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from prometheus_client import REGISTRY
from pydantic import SecretStr, ValidationError
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.orm import Session

from app import cli
from app.core.audit_seal import GENESIS, seal
from app.core.config import Settings, settings
from app.core.row_security import restrict_rows
from app.models.audit_log import AuditEventType, AuditLog, in_chain
from app.models.security_event import (
    DETECTION_SOURCE,
    MITRE_TECHNIQUES,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.services import audit_chain_service, session_cleanup
from app.services.audit_chain_service import (
    ChainCheck,
    alert_broken_chain,
    check_audit_chains,
    verify_chains,
)
from app.services.audit_service import create_audit_log
from app.services.tenancy import SYSTEM, Scope
from tests.accounts import create_account, organization_id
from tests.conftest import (
    BACKEND,
    TestingSessionLocal,
    owner_engine,
    rewriting_history,
)

BROKEN = SecurityEventType.AUDIT_CHAIN_BROKEN
KEY = settings.audit_chain_key.get_secret_value().encode()


@pytest.fixture(autouse=True)
def fresh_memory() -> Iterator[None]:
    """Each test starts as a process that has not checked the chains yet."""
    audit_chain_service._last_lengths.clear()
    yield
    audit_chain_service._last_lengths.clear()


def write(db: Session, organization: int | None, count: int) -> None:
    for index in range(count):
        create_audit_log(
            db,
            AuditEventType.ADMIN_ENDPOINT_ACCESSED,
            f"Record {index} for a test",
            ip_address="203.0.113.5",
            organization_id=organization,
        )


def chain(db: Session, organization: int | None) -> list[AuditLog]:
    db.expire_all()
    return list(
        db.scalars(
            select(AuditLog).where(in_chain(organization)).order_by(AuditLog.chain_seq)
        )
    )


def check_of(db: Session, organization: int | None) -> ChainCheck:
    return next(
        check for check in verify_chains(db) if check.organization_id == organization
    )


def resealed(record: AuditLog, previous: str, key: bytes = KEY) -> str:
    return seal(
        key,
        previous=previous,
        chain_seq=record.chain_seq,
        event_type=record.event_type.name,
        user_id=record.user_id,
        target_user_id=record.target_user_id,
        organization_id=record.organization_id,
        email=record.email,
        ip_address=record.ip_address,
        message=record.message,
        created_at=record.created_at,
    )


def broken_alerts(db: Session) -> list[SecurityEvent]:
    db.expire_all()
    return list(
        db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == BROKEN))
    )


# Sealing


def test_each_organization_and_the_platform_has_a_chain_of_its_own(
    db_session: Session,
) -> None:
    acme = organization_id(db_session, "acme")
    globex = organization_id(db_session, "globex")
    write(db_session, acme, 3)
    write(db_session, None, 2)
    write(db_session, globex, 1)
    write(db_session, acme, 1)

    for organization, length in ((acme, 4), (globex, 1), (None, 2)):
        records = chain(db_session, organization)
        assert [record.chain_seq for record in records] == list(range(1, length + 1))
        previous = GENESIS
        for record in records:
            assert record.chain_hash == resealed(record, previous)
            assert len(record.chain_hash) == 64
            previous = record.chain_hash

    assert [
        (check.organization_id, check.records) for check in verify_chains(db_session)
    ] == [(None, 2), (acme, 4), (globex, 1)]
    assert all(check.intact for check in verify_chains(db_session))


def test_every_way_of_writing_audit_records_is_sealed(db_session: Session) -> None:
    """An account's creation writes its record through a service of its own,
    not create_audit_log; the seal is set on flush, whoever adds the row."""
    create_account("sealed")

    [record] = chain(db_session, organization_id(db_session))
    assert record.event_type == AuditEventType.USER_REGISTERED
    assert record.chain_seq == 1
    assert record.chain_hash == resealed(record, GENESIS)


def test_records_added_together_take_consecutive_places(db_session: Session) -> None:
    acme = organization_id(db_session, "acme")
    db_session.add_all(
        AuditLog(
            event_type=AuditEventType.USERS_VIEWED,
            organization_id=organization,
            message=f"Read {index}",
        )
        for index, organization in enumerate((acme, None, acme, None, acme))
    )
    db_session.commit()

    assert [record.chain_seq for record in chain(db_session, acme)] == [1, 2, 3]
    assert [record.message for record in chain(db_session, acme)] == [
        "Read 0",
        "Read 2",
        "Read 4",
    ]
    assert [record.chain_seq for record in chain(db_session, None)] == [1, 2]
    assert all(check.intact for check in verify_chains(db_session))


def test_the_seal_covers_the_database_clock_time(db_session: Session) -> None:
    """The time the database would have stamped: its clock when the record's
    transaction began, as now() gives."""
    began = db_session.scalar(select(func.now()))  # Begins the transaction.
    write(db_session, None, 1)

    [record] = chain(db_session, None)
    assert record.created_at == began
    assert record.chain_hash == resealed(record, GENESIS)


def test_an_organization_seals_its_own_chain_under_row_security(
    db_session: Session,
) -> None:
    """A request inside one organization sees only that organization's rows,
    which is all the chain it writes needs."""
    acme = organization_id(db_session, "acme")
    write(db_session, None, 3)
    write(db_session, acme, 2)

    with TestingSessionLocal() as db:
        restrict_rows(db, Scope(organization_id=acme))
        write(db, acme, 1)

    assert [record.chain_seq for record in chain(db_session, acme)] == [1, 2, 3]
    assert all(check.intact for check in verify_chains(db_session))


def test_concurrent_writers_never_share_a_place(db_session: Session) -> None:
    acme = organization_id(db_session, "acme")
    writers, each = 4, 15
    start = threading.Barrier(writers)
    errors: list[BaseException] = []

    def writer() -> None:
        try:
            with TestingSessionLocal() as db:
                restrict_rows(db, SYSTEM)
                start.wait()
                write(db, acme, each)
        except BaseException as error:  # Reported by the test below.
            errors.append(error)

    threads = [threading.Thread(target=writer) for _ in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert [record.chain_seq for record in chain(db_session, acme)] == list(
        range(1, writers * each + 1)
    )
    assert check_of(db_session, acme).intact


# Verifying


@pytest.mark.breaks_audit_chain
@pytest.mark.parametrize(
    "field",
    [
        "event_type",
        "user_id",
        "target_user_id",
        "email",
        "ip_address",
        "message",
        "created_at",
        "chain_hash",
    ],
)
def test_changing_any_sealed_field_breaks_the_chain_there(
    db_session: Session, field: str
) -> None:
    acme = organization_id(db_session, "acme")
    user_id = create_account("actor", organization="acme")
    write(db_session, acme, 3)  # Places 2 to 4, after the account's record.
    values: dict[str, Any] = {
        "event_type": AuditEventType.LOGIN_FAILED,
        "user_id": user_id,
        "target_user_id": user_id,
        "email": "someone@example.com",
        "ip_address": "198.51.100.77",
        "message": "Nothing happened",
        "created_at": AuditLog.created_at - timedelta(hours=1),
        "chain_hash": "f" * 64,
    }

    with rewriting_history(db_session) as owner:
        owner.execute(
            update(AuditLog)
            .where(in_chain(acme), AuditLog.chain_seq == 3)
            .values({field: values[field]})
        )

    check = check_of(db_session, acme)
    assert (check.broken_at, check.problem, check.records) == (3, "changed", 4)


@pytest.mark.breaks_audit_chain
def test_moving_a_record_to_another_organization_breaks_both_chains(
    db_session: Session,
) -> None:
    acme = organization_id(db_session, "acme")
    globex = organization_id(db_session, "globex")
    write(db_session, acme, 3)
    write(db_session, globex, 1)

    with rewriting_history(db_session) as owner:
        owner.execute(
            update(AuditLog)
            .where(in_chain(acme), AuditLog.chain_seq == 3)
            .values(organization_id=globex, chain_seq=2)
        )

    left, moved_to = check_of(db_session, acme), check_of(db_session, globex)
    assert (left.problem, left.records) == (None, 2)
    assert (moved_to.broken_at, moved_to.problem) == (2, "changed")


@pytest.mark.breaks_audit_chain
def test_a_deleted_record_leaves_its_place_missing(db_session: Session) -> None:
    write(db_session, None, 5)

    with rewriting_history(db_session) as owner:
        owner.execute(delete(AuditLog).where(in_chain(None), AuditLog.chain_seq == 2))

    check = check_of(db_session, None)
    assert (check.broken_at, check.problem, check.records) == (2, "missing", 5)


@pytest.mark.breaks_audit_chain
def test_a_deleted_first_record_leaves_its_place_missing(db_session: Session) -> None:
    write(db_session, None, 2)

    with rewriting_history(db_session) as owner:
        owner.execute(delete(AuditLog).where(in_chain(None), AuditLog.chain_seq == 1))

    check = check_of(db_session, None)
    assert (check.broken_at, check.problem) == (1, "missing")


@pytest.mark.breaks_audit_chain
@pytest.mark.parametrize("key", [b"", b"a key the owner of the tables made up"])
def test_a_record_sealed_without_the_key_does_not_verify(
    db_session: Session, key: bytes
) -> None:
    """The owner of the tables adds a record and seals it as best they can:
    without AUDIT_CHAIN_KEY, every guess at the seal is wrong."""
    write(db_session, None, 2)
    [_, head] = chain(db_session, None)
    forged = AuditLog(
        event_type=AuditEventType.LOGIN_SUCCESS,
        message="A sign-in that never happened",
        created_at=head.created_at,
        chain_seq=3,
    )
    forged_seal = resealed(forged, head.chain_hash, key)

    with rewriting_history(db_session) as owner:
        owner.execute(
            insert(AuditLog).values(
                event_type=forged.event_type,
                message=forged.message,
                created_at=forged.created_at,
                chain_seq=3,
                chain_hash=forged_seal,
            )
        )

    check = check_of(db_session, None)
    assert (check.broken_at, check.problem, check.records) == (3, "changed", 3)


def test_the_seal_hides_nothing_it_covers(db_session: Session) -> None:
    """The same fields and the same previous seal always give the same seal,
    and any other previous seal gives another: the chain is the order."""
    write(db_session, None, 2)
    [first, second] = chain(db_session, None)

    assert resealed(second, first.chain_hash) == second.chain_hash
    assert resealed(second, GENESIS) != second.chain_hash


# The periodic check and its alert


def test_an_intact_history_raises_no_alert_and_reports_its_heads(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    acme = organization_id(db_session, "acme")
    write(db_session, acme, 2)
    write(db_session, None, 1)

    with caplog.at_level(logging.INFO, logger=audit_chain_service.__name__):
        checks = check_audit_chains(db_session)

    assert broken_alerts(db_session) == []
    assert [check.label for check in checks] == ["platform", str(acme)]
    logged = {
        record.__dict__["chain"]: record
        for record in caplog.records
        if record.getMessage() == "Audit chain checked"
    }
    assert logged[str(acme)].__dict__["records"] == 2
    assert logged[str(acme)].__dict__["head"] == chain(db_session, acme)[-1].chain_hash
    assert logged[str(acme)].__dict__["intact"] is True
    assert logged["platform"].__dict__["records"] == 1
    sample = REGISTRY.get_sample_value
    assert sample("sentinelcore_audit_chain_records", {"chain": str(acme)}) == 2
    assert sample("sentinelcore_audit_chain_intact", {"chain": str(acme)}) == 1
    assert sample("sentinelcore_audit_chain_intact", {"chain": "platform"}) == 1


@pytest.mark.breaks_audit_chain
def test_a_broken_chain_raises_one_platform_alert(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    acme = organization_id(db_session, "acme")
    write(db_session, acme, 3)
    secret_message = chain(db_session, acme)[1].message
    with rewriting_history(db_session) as owner:
        owner.execute(
            update(AuditLog)
            .where(in_chain(acme), AuditLog.chain_seq == 2)
            .values(message="Nothing to see")
        )

    with caplog.at_level(logging.INFO, logger=audit_chain_service.__name__):
        check_audit_chains(db_session)
        check_audit_chains(db_session)

    [alert] = broken_alerts(db_session)
    assert alert.severity == SecuritySeverity.INCIDENT
    assert alert.source == DETECTION_SOURCE
    assert alert.organization_id is None
    assert alert.mitre_technique == MITRE_TECHNIQUES[BROKEN] == "T1070"
    assert alert.occurred_at is not None
    assert alert.message == (
        f"Audit history of Acme (organization {acme}) broken at record 2: changed"
    )
    assert secret_message is not None and secret_message not in alert.message
    assert "Nothing to see" not in alert.message
    errors = [
        record
        for record in caplog.records
        if record.getMessage() == "Audit chain checked"
        and record.__dict__["chain"] == str(acme)
    ]
    assert [record.levelno for record in errors] == [logging.ERROR] * 2
    assert (errors[0].__dict__["broken_at"], errors[0].__dict__["problem"]) == (
        2,
        "changed",
    )
    assert (
        REGISTRY.get_sample_value(
            "sentinelcore_audit_chain_intact", {"chain": str(acme)}
        )
        == 0
    )


@pytest.mark.breaks_audit_chain
def test_each_new_break_raises_an_alert_of_its_own(db_session: Session) -> None:
    write(db_session, None, 4)

    def tamper(place: int) -> None:
        with rewriting_history(db_session) as owner:
            owner.execute(
                update(AuditLog)
                .where(in_chain(None), AuditLog.chain_seq == place)
                .values(message="Changed")
            )

    tamper(3)
    check_audit_chains(db_session)
    tamper(2)
    check_audit_chains(db_session)

    assert sorted(alert.message for alert in broken_alerts(db_session)) == [
        "Audit history of the platform broken at record 2: changed",
        "Audit history of the platform broken at record 3: changed",
    ]


@pytest.mark.breaks_audit_chain
def test_a_shorter_chain_than_at_the_last_check_is_truncated(
    db_session: Session,
) -> None:
    """Deleting the newest records leaves a chain that verifies; only its
    length, remembered from the last check, shows what went."""
    write(db_session, None, 5)
    assert check_audit_chains(db_session)[0].intact

    with rewriting_history(db_session) as owner:
        owner.execute(delete(AuditLog).where(in_chain(None), AuditLog.chain_seq >= 4))
    assert check_of(db_session, None).intact

    [check] = check_audit_chains(db_session)
    assert (check.broken_at, check.problem, check.records) == (4, "truncated", 3)
    [alert] = broken_alerts(db_session)
    assert (
        alert.message == "Audit history of the platform broken at record 4: truncated"
    )

    # Once reported, the shorter chain is the one later checks compare with.
    write(db_session, None, 1)
    assert check_audit_chains(db_session)[0].intact


@pytest.mark.breaks_audit_chain
def test_a_chain_deleted_whole_is_truncated(db_session: Session) -> None:
    acme = organization_id(db_session, "acme")
    write(db_session, acme, 2)
    check_audit_chains(db_session)

    with rewriting_history(db_session) as owner:
        owner.execute(delete(AuditLog).where(in_chain(acme)))

    [check] = check_audit_chains(db_session)
    assert (check.organization_id, check.broken_at, check.problem) == (
        acme,
        1,
        "truncated",
    )
    assert len(broken_alerts(db_session)) == 1


def test_two_processes_raise_the_same_alert_once(db_session: Session) -> None:
    """Every API process runs the check; the alert lock and the lookup under
    it keep a break from being reported once per process."""
    check = ChainCheck(None, 3, GENESIS, broken_at=2, problem="changed")
    start = threading.Barrier(2)
    raised: list[SecurityEvent | None] = []

    def process() -> None:
        with TestingSessionLocal() as db:
            restrict_rows(db, SYSTEM)
            start.wait()
            raised.append(alert_broken_chain(db, check))

    threads = [threading.Thread(target=process) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(alert is None for alert in raised) == [False, True]
    assert len(broken_alerts(db_session)) == 1


@pytest.mark.breaks_audit_chain
def test_the_cleanup_task_checks_the_chains(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(session_cleanup, "SessionLocal", TestingSessionLocal)
    write(db_session, None, 2)
    with rewriting_history(db_session) as owner:
        owner.execute(update(AuditLog).where(in_chain(None)).values(email="x@y.z"))

    session_cleanup.run_session_cleanup()

    assert len(broken_alerts(db_session)) == 1


def test_a_failed_check_leaves_the_cleanup_done(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(db: Session) -> None:
        raise RuntimeError("database gone")

    monkeypatch.setattr(session_cleanup, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(session_cleanup, "check_audit_chains", fail)

    with caplog.at_level(logging.INFO, logger=session_cleanup.__name__):
        assert session_cleanup.run_session_cleanup() == 0

    messages = [record.getMessage() for record in caplog.records]
    assert "Audit chain check failed" in messages
    assert "Session cleanup completed" in messages


# The command


@pytest.fixture()
def cli_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "SessionLocal", TestingSessionLocal)


def test_the_command_prints_each_chain_and_succeeds_when_intact(
    db_session: Session, cli_database: None, capsys: pytest.CaptureFixture[str]
) -> None:
    acme = organization_id(db_session, "acme")
    write(db_session, acme, 2)
    write(db_session, None, 1)

    cli.main(["verify-audit-chain"])

    head = chain(db_session, acme)[-1].chain_hash
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("platform: 1 records, head ")
    assert lines[1] == f"organization {acme}: 2 records, head {head}, intact"


def test_the_command_says_when_there_is_nothing_to_check(
    db_session: Session, cli_database: None, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["verify-audit-chain"])

    assert capsys.readouterr().out == "No audit records yet.\n"


@pytest.mark.breaks_audit_chain
def test_the_command_fails_on_a_broken_chain_without_raising_an_alert(
    db_session: Session, cli_database: None, capsys: pytest.CaptureFixture[str]
) -> None:
    write(db_session, None, 3)
    with rewriting_history(db_session) as owner:
        owner.execute(delete(AuditLog).where(in_chain(None), AuditLog.chain_seq == 2))

    with pytest.raises(SystemExit) as exit:
        cli.main(["verify-audit-chain"])

    assert exit.value.code == 1
    assert "platform: 3 records" in capsys.readouterr().out
    assert broken_alerts(db_session) == []


@pytest.mark.breaks_audit_chain
def test_the_command_reports_the_break(
    db_session: Session, cli_database: None, capsys: pytest.CaptureFixture[str]
) -> None:
    write(db_session, None, 3)
    with rewriting_history(db_session) as owner:
        owner.execute(delete(AuditLog).where(in_chain(None), AuditLog.chain_seq == 2))

    with pytest.raises(SystemExit):
        cli.main(["verify-audit-chain"])

    assert capsys.readouterr().out.rstrip().endswith("BROKEN at record 2 (missing)")


# The key


def test_the_key_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDIT_CHAIN_KEY")
    with pytest.raises(ValidationError, match="audit_chain_key"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            database_url="postgresql+psycopg://x@localhost/x",
            secret_key="s" * 32,
        )


@pytest.mark.parametrize(
    ("key", "problem"),
    [
        ("k" * 31, "at least 32 bytes"),
        ("s" * 32, "must differ from SECRET_KEY"),
    ],
)
def test_the_key_must_be_long_and_its_own(key: str, problem: str) -> None:
    with pytest.raises(ValidationError, match=problem):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            database_url="postgresql+psycopg://x@localhost/x",
            secret_key="s" * 32,
            audit_chain_key=SecretStr(key),
        )


# The migration


def test_the_migration_seals_the_history_already_recorded(db_session: Session) -> None:
    """Records written before the seal existed are sealed in the order they
    were written, then the columns become required; going down and up again
    leaves the schema as it was."""
    acme = organization_id(db_session, "acme")
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    try:
        with owner_engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "a5eaa2f50fd1")
            for organization, message in (
                (acme, "First of Acme"),
                (None, "First of the platform"),
                (acme, "Second of Acme"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO audit_logs (event_type, organization_id, message) "
                        "VALUES ('USERS_VIEWED', :organization, :message)"
                    ),
                    {"organization": organization, "message": message},
                )
            command.upgrade(config, "head")
    finally:
        with owner_engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    assert [record.message for record in chain(db_session, acme)] == [
        "First of Acme",
        "Second of Acme",
    ]
    assert [
        (check.organization_id, check.records) for check in verify_chains(db_session)
    ] == [(None, 1), (acme, 2)]
    assert all(check.intact for check in verify_chains(db_session))

    # New records continue the sealed chains.
    write(db_session, acme, 1)
    assert check_of(db_session, acme).records == 3
    assert check_of(db_session, acme).intact
