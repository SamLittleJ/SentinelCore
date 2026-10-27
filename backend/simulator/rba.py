"""Command line: python -m simulator.rba --data .rba/rba-dataset.csv

The detection rules measured on data they were not written for: the Login
Data Set for Risk-Based Authentication (Wiefling, Jørgensen, Thunem and Lo
Iacono, 2022; Zenodo, DOI 10.5281/zenodo.6782155, CC BY 4.0). It holds 31
million sign-ins of a large online service, synthesized from the real ones,
with two labels: the address is on a list of known attackers, and the
service's incident response confirmed an account takeover.

Two experiments, both through the API of a SentinelCore running on the
`sentinelcore_eval` database (`make evaluate-rba`):

A. Accounts. Every user with a confirmed takeover in the last twelve months
   of the data, and a sample of the others, drawn in proportion to how often
   they sign in. They become accounts of one organization, and their sign-ins
   are reported through ingestion, oldest first. Measured: the unfamiliar
   network and device rule (T1078) against the takeover label, and how often
   the dormant account rule fires.
B. Addresses. Every sign-in of a few whole weeks, drawn at random, each week
   in an organization of its own. Measured: the password spray rule
   (T1110.003) against the attacker-address label, and B1, this
   application's own lockout after five failures, replayed on the same
   sign-ins.

The thresholds are the application's settings, never fitted to this data.
Every rate comes with a 95% Wilson interval. The times are moved, keeping
their order and spacing, so that each experiment ends now: ingestion takes
events up to a year old. Only the accounts are written to the database
directly; this step refuses any database but the evaluation's.
"""

import argparse
import csv
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict, deque
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.security_event import (
    DETECTION_SOURCE,
    SecurityEvent,
    SecurityEventType,
)
from app.models.user import User, UserRole
from simulator.client import SentinelCore, SimulatorError

EVAL_DATABASE = "sentinelcore_eval"
DATASET = "Login Data Set for Risk-Based Authentication, DOI 10.5281/zenodo.6782155"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# The last twelve months of the data, less a margin: ingestion refuses events
# more than a year old, and the run itself takes time.
HISTORY = timedelta(days=360)
WEEK = timedelta(days=7)
# Each experiment ends this long before the run starts.
END_MARGIN = timedelta(hours=1)
# Users by how many sign-ins they have in the window: the sample keeps the
# data's proportions, so false alarms per 1,000 sign-ins reflect its users.
STRATA = ((1, 9), (10, 49), (50, None))
Z_95 = 1.959964
EMAIL_DOMAIN = "rba.example"
# No one signs in as these accounts: this is no password hash at all.
NO_PASSWORD = "!"  # nosec B105
USER_AGENT_LIMIT = 255


@dataclass(frozen=True)
class Login:
    at: datetime
    user: int
    ip: str
    user_agent: str
    success: bool
    attack_ip: bool
    takeover: bool
    # What B2 (simulator/freeman.py) also scores; the rules use none of it.
    asn: str = ""
    country: str = ""
    browser: str = ""
    os: str = ""
    device_type: str = ""


def parse_time(text: str) -> datetime:
    # The data's times carry no zone; they are read as UTC.
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def read_logins(path: Path) -> Iterator[Login]:
    with path.open(newline="") as file:
        rows = csv.DictReader(file)
        for row in rows:
            yield Login(
                at=parse_time(row["Login Timestamp"]),
                user=int(row["User ID"]),
                ip=row["IP Address"],
                user_agent=row["User Agent String"],
                success=row["Login Successful"] == "True",
                attack_ip=row["Is Attack IP"] == "True",
                takeover=row["Is Account Takeover"] == "True",
                asn=row["ASN"],
                country=row["Country"],
                browser=row["Browser Name and Version"],
                os=row["OS Name and Version"],
                device_type=row["Device Type"],
            )


def email_of(user: int) -> str:
    # The data's ids are signed 64-bit integers.
    return f"u{user % 2**64:016x}@{EMAIL_DOMAIN}"


# Rates


@dataclass(frozen=True)
class Rate:
    hits: int
    total: int

    @property
    def value(self) -> float | None:
        return self.hits / self.total if self.total else None

    @property
    def interval(self) -> tuple[float, float] | None:
        return wilson(self.hits, self.total)


def wilson(hits: int, total: int, z: float = Z_95) -> tuple[float, float] | None:
    """The Wilson score interval of hits/total, or None for no trials."""
    if total == 0:
        return None
    p = hits / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    half /= denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def per_thousand(count: int, logins: int) -> float:
    return 1000 * count / logins if logins else 0.0


# Sampling


@dataclass
class Plan:
    """What the two experiments use, drawn before any result is seen."""

    start: datetime
    end: datetime
    users: set[int]
    takeover_users: set[int]
    takeover_users_before_start: int
    weeks: list[datetime]
    population: dict[str, int] = field(default_factory=dict)


def stratum(count: int) -> int:
    for index, (low, high) in enumerate(STRATA):
        if count >= low and (high is None or count <= high):
            return index
    raise ValueError(count)


def draw_users(
    counts: dict[int, int], excluded: set[int], size: int, rng: random.Random
) -> set[int]:
    """`size` users not in `excluded`, from each stratum in proportion to
    its share of them. Sorted first, so one seed draws the same users."""
    strata: list[list[int]] = [[] for _ in STRATA]
    for user, count in counts.items():
        if user not in excluded:
            strata[stratum(count)].append(user)
    available = sum(len(group) for group in strata)
    drawn: set[int] = set()
    for group in strata:
        group.sort()
        share = round(size * len(group) / available) if available else 0
        drawn.update(rng.sample(group, min(share, len(group))))
    return drawn


def draw_weeks(
    start: datetime, end: datetime, count: int, rng: random.Random
) -> list[datetime]:
    """The starts of `count` whole weeks inside [start, end), not
    overlapping, in time order."""
    span = (end - WEEK - start).total_seconds()
    weeks: list[datetime] = []
    while len(weeks) < count:
        candidate = start + timedelta(seconds=rng.uniform(0, span))
        if all(abs(candidate - week) >= WEEK for week in weeks):
            weeks.append(candidate)
    return sorted(weeks)


def data_end(path: Path) -> datetime:
    """Just after the last sign-in: the data is in time order, so its last
    line holds it."""
    with path.open("rb") as file:
        file.seek(max(0, file.seek(0, os.SEEK_END) - 64 * 1024))
        last = file.read().decode().splitlines()[-1]
    return parse_time(next(csv.reader([last]))[1]) + timedelta(microseconds=1)


def plan(
    logins: Iterable[Login], end: datetime, users: int, weeks: int, seed: int
) -> Plan:
    """One pass over the data: each user's sign-ins in the window and the
    takeovers, then the draws."""
    start = end - HISTORY
    counts: Counter[int] = Counter()
    takeover_users: set[int] = set()
    takeovers_before: set[int] = set()
    for login in logins:
        if not start <= login.at < end:
            if login.takeover and login.at < start:
                takeovers_before.add(login.user)
            continue
        counts[login.user] += 1
        if login.takeover:
            takeover_users.add(login.user)
    rng = random.Random(seed)  # nosec B311
    sample = draw_users(counts, takeover_users, users, rng)
    population = Counter(stratum(count) for count in counts.values())
    return Plan(
        start=start,
        end=end,
        users=sample | takeover_users,
        takeover_users=takeover_users,
        takeover_users_before_start=len(takeovers_before - takeover_users),
        weeks=draw_weeks(start, end, weeks, rng),
        population={label(index): population[index] for index in range(len(STRATA))},
    )


def label(index: int) -> str:
    low, high = STRATA[index]
    return f"{low}+" if high is None else f"{low}-{high}"


def collect(
    logins: Iterable[Login], chosen: Plan
) -> tuple[list[Login], list[list[Login]]]:
    """The second pass: the sampled users' sign-ins in the window, and every
    sign-in of each drawn week."""
    accounts: list[Login] = []
    weeks: list[list[Login]] = [[] for _ in chosen.weeks]
    for login in logins:
        if not chosen.start <= login.at < chosen.end:
            continue
        if login.user in chosen.users:
            accounts.append(login)
        for index, week in enumerate(chosen.weeks):
            if week <= login.at < week + WEEK:
                weeks[index].append(login)
    accounts.sort(key=lambda login: login.at)
    for week_logins in weeks:
        week_logins.sort(key=lambda login: login.at)
    return accounts, weeks


# Replaying the sign-ins


def event_of(login: Login, shift: timedelta) -> dict | None:
    """The ingestion event for `login`, its time moved by `shift`, or None
    when its address is not one."""
    try:
        address = str(ip_address(login.ip))
    except ValueError:
        return None
    return {
        "event_type": "login_success" if login.success else "login_failed",
        "occurred_at": (login.at + shift).isoformat(),
        "email": email_of(login.user),
        "ip_address": address,
        "user_agent": login.user_agent[:USER_AGENT_LIMIT] or None,
    }


def shift_to_now(last: datetime, now: datetime) -> timedelta:
    """How far to move times so that `last` falls END_MARGIN before now."""
    return now - END_MARGIN - last


def create_accounts(db: Session, organization_id: int, users: Iterable[int]) -> int:
    accounts = [
        User(
            username=f"rba-{user % 2**64:016x}",
            email=email_of(user),
            hashed_password=NO_PASSWORD,
            role=UserRole.USER,
            organization_id=organization_id,
        )
        for user in sorted(users)
    ]
    db.add_all(accounts)
    db.commit()
    return len(accounts)


@dataclass(frozen=True)
class Alert:
    event_type: SecurityEventType
    email: str | None
    ip: str | None
    at: datetime


def alerts_of(db: Session, organization_id: int) -> list[Alert]:
    rows = db.execute(
        select(
            SecurityEvent.event_type,
            SecurityEvent.email,
            SecurityEvent.ip_address,
            SecurityEvent.occurred_at,
        ).where(
            SecurityEvent.source == DETECTION_SOURCE,
            SecurityEvent.organization_id == organization_id,
        )
    ).all()
    return [Alert(kind, email, ip, at) for kind, email, ip, at in rows]


# Measuring


def to_millisecond(at: datetime) -> datetime:
    return at.replace(microsecond=at.microsecond // 1000 * 1000)


def eligible_takeovers(
    logins: list[Login],
    lookback_days: int | None = None,
    min_sign_ins: int | None = None,
) -> set[tuple[int, datetime]]:
    """The successful takeover sign-ins the T1078 rule can judge: those after
    enough successful sign-ins in its lookback to compare with. The
    thresholds default to the application's settings."""
    lookback = timedelta(
        days=lookback_days or settings.detection_unfamiliar_lookback_days
    )
    minimum = min_sign_ins or settings.detection_unfamiliar_min_sign_ins
    history: dict[int, deque[datetime]] = defaultdict(deque)
    eligible = set()
    for login in logins:
        if not login.success:
            continue
        past = history[login.user]
        while past and past[0] < login.at - lookback:
            past.popleft()
        if login.takeover and len(past) >= minimum:
            eligible.add((login.user, login.at))
        past.append(login.at)
    return eligible


@dataclass
class AccountResult:
    users: int
    takeover_users: int
    takeover_users_before_start: int
    logins: int
    successful: int
    takeover_logins: int
    takeover_successful: int
    takeover_eligible: int
    alerts: int
    alerts_on_takeovers: int
    users_caught: int
    eligible_caught: int
    dormant_alerts: int
    skipped: int

    @property
    def recall(self) -> Rate:
        return Rate(self.alerts_on_takeovers, self.takeover_successful)

    @property
    def recall_eligible(self) -> Rate:
        return Rate(self.eligible_caught, self.takeover_eligible)

    @property
    def recall_users(self) -> Rate:
        return Rate(self.users_caught, self.takeover_users)

    @property
    def precision(self) -> Rate:
        return Rate(self.alerts_on_takeovers, self.alerts)

    @property
    def false_alarms_per_thousand(self) -> float:
        return per_thousand(self.alerts - self.alerts_on_takeovers, self.logins)

    @property
    def dormant_per_thousand(self) -> float:
        return per_thousand(self.dormant_alerts, self.logins)


def measure_accounts(
    logins: list[Login],
    alerts: list[Alert],
    shift: timedelta,
    chosen: Plan,
    skipped: int,
    lookback_days: int | None = None,
    min_sign_ins: int | None = None,
) -> AccountResult:
    user_of = {email_of(user): user for user in chosen.users}
    takeover_at = {
        (login.user, to_millisecond(login.at))
        for login in logins
        if login.takeover and login.success
    }
    eligible = {
        (user, to_millisecond(at))
        for user, at in eligible_takeovers(logins, lookback_days, min_sign_ins)
    }
    unfamiliar = [
        a for a in alerts if a.event_type == SecurityEventType.UNFAMILIAR_SIGN_IN
    ]
    hits = set()
    for alert in unfamiliar:
        user = user_of.get(alert.email or "")
        if user is not None:
            key = (user, to_millisecond(alert.at - shift))
            if key in takeover_at:
                hits.add(key)
    return AccountResult(
        users=len(chosen.users),
        takeover_users=len(chosen.takeover_users),
        takeover_users_before_start=chosen.takeover_users_before_start,
        logins=len(logins),
        successful=sum(login.success for login in logins),
        takeover_logins=sum(login.takeover for login in logins),
        takeover_successful=len(takeover_at),
        takeover_eligible=len(eligible),
        alerts=len(unfamiliar),
        alerts_on_takeovers=len(hits),
        users_caught=len({user for user, _ in hits}),
        eligible_caught=len(hits & eligible),
        dormant_alerts=sum(
            alert.event_type == SecurityEventType.DORMANT_ACCOUNT_LOGIN
            for alert in alerts
        ),
        skipped=skipped,
    )


@dataclass
class Lockout:
    """B1 on one week: this application's lockout, replayed per email.

    Legitimate means a sign-in that would have succeeded, from an address not
    marked as an attacker, and not a takeover: someone with the right
    password. The data's failures from unmarked addresses are not counted as
    legitimate: many are attacks the label does not know."""

    attack_attempts: int = 0
    attack_denied: int = 0
    legitimate_attempts: int = 0
    legitimate_denied: int = 0
    legitimate_users_denied: int = 0
    lockouts: int = 0


def replay_lockout(logins: list[Login], limit: int | None = None) -> Lockout:
    """As services/login_protection_service.py: `login_max_failed_attempts`
    failures within the window, counted since the last success or lockout,
    lock the email for `login_lockout_minutes`; attempts while locked are
    refused and not counted. `limit` replaces the setting."""
    window = timedelta(minutes=settings.login_failure_window_minutes)
    lock_for = timedelta(minutes=settings.login_lockout_minutes)
    limit = limit or settings.login_max_failed_attempts
    failures: dict[int, deque[datetime]] = defaultdict(deque)
    locked_until: dict[int, datetime] = {}
    denied_users: set[int] = set()
    result = Lockout()
    for login in logins:
        legitimate = login.success and not login.attack_ip and not login.takeover
        result.attack_attempts += login.attack_ip
        result.legitimate_attempts += legitimate
        until = locked_until.get(login.user)
        if until is not None and login.at < until:
            result.attack_denied += login.attack_ip
            if legitimate:
                result.legitimate_denied += 1
                denied_users.add(login.user)
            continue
        recent = failures[login.user]
        if login.success:
            recent.clear()
            continue
        while recent and recent[0] <= login.at - window:
            recent.popleft()
        recent.append(login.at)
        if len(recent) >= limit:
            locked_until[login.user] = login.at + lock_for
            recent.clear()
            result.lockouts += 1
    result.legitimate_users_denied = len(denied_users)
    return result


def peak_emails(logins: list[Login]) -> int:
    """The most different emails one address failed on within the spray
    rule's window: what the rule compares with its threshold."""
    window = timedelta(minutes=settings.detection_spray_window_minutes)
    failures = sorted((login.at, login.user) for login in logins if not login.success)
    peak = 0
    first = 0
    for last in range(len(failures)):
        while failures[last][0] - failures[first][0] > window:
            first += 1
        peak = max(peak, len({user for _, user in failures[first : last + 1]}))
    return peak


@dataclass
class WeekResult:
    start: datetime
    logins: int
    failed: int
    attack_ips: int
    # The most emails any attacker address failed on within the window, and
    # how many such addresses reached the rule's threshold.
    attack_peak: int
    attack_ips_at_threshold: int
    flagged_ips: int
    flagged_attack_ips: int
    alerts: int
    alerts_on_attack_ips: int
    skipped: int
    lockout: Lockout

    @property
    def recall(self) -> Rate:
        return Rate(self.flagged_attack_ips, self.attack_ips)

    @property
    def precision(self) -> Rate:
        return Rate(self.flagged_attack_ips, self.flagged_ips)

    @property
    def false_alarms_per_thousand(self) -> float:
        return per_thousand(self.alerts - self.alerts_on_attack_ips, self.logins)


def measure_week(
    start: datetime,
    logins: list[Login],
    alerts: list[Alert],
    skipped: int,
    min_accounts: int | None = None,
) -> WeekResult:
    threshold = min_accounts or settings.detection_spray_min_accounts
    # The rule sees failures, so an address counts once it has failed here.
    attack_ips = {login.ip for login in logins if login.attack_ip and not login.success}
    known = {login.ip for login in logins if login.attack_ip}
    sprays = [
        a for a in alerts if a.event_type == SecurityEventType.PASSWORD_SPRAY_DETECTED
    ]
    flagged = {alert.ip for alert in sprays if alert.ip}
    by_address: dict[str, list[Login]] = defaultdict(list)
    for login in logins:
        if login.ip in attack_ips:
            by_address[login.ip].append(login)
    peaks = [peak_emails(address_logins) for address_logins in by_address.values()]
    return WeekResult(
        start=start,
        logins=len(logins),
        failed=sum(not login.success for login in logins),
        attack_ips=len(attack_ips),
        attack_peak=max(peaks, default=0),
        attack_ips_at_threshold=sum(peak >= threshold for peak in peaks),
        flagged_ips=len(flagged),
        flagged_attack_ips=len(flagged & known),
        alerts=len(sprays),
        alerts_on_attack_ips=sum(alert.ip in known for alert in sprays),
        skipped=skipped,
        lockout=replay_lockout(logins),
    )


# The run


@dataclass
class Results:
    seed: int
    revision: str
    plan: Plan
    accounts: AccountResult
    weeks: list[WeekResult]
    started_at: datetime
    seconds: float


def ingest(api: SentinelCore, logins: list[Login], shift: timedelta) -> int:
    """Reports `logins`, oldest first; returns how many were skipped."""
    events = [event_of(login, shift) for login in logins]
    api.ingest([event for event in events if event is not None])
    return sum(event is None for event in events)


def run_experiment(
    api: SentinelCore,
    db: Session,
    name: str,
    logins: list[Login],
    users: set[int] | None,
    now: datetime,
) -> tuple[int, timedelta, int]:
    """One organization, its accounts if any, its key, its sign-ins. Returns
    the organization, the time shift and the sign-ins skipped."""
    slug = name.lower().replace(" ", "-")
    organization_id = api.create_organization(name, slug)
    if users:
        create_accounts(db, organization_id, users)
    api.create_api_key(organization_id, f"RBA {name}", "rba", 30)
    shift = shift_to_now(logins[-1].at, now) if logins else timedelta()
    return organization_id, shift, ingest(api, logins, shift)


def evaluate(
    api: SentinelCore, db: Session, data: Path, args: argparse.Namespace
) -> Results:
    started = datetime.now(UTC)
    chosen = plan(read_logins(data), data_end(data), args.users, args.weeks, args.seed)
    accounts, weeks = collect(read_logins(data), chosen)
    print(
        f"Plan: {len(chosen.users)} users ({len(chosen.takeover_users)} with a "
        f"takeover), {len(accounts)} sign-ins; {len(weeks)} weeks, "
        f"{sum(map(len, weeks))} sign-ins",
        flush=True,
    )

    organization, shift, skipped = run_experiment(
        api, db, "RBA accounts", accounts, chosen.users, datetime.now(UTC)
    )
    account_result = measure_accounts(
        accounts, alerts_of(db, organization), shift, chosen, skipped
    )
    week_results = []
    for index, (start, week) in enumerate(zip(chosen.weeks, weeks, strict=True)):
        organization, shift, skipped = run_experiment(
            api, db, f"RBA week {index + 1}", week, None, datetime.now(UTC)
        )
        week_results.append(
            measure_week(start, week, alerts_of(db, organization), skipped)
        )
    return Results(
        seed=args.seed,
        revision=args.revision,
        plan=chosen,
        accounts=account_result,
        weeks=week_results,
        started_at=started,
        seconds=(datetime.now(UTC) - started).total_seconds(),
    )


# The report


def percent(rate: Rate) -> str:
    if rate.value is None or rate.interval is None:
        return "—"
    low, high = rate.interval
    return f"{rate.hits}/{rate.total} ({rate.value:.1%}; 95% CI {low:.1%}–{high:.1%})"


def to_json(results: Results) -> str:
    def rate(value: Rate) -> dict:
        return {
            "hits": value.hits,
            "total": value.total,
            "value": value.value,
            "interval": value.interval,
        }

    accounts = results.accounts
    return json.dumps(
        {
            "dataset": DATASET,
            "seed": results.seed,
            "revision": results.revision,
            "started_at": results.started_at.isoformat(),
            "seconds": round(results.seconds),
            "settings": thresholds(),
            "window": [results.plan.start.isoformat(), results.plan.end.isoformat()],
            "population_by_sign_ins": results.plan.population,
            "accounts": {
                **asdict(accounts),
                "recall": rate(accounts.recall),
                "recall_eligible": rate(accounts.recall_eligible),
                "recall_users": rate(accounts.recall_users),
                "precision": rate(accounts.precision),
                "false_alarms_per_1000": accounts.false_alarms_per_thousand,
                "dormant_per_1000": accounts.dormant_per_thousand,
            },
            "weeks": [
                {
                    **{k: v for k, v in asdict(week).items() if k != "start"},
                    "start": week.start.isoformat(),
                    "recall": rate(week.recall),
                    "precision": rate(week.precision),
                    "false_alarms_per_1000": week.false_alarms_per_thousand,
                }
                for week in results.weeks
            ],
        },
        indent=2,
    )


def thresholds() -> dict[str, int]:
    return {
        "detection_spray_min_accounts": settings.detection_spray_min_accounts,
        "detection_spray_window_minutes": settings.detection_spray_window_minutes,
        "detection_unfamiliar_lookback_days": (
            settings.detection_unfamiliar_lookback_days
        ),
        "detection_unfamiliar_min_sign_ins": settings.detection_unfamiliar_min_sign_ins,
        "detection_dormant_days": settings.detection_dormant_days,
        "login_max_failed_attempts": settings.login_max_failed_attempts,
        "login_failure_window_minutes": settings.login_failure_window_minutes,
        "login_lockout_minutes": settings.login_lockout_minutes,
    }


def to_markdown(results: Results) -> str:
    a = results.accounts
    lines = [
        "# Independent evaluation on the RBA login data set",
        "",
        f"Generated by `make evaluate-rba` (seed {results.seed}, commit "
        f"`{results.revision}`) on {results.started_at:%Y-%m-%d}, in "
        f"{results.seconds / 60:.0f} minutes. The method is in this file's "
        "last section and in `backend/simulator/rba.py`.",
        "",
        "Data: *Login Data Set for Risk-Based Authentication*, S. Wiefling, "
        "P. R. Jørgensen, S. Thunem and L. Lo Iacono, 2022, "
        "[DOI 10.5281/zenodo.6782155](https://doi.org/10.5281/zenodo.6782155), "
        "licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). "
        "It was synthesized from a real service's sign-ins; addresses, user "
        "agents and times were generated with the real distributions. The "
        "sign-ins below are a sample of it, with their times moved.",
        "",
        "B2, the Freeman et al. risk score, and the rules under other "
        "thresholds, on this same sample: `independent-rba-baselines.md` "
        "(`make evaluate-rba-offline`).",
        "",
        "## A. Accounts: unfamiliar network and device (T1078)",
        "",
        f"{a.users} users ({a.takeover_users} with a confirmed takeover in the "
        f"window; {a.takeover_users_before_start} more had theirs only before "
        f"it), {a.logins} sign-ins, {a.successful} of them successful.",
        "",
        "| Measure | Result |",
        "| --- | --- |",
        *(
            f"| {measure} | {value} |"
            for measure, value in (
                (
                    "Takeover sign-ins flagged (the successful ones: the rule "
                    "judges only those)",
                    percent(a.recall),
                ),
                (
                    "… of those with enough history for the rule to compare",
                    percent(a.recall_eligible),
                ),
                (
                    "Users with a takeover flagged at least once",
                    percent(a.recall_users),
                ),
                ("Alerts that point at a takeover", percent(a.precision)),
                (
                    "False alarms per 1,000 sign-ins",
                    f"{a.false_alarms_per_thousand:.2f}",
                ),
                (
                    "Dormant account alerts per 1,000 sign-ins (no label to "
                    "judge them)",
                    f"{a.dormant_per_thousand:.2f}",
                ),
            )
        ),
        "",
        f"Of the {a.takeover_logins} takeover sign-ins, {a.takeover_successful} "
        f"succeeded, and {a.takeover_eligible} came after at least "
        f"{settings.detection_unfamiliar_min_sign_ins} successful sign-ins in "
        f"the {settings.detection_unfamiliar_lookback_days} days before.",
        "",
        "## B. Addresses: password spray (T1110.003) and B1, lockout",
        "",
        "An address counts as an attacker when the data marks it so and it "
        "failed at least once in the week. The label means the address is on "
        "a list of known attackers, not that it sprayed passwords here, so the "
        "recall below is a lower bound.",
        "",
        "| Week | Sign-ins | Attacker addresses | Most emails one failed on "
        f"in {settings.detection_spray_window_minutes} min | Flagged (recall) "
        "| Flags on attackers (precision) | False alarms / 1,000 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for week in results.weeks:
        lines.append(
            f"| {week.start:%Y-%m-%d} | {week.logins} | {week.attack_ips} | "
            f"{week.attack_peak} ({week.attack_ips_at_threshold} at the "
            f"threshold of {settings.detection_spray_min_accounts}) | "
            f"{percent(week.recall)} | {percent(week.precision)} | "
            f"{week.false_alarms_per_thousand:.2f} |"
        )
    lines += [
        "",
        "The fourth column is what the rule compares with its threshold. When "
        "no attacker address reaches it, the data holds no password spray of "
        "the shape the rule looks for, and a recall of zero says that, not "
        "that sprays of that shape pass: the attackers here try a few emails "
        "each, slowly, as in the simulator's `slow-spray` variant.",
    ]
    lines += [
        "",
        "B1 is this application's own lockout, replayed on the same sign-ins: "
        f"{settings.login_max_failed_attempts} failures within "
        f"{settings.login_failure_window_minutes} minutes lock the email for "
        f"{settings.login_lockout_minutes}. The detection rules only alert, so "
        "they deny no one; the lockout denies attackers and legitimate users "
        "alike. Legitimate here means a sign-in that would have succeeded, from "
        "an address not marked as an attacker, and not a takeover.",
        "",
        "| Week | Lockouts | Attacker attempts denied "
        "| Legitimate sign-ins denied | Legitimate users denied |",
        "| --- | --- | --- | --- | --- |",
    ]
    for week in results.weeks:
        lock = week.lockout
        lines.append(
            f"| {week.start:%Y-%m-%d} | {lock.lockouts} | "
            f"{percent(Rate(lock.attack_denied, lock.attack_attempts))} | "
            f"{percent(Rate(lock.legitimate_denied, lock.legitimate_attempts))} | "
            f"{lock.legitimate_users_denied} |"
        )
    lines += [
        "",
        "## Method",
        "",
        f"- **Window.** The last {HISTORY.days} days of the data "
        f"({results.plan.start:%Y-%m-%d} to {results.plan.end:%Y-%m-%d}): "
        "ingestion refuses events more than a year old.",
        "- **Sample (A).** Every user with a confirmed takeover in the window, "
        "and ordinary users drawn from each group by number of sign-ins "
        f"({', '.join(STRATA_LABELS)}) in proportion to the data's: "
        + ", ".join(f"{k}: {v}" for k, v in results.plan.population.items())
        + " users. The sampled users become accounts of one organization.",
        "- **Weeks (B).** Whole weeks drawn at random in the window, not "
        "overlapping, every sign-in included, each in its own organization, "
        "with no accounts: the spray rule needs only the emails.",
        "- **Replay.** Each experiment's times are moved together so that it "
        "ends an hour before the run, keeping their order and spacing; sign-ins "
        "go through the ingestion API in batches, oldest first, with the "
        "server's ingestion rate limit raised for the run. Sign-ins with an "
        f"invalid address were skipped (A: {a.skipped}; weeks: "
        f"{', '.join(str(week.skipped) for week in results.weeks)}).",
        "- **Thresholds.** The application's settings, never fitted to this "
        "data: " + ", ".join(f"`{k}` {v}" for k, v in thresholds().items()) + ".",
        "- **Intervals.** 95% Wilson score intervals.",
        "- **What the synthesis changes.** The data set's addresses were "
        "generated anew for each distinct real one, so two addresses of one "
        "real network rarely share a /24 here. The T1078 rule treats a /24 as "
        "a familiar network; on this data it mostly recognises exact "
        "addresses only, which raises its false alarms. Its times contain "
        "randomness too, which may spread out bursts.",
        "- **Not measured here.** Brute force (it watches only this "
        "application's own sign-ins), password spray across organizations "
        "(the data has one service) and privileged roles (no such events): "
        "see the simulator's report, `report.md`. Time to detect is measured "
        "there too: these times are partly random.",
        "",
    ]
    return "\n".join(lines)


STRATA_LABELS = [label(index) for index in range(len(STRATA))]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m simulator.rba",
        description="Measure the detection rules on the RBA login data set.",
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--owner-email", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--users", type=int, default=20_000)
    parser.add_argument("--weeks", type=int, default=3)
    parser.add_argument("--revision", default=os.environ.get("REVISION", "unknown"))
    parser.add_argument("--out", type=Path, default=Path("../docs/evaluation"))
    parser.add_argument(
        "--database-url",
        default=os.environ.get("MIGRATIONS_DATABASE_URL"),
        help=f"The {EVAL_DATABASE} database, as the owner of its tables.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    host = urlsplit(args.base_url).hostname
    if host not in LOCAL_HOSTS:
        print(f"Refusing to fill {host}: the evaluation runs locally.", file=sys.stderr)
        return 2
    if (
        args.database_url is None
        or make_url(args.database_url).database != EVAL_DATABASE
    ):
        print(
            f"Refusing to run: the database must be {EVAL_DATABASE}, since "
            "accounts are written to it directly.",
            file=sys.stderr,
        )
        return 2
    password = os.environ.get("SENTINELCORE_OWNER_PASSWORD")
    if not password:
        print("Set SENTINELCORE_OWNER_PASSWORD.", file=sys.stderr)
        return 2

    engine = create_engine(args.database_url)
    try:
        with (
            httpx.Client(base_url=args.base_url, timeout=300) as http,
            Session(engine) as db,
        ):
            api = SentinelCore(http)
            api.log_in(args.owner_email, password)
            results = evaluate(api, db, args.data, args)
    except (SimulatorError, httpx.HTTPError) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "independent-rba.md").write_text(to_markdown(results))
    (args.out / "independent-rba.json").write_text(to_json(results) + "\n")
    print(f"Written to {args.out}/independent-rba.md and .json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
