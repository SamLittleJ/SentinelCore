"""Command line: python -m simulator.demo --owner-email owner@sim.example.com

Fills the demo database with ninety days of three synthetic organizations,
through the API of a SentinelCore running on it:

1. Acme, the attacked one: its people join by invitation, and two operators
   join them, an admin and an analyst. Globex and Initech, smaller, have
   people who only keep to their routine, and an admin each.
2. Each organization's routine sign-ins, and the simulator's attacks on
   Acme spread across the ninety days, are reported through its own key,
   oldest first, as a log shipper sends them. Each detection rule judges an
   event against the events before its own time, whatever the order they
   arrive in.
3. Today's work: attacks on Acme that can only happen live (brute force
   against this application's own sign-in, an admin role granted), the
   operators' response to what was detected, a few sign-ins failing on
   emails no account has, which belong to the platform, a password spray
   split across Acme, Globex and such emails, which only the platform sees,
   and Initech suspended by the owner.
4. Every alert raised from the history is then placed at the moment its
   event happened, plus a few seconds, as if SentinelCore had watched the
   ninety days live. This step writes to the database directly, so it
   refuses any database but the demo's.

Everything is synthetic and drawn from one seed. `make demo` runs this on the
`sentinelcore_demo` database it has just created. The owner's password is
read from SENTINELCORE_OWNER_PASSWORD, or asked for. With --accounts-dir, the
admins' passwords are written there, one file each, readable by the user
alone, to sign in as them during a presentation.
"""

import argparse
import getpass
import os
import random
import secrets
import sys
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

# Every model, as migrations/env.py loads them: run on its own, this module
# must still resolve the foreign keys of the alerts it updates.
from app.models import (  # noqa: F401
    api_key,
    audit_log,
    invitation,
    security_event,
    user,
    user_session,
)
from app.models.security_event import DETECTION_SOURCE, SecurityEvent
from simulator.__main__ import LOCAL_HOSTS, loopback_senders
from simulator.attacks import Attack, plan_attacks
from simulator.client import SentinelCore, SimulatorError
from simulator.population import (
    Organization,
    build_organization,
    build_quiet_organization,
)

DEMO_DATABASE = "sentinelcore_demo"
HISTORY_DAYS = 90

# Days before the run within which each backfilled attack may start, so that
# what makes it an attack still holds on that day:
# - a dormant account was last used 100 days before the run, so it counts as
#   dormant (over 90 days) only in the last ten days;
# - an idle account was last used 85 days before the run and must keep fewer
#   than three sign-ins in the 90 days before the attack to stay unjudged;
# - a stolen password used from a new place needs a few weeks of the
#   victim's habits to stand out.
WINDOWS: dict[str, tuple[int, int]] = {
    "spray": (1, HISTORY_DAYS - 1),
    "slow-spray": (1, HISTORY_DAYS - 1),
    "distributed-spray": (1, HISTORY_DAYS - 1),
    "unfamiliar": (2, HISTORY_DAYS - 14),
    "copied-user-agent": (2, HISTORY_DAYS - 14),
    "dormant": (1, 9),
    "idle-account": (1, 8),
}
# A script's pace drifts a little over a network: each gap between two
# attempts is stretched or shrunk by up to this factor.
JITTER = (0.9, 1.3)
# Attacks that only happen live, and how many of each the demo plays today.
TODAY = {"brute-force": 2, "privileged-role": 1}
# From an event to its alert, as a log shipper and the pipeline take, in seconds.
DETECTION_DELAY = (2.0, 40.0)


@dataclass(frozen=True)
class Tenant:
    """One of the demo's organizations: its own email domain (reserved for
    examples, RFC 2606), office address and home networks."""

    name: str
    slug: str
    domain: str
    office_ip: str
    first_home: int


ACME = Tenant("Acme", "acme", "acme.example", "192.0.2.10", 0)
GLOBEX = Tenant("Globex", "globex", "globex.example", "192.0.2.20", 40)
INITECH = Tenant("Initech", "initech", "initech.example", "192.0.2.30", 60)
# The quiet organizations' size, besides their admin.
QUIET_PEOPLE = {GLOBEX: 12, INITECH: 6}


@dataclass(frozen=True)
class Operator:
    username: str
    email: str
    role: str


ADMIN = Operator("andreea.vasile", "andreea.vasile@acme.example", "admin")
ANALYST = Operator("tudor.ciobanu", "tudor.ciobanu@acme.example", "security_analyst")
GLOBEX_ADMIN = Operator("matei.radulescu", "matei.radulescu@globex.example", "admin")
INITECH_ADMIN = Operator("ilie.constantin", "ilie.constantin@initech.example", "admin")
# People about to join Acme, invited today.
NEW_HIRES = ("sara.neagu", "victor.oprea", "ilinca.preda")
WITHDRAWN = "temp.contractor"
# Tried today at this application's sign-in. No account has them, so the
# failures belong to the platform; too few for a password spray.
UNKNOWN_EMAILS = (
    "admin@acme-corp.example",
    "root@globex-it.example",
    "it.support@initech-mail.example",
)
# Today's spray across organizations: four people of Acme, four of Globex
# and these guesses, below each organization's spray rule, from a loopback
# address of its own so the morning's other failures do not add to it.
CROSS_SPRAY_ADDRESS = "127.0.0.11"
CROSS_SPRAY_PEOPLE = 4
CROSS_SPRAY_GUESSES = (
    "admin@globex.example",
    "it@globex.example",
    "hr@acme.example",
    "finance@acme.example",
)


@dataclass(frozen=True)
class Account:
    """An account to sign in with during a presentation."""

    file: str
    email: str
    password: str = field(repr=False)


@dataclass
class Seeded:
    started_at: datetime
    people: int
    sign_ins: int
    backfilled_attacks: int
    live_attacks: int
    # People per organization, operators included.
    organizations: dict[str, int] = field(default_factory=dict)
    accounts: list[Account] = field(default_factory=list)


def place_in_history(attack: Attack, rng: random.Random, midnight: datetime) -> Attack:
    """`attack`, moved to a random moment of a day in its window. Its burst
    keeps its shape, each gap drifting a little."""
    low, high = WINDOWS[attack.variant]
    # Starts before 23:00, so even a slow spray ends before midnight.
    current = (
        midnight
        - timedelta(days=rng.randint(low, high))
        + timedelta(seconds=rng.uniform(0, 23 * 3600))
    )
    previous = None
    steps = []
    for step in attack.steps:
        if step.sign_in is None:
            raise ValueError(f"{attack.name} has a step that is not reported")
        if previous is not None:
            current += (step.sign_in.occurred_at - previous) * rng.uniform(*JITTER)
        previous = step.sign_in.occurred_at
        steps.append(replace(step, sign_in=replace(step.sign_in, occurred_at=current)))
    return replace(attack, steps=steps)


def join(api: SentinelCore, operator: Operator, organization_id: int) -> str:
    """Brings `operator` in by invitation; returns the password chosen."""
    password = secrets.token_urlsafe(18)
    api.add_person(
        operator.username, operator.email, password, operator.role, organization_id
    )
    return password


def seed_demo(
    owner: SentinelCore,
    admin: SentinelCore,
    analyst: SentinelCore,
    seed: int,
    now: datetime | None = None,
) -> Seeded:
    """Plays the demo through the API. `owner` is signed in; `admin` and
    `analyst` are signed in once they have joined. The history ends at
    `now`, the current time unless a test sets an earlier one."""
    # Simulated behaviour, not a secret: a seed must give the same demo.
    rng = random.Random(seed)  # nosec B311
    started_at = now or datetime.now(UTC)
    midnight = started_at.replace(hour=0, minute=0, second=0, microsecond=0)
    organization = build_organization(
        rng,
        started_at,
        "",
        HISTORY_DAYS,
        through_now=True,
        domain=ACME.domain,
        office_ip=ACME.office_ip,
        first_home=ACME.first_home,
    )

    acme = owner.create_organization(ACME.name, ACME.slug)
    # The key the organization's VPN reports sign-ins with; it stays active.
    owner.create_api_key(acme, "Corporate VPN", "vpn", 365)
    user_ids = {
        person.email: owner.add_person(
            person.handle, person.email, person.password, "user", acme
        )
        for person in organization.people
    }
    admin_password = join(owner, ADMIN, acme)
    admin.log_in(ADMIN.email, admin_password)
    analyst.log_in(ANALYST.email, join(owner, ANALYST, acme))
    accounts = [Account("acme-admin.txt", ADMIN.email, admin_password)]

    backfilled: list[Attack] = []
    live: list[Attack] = []
    for attack in plan_attacks(rng, started_at, organization, user_ids):
        if attack.variant in WINDOWS:
            backfilled.append(place_in_history(attack, rng, midnight))
        elif sum(other.variant == attack.variant for other in live) < TODAY.get(
            attack.variant, 0
        ):
            live.append(attack)

    history = organization.sign_ins + [
        step.sign_in
        for attack in backfilled
        for step in attack.steps
        if step.sign_in is not None
    ]
    history.sort(key=lambda sign_in: sign_in.occurred_at)
    owner.ingest([sign_in.payload() for sign_in in history])
    people = {ACME.name: len(organization.people) + 2}

    # The quiet organizations, drawn after Acme so its history stays the
    # same for a seed. Usernames are unique across the platform.
    taken = {person.handle for person in organization.people}
    taken |= {ADMIN.username, ANALYST.username}
    quiet: dict[Tenant, int] = {}
    globex_people: list[str] = []
    for tenant, admin_of in ((GLOBEX, GLOBEX_ADMIN), (INITECH, INITECH_ADMIN)):
        quiet_organization = build_quiet_organization(
            rng,
            started_at,
            QUIET_PEOPLE[tenant],
            HISTORY_DAYS,
            through_now=True,
            domain=tenant.domain,
            office_ip=tenant.office_ip,
            first_home=tenant.first_home,
            taken=frozenset(taken),
        )
        taken |= {person.handle for person in quiet_organization.people}
        quiet[tenant] = owner.create_organization(tenant.name, tenant.slug)
        owner.create_api_key(quiet[tenant], "Corporate VPN", "vpn", 365)
        for person in quiet_organization.people:
            owner.add_person(
                person.handle, person.email, person.password, "user", quiet[tenant]
            )
        accounts.append(
            Account(
                f"{tenant.slug}-admin.txt",
                admin_of.email,
                join(owner, admin_of, quiet[tenant]),
            )
        )
        owner.ingest([sign_in.payload() for sign_in in quiet_organization.sign_ins])
        history += quiet_organization.sign_ins
        if tenant == GLOBEX:
            globex_people = [person.email for person in quiet_organization.people]
        people[tenant.name] = len(quiet_organization.people) + 1

    for attack in live:
        for step in attack.steps:
            if step.kind == "wrong_password" and step.email is not None:
                owner.sign_in_with_wrong_password(step.email)
            elif step.kind == "grant_admin" and step.user_id is not None:
                owner.grant_admin(step.user_id)
    respond(owner, admin, analyst, acme, organization, user_ids, live)

    for email in UNKNOWN_EMAILS:
        owner.sign_in_with_wrong_password(email)
    # From the owner's own address when the server is not on IPv4 loopback.
    address = CROSS_SPRAY_ADDRESS if owner.from_address is not None else None
    spray = (
        [person.email for person in organization.active[15 : 15 + CROSS_SPRAY_PEOPLE]]
        + globex_people[:CROSS_SPRAY_PEOPLE]
        + list(CROSS_SPRAY_GUESSES)
    )
    for email in rng.sample(spray, len(spray)):
        owner.sign_in_with_wrong_password(email, address)
    # Last: its members are signed out and its key refused from now on.
    owner.suspend_organization(quiet[INITECH])

    return Seeded(
        started_at=started_at,
        people=sum(people.values()),
        sign_ins=len(history),
        backfilled_attacks=len(backfilled),
        # The spray across organizations too.
        live_attacks=len(live) + 1,
        organizations=people,
        accounts=accounts,
    )


def respond(
    owner: SentinelCore,
    admin: SentinelCore,
    analyst: SentinelCore,
    acme: int,
    organization: Organization,
    user_ids: dict[str, int],
    live: list[Attack],
) -> None:
    """Today's work of the operators, after the night's alerts."""
    brute_force = next(attack for attack in live if attack.variant == "brute-force")
    (brute_forced,) = brute_force.emails
    analyst.revoke_sessions(
        user_ids[brute_forced],
        "Brute force against the account this morning; sessions closed until "
        "the owner confirms the password is safe",
    )
    unfamiliar_victim = organization.active[0]
    analyst.lock(
        user_ids[unfamiliar_victim.email],
        24,
        "Signed in from an unknown network and computer; locked while we "
        "check with the owner",
    )
    # The dormant accounts belonged to people who left: closed after the
    # attacks on them.
    for person in organization.dormant[:2]:
        admin.deactivate(user_ids[person.email])
    # A promotion, which only the owner makes: the analyst role reaches
    # every account, so it alerts.
    owner.change_role(user_ids[organization.active[19].email], "security_analyst")

    for handle in NEW_HIRES:
        admin.invite(f"{handle}@{ACME.domain}")
    withdrawn, _ = admin.invite(f"{WITHDRAWN}@{ACME.domain}")
    admin.revoke_invitation(withdrawn)

    # A key for a system that was retired.
    old_key = owner.create_api_key(acme, "Old identity provider", "idp", 30)
    owner.revoke_api_key(old_key)


def place_alerts_at_event_time(
    db: Session, rng: random.Random, before: datetime
) -> int:
    """Gives every alert raised from an event before `before` the time of
    that event plus a detection delay, as if it had been raised live.
    Returns how many alerts moved."""
    alerts = db.scalars(
        select(SecurityEvent)
        .where(
            SecurityEvent.source == DETECTION_SOURCE,
            SecurityEvent.occurred_at < before,
        )
        .order_by(SecurityEvent.id)
    ).all()
    for alert in alerts:
        if alert.occurred_at is not None:  # Always, by the query.
            alert.created_at = alert.occurred_at + timedelta(
                seconds=rng.uniform(*DETECTION_DELAY)
            )
    db.commit()
    return len(alerts)


def write_accounts(directory: Path, accounts: list[Account]) -> None:
    """One file per account in `directory`, readable by the user alone. The
    passwords are never printed."""
    for account in accounts:
        path = directory / account.file
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        # An older file keeps its mode through O_CREAT.
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as file:
            file.write(
                "SentinelCore demo account (local only)\n"
                f"email: {account.email}\n"
                f"password: {account.password}\n"
            )


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m simulator.demo",
        description="Fill the demo database with ninety days of three synthetic "
        "organizations.",
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--owner-email", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--accounts-dir",
        type=Path,
        help="Where to write the admins' passwords, one file each, mode 600.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("MIGRATIONS_DATABASE_URL")
        or os.environ.get("DATABASE_URL"),
        help=f"The {DEMO_DATABASE} database the backend runs on, as the owner "
        "of its tables, since the API's role may not move alerts; defaults to "
        "MIGRATIONS_DATABASE_URL, then DATABASE_URL.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    host = urlsplit(args.base_url).hostname
    if host not in LOCAL_HOSTS:
        print(f"Refusing to fill {host}: the demo runs locally.", file=sys.stderr)
        return 2
    if args.database_url is None or make_url(args.database_url).database != (
        DEMO_DATABASE
    ):
        print(
            f"Refusing to run: the database must be {DEMO_DATABASE}, since the "
            "demo rewrites the time of its alerts.",
            file=sys.stderr,
        )
        return 2

    password = os.environ.get("SENTINELCORE_OWNER_PASSWORD") or getpass.getpass(
        f"Password for {args.owner_email}: "
    )
    with httpx.Client(base_url=args.base_url, timeout=60) as http:
        owner = SentinelCore(http, from_address=loopback_senders(args.base_url))
        admin, analyst = SentinelCore(http), SentinelCore(http)
        try:
            owner.log_in(args.owner_email, password)
            seeded = seed_demo(owner, admin, analyst, args.seed)
        except (SimulatorError, httpx.HTTPError) as error:
            print(error, file=sys.stderr)
            return 1
        finally:
            owner.close_senders()

    engine = create_engine(args.database_url)
    try:
        with Session(engine) as db:
            # Its own generator, so the history above stays the same if this
            # step changes.
            moved = place_alerts_at_event_time(
                db,
                random.Random(args.seed),  # nosec B311
                seeded.started_at,
            )
    finally:
        engine.dispose()

    if args.accounts_dir is not None:
        write_accounts(args.accounts_dir, seeded.accounts)

    organizations = ", ".join(
        f"{name} {count}" for name, count in seeded.organizations.items()
    )
    print(
        f"Demo ready: {seeded.people} people ({organizations}; "
        f"{INITECH.name} suspended), {seeded.sign_ins} sign-ins over "
        f"{HISTORY_DAYS} days, {seeded.backfilled_attacks} attacks in the "
        f"history and {seeded.live_attacks} today, {moved} alerts placed at "
        "their event's time."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
