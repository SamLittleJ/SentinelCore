"""The check of a restored backup (`make backup-check`, docs/06-backups.md).

A dump restored into a database of its own is compared with the live one:
its audit chains verify with the key, each chain's last restored record is in
the live database with the same seal, so the copy is a prefix of the real
history rather than any chain sealed with the key, and the append-only tables
hold rows, no more than live. Both sessions belong to the owner of the
tables, which row-level security does not limit. Problems name chains and
tables, never a record's contents."""

from dataclasses import dataclass, field

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.audit_log import AuditLog, in_chain
from app.services.audit_chain_service import ChainCheck, verify_chains

# Rows are added, never removed (sessions and usage hours are cleaned up, so
# their counts may shrink after a dump).
APPEND_ONLY = ("audit_logs", "security_events")


@dataclass(frozen=True)
class TableCount:
    table: str
    restored: int
    live: int


@dataclass(frozen=True)
class ChainComparison:
    check: ChainCheck
    # The chain's last restored record is in the live database, same seal.
    in_live: bool


@dataclass(frozen=True)
class RestoreReport:
    chains: list[ChainComparison]
    counts: list[TableCount]
    problems: list[str] = field(default_factory=list)


def compare_restore(live: Session, restored: Session) -> RestoreReport:
    chains = [
        ChainComparison(check, _in_live(live, check))
        for check in verify_chains(restored)
    ]
    counts = [
        TableCount(table.name, _count(restored, table.name), _count(live, table.name))
        for table in Base.metadata.sorted_tables
    ]

    problems: list[str] = []
    for chain in chains:
        check = chain.check
        if not check.intact:
            problems.append(
                f"chain {check.label}: broken at record {check.broken_at} "
                f"({check.problem})"
            )
        elif not chain.in_live:
            problems.append(
                f"chain {check.label}: record {check.records} is not in the live "
                "database with the same seal"
            )
    for count in counts:
        if count.table not in APPEND_ONLY:
            continue
        if count.restored == 0:
            problems.append(f"{count.table}: restored 0")
        elif count.restored > count.live:
            problems.append(
                f"{count.table}: restored {count.restored}, live {count.live}"
            )
    return RestoreReport(chains, counts, problems)


def _in_live(live: Session, check: ChainCheck) -> bool:
    seal = live.scalar(
        select(AuditLog.chain_hash).where(
            in_chain(check.organization_id), AuditLog.chain_seq == check.records
        )
    )
    return seal == check.head


def _count(db: Session, table: str) -> int:
    # The names come from the models, never from input.
    return db.scalar(select(func.count()).select_from(text(table))) or 0
