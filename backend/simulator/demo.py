"""Command line: python -m simulator.demo --owner-email owner@sim.example.com

Fills the demo database with ninety days of a synthetic organization, through
the API of a SentinelCore running on it:

1. Its people join by invitation, and two operators join them: an admin and
   an analyst.
2. Their routine sign-ins and the simulator's attacks, spread across the
   ninety days, are reported through ingestion oldest first, as a log
   shipper sends them. Each detection rule judges an event against the
   events before its own time, whatever the order they arrive in.
3. Today's work: attacks that can only happen live (brute force against
   this application's own sign-in, an admin role granted) and the operators'
   response to what was detected.
4. Every alert raised from the history is then placed at the moment its
   event happened, plus a few seconds, as if SentinelCore had watched the
   ninety days live. This step writes to the database directly, so it
   refuses any database but the demo's.

Everything is synthetic and drawn from one seed. `make demo` runs this on the
`sentinelcore_demo` database it has just created. The owner's password is
read from SENTINELCORE_OWNER_PASSWORD, or asked for.
"""

import argparse
import getpass
import os
import random
import secrets
import sys
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
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
from simulator.__main__ import LOCAL_HOSTS
from simulator.attacks import Attack, plan_attacks
from simulator.client import SentinelCore, SimulatorError
from simulator.population import Organization, build_organization

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
class Operator:
    username: str
    email: str
    role: str


ADMIN = Operator("andreea.vasile", "andreea.vasile@sim.example.com", "admin")
ANALYST = Operator("tudor.ciobanu", "tudor.ciobanu@sim.example.com", "security_analyst")
# People about to join, invited today.
NEW_HIRES = ("sara.neagu", "victor.oprea", "ilinca.preda")
WITHDRAWN = "temp.contractor"


@dataclass
class Seeded:
    started_at: datetime
    people: int
    sign_ins: int
    backfilled_attacks: int
    live_attacks: int


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
    """Brings `operator` in by invitation; returns the password chosen,
    which is used to sign in and then forgotten."""
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
        rng, started_at, "", HISTORY_DAYS, through_now=True
    )

    acme = owner.create_organization("Acme", "acme")
    # The key the organization's VPN reports sign-ins with; it stays active.
    owner.create_api_key(acme, "Corporate VPN", "vpn", 365)
    user_ids = {
        person.email: owner.add_person(
            person.handle, person.email, person.password, "user", acme
        )
        for person in organization.people
    }
    admin.log_in(ADMIN.email, join(owner, ADMIN, acme))
    analyst.log_in(ANALYST.email, join(owner, ANALYST, acme))

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

    for attack in live:
        for step in attack.steps:
            if step.kind == "wrong_password" and step.email is not None:
                owner.sign_in_with_wrong_password(step.email)
            elif step.kind == "grant_admin" and step.user_id is not None:
                owner.grant_admin(step.user_id)
    respond(owner, admin, analyst, acme, organization, user_ids, live)

    return Seeded(
        started_at=started_at,
        people=len(organization.people) + 2,
        sign_ins=len(history),
        backfilled_attacks=len(backfilled),
        live_attacks=len(live),
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
        admin.invite(f"{handle}@sim.example.com")
    withdrawn, _ = admin.invite(f"{WITHDRAWN}@sim.example.com")
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


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m simulator.demo",
        description="Fill the demo database with ninety days of a synthetic "
        "organization.",
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--owner-email", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help=f"The {DEMO_DATABASE} database the backend runs on; defaults to "
        "DATABASE_URL.",
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
        owner, admin, analyst = (SentinelCore(http) for _ in range(3))
        try:
            owner.log_in(args.owner_email, password)
            seeded = seed_demo(owner, admin, analyst, args.seed)
        except (SimulatorError, httpx.HTTPError) as error:
            print(error, file=sys.stderr)
            return 1

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

    print(
        f"Demo ready: {seeded.people} people, {seeded.sign_ins} sign-ins over "
        f"{HISTORY_DAYS} days, {seeded.backfilled_attacks} attacks in the "
        f"history and {seeded.live_attacks} today, {moved} alerts placed at "
        "their event's time."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
