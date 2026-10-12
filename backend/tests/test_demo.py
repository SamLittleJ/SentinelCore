import random
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.models.invitation import Invitation
from app.models.security_event import (
    DETECTION_SOURCE,
    SecurityEvent,
    SecurityEventType,
)
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.user_service import create_owner
from simulator.attacks import plan_attacks
from simulator.client import SentinelCore
from simulator.demo import (
    DETECTION_DELAY,
    HISTORY_DAYS,
    JITTER,
    TODAY,
    WINDOWS,
    main,
    place_alerts_at_event_time,
    place_in_history,
    seed_demo,
)
from simulator.population import build_organization
from tests.conftest import rewriting_history

OWNER_EMAIL = "owner@sim.example.com"
OWNER_PASSWORD = "owner-password-1"
NOW = datetime(2026, 10, 11, 15, 30, tzinfo=UTC)
MIDNIGHT = NOW.replace(hour=0, minute=0, second=0, microsecond=0)


def demo_attacks(seed: int):
    rng = random.Random(seed)
    organization = build_organization(rng, NOW, "", HISTORY_DAYS)
    user_ids = {person.email: n for n, person in enumerate(organization.people)}
    attacks = plan_attacks(rng, NOW, organization, user_ids)
    return [
        place_in_history(attack, rng, MIDNIGHT)
        for attack in attacks
        if attack.variant in WINDOWS
    ]


# Placing attacks in the history


def test_each_attack_starts_on_a_day_of_its_window() -> None:
    for attack in demo_attacks(seed=3):
        low, high = WINDOWS[attack.variant]
        first = attack.steps[0].sign_in
        last = attack.steps[-1].sign_in
        assert first is not None and last is not None
        assert MIDNIGHT - timedelta(days=high) <= first.occurred_at
        assert first.occurred_at < MIDNIGHT - timedelta(days=low - 1)
        assert last.occurred_at < MIDNIGHT


def test_a_burst_keeps_its_shape_with_a_little_drift() -> None:
    sprays = [attack for attack in demo_attacks(seed=3) if attack.variant == "spray"]
    gaps = [
        (later.sign_in.occurred_at - earlier.sign_in.occurred_at).total_seconds()
        for attack in sprays
        for earlier, later in zip(attack.steps, attack.steps[1:], strict=False)
        if earlier.sign_in is not None and later.sign_in is not None
    ]
    assert min(gaps) >= 30 * JITTER[0]
    assert max(gaps) <= 30 * JITTER[1]
    # Not the simulator's fixed 30 seconds any more.
    assert len(set(gaps)) > len(gaps) // 2


def test_attacks_are_spread_over_the_history() -> None:
    days = {
        (MIDNIGHT - attack.steps[0].sign_in.occurred_at).days
        for attack in demo_attacks(seed=3)
        if attack.steps[0].sign_in is not None
    }
    assert len(days) >= 15
    assert max(days) > 45


def test_a_seed_gives_the_same_history() -> None:
    def times(seed: int) -> list[datetime]:
        return [
            step.sign_in.occurred_at
            for attack in demo_attacks(seed)
            for step in attack.steps
            if step.sign_in is not None
        ]

    assert times(5) == times(5)
    assert times(5) != times(6)


def test_the_demo_routine_reaches_this_morning() -> None:
    def today(through_now: bool) -> list[datetime]:
        organization = build_organization(
            random.Random(3), NOW, "", HISTORY_DAYS, through_now=through_now
        )
        return [
            sign_in.occurred_at
            for sign_in in organization.sign_ins
            if sign_in.occurred_at >= MIDNIGHT
        ]

    # 15:30 on a Sunday: no office, but some people sign in from home.
    assert today(through_now=True)
    assert all(moment < NOW for moment in today(through_now=True))
    # The simulator's own history still ends the day before.
    assert today(through_now=False) == []


# The whole demo, in-process


@pytest.fixture()
def operators(
    client: TestClient, db_session: Session
) -> tuple[SentinelCore, SentinelCore, SentinelCore]:
    create_owner(
        db_session,
        UserCreate(username="owner", email=OWNER_EMAIL, password=OWNER_PASSWORD),
    )
    owner, admin, analyst = (SentinelCore(client) for _ in range(3))
    owner.log_in(OWNER_EMAIL, OWNER_PASSWORD)
    return owner, admin, analyst


def test_the_demo_looks_like_ninety_days_watched_live(
    operators: tuple[SentinelCore, SentinelCore, SentinelCore],
    db_session: Session,
) -> None:
    # A workday afternoon in the past, so the morning's routine is certain.
    day = datetime.now(UTC) - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    afternoon = day.replace(hour=15, minute=30, second=0, microsecond=0)
    seeded = seed_demo(*operators, seed=7, now=afternoon)
    # The demo moves alerts as the owner of the tables: the API may not.
    with rewriting_history(db_session) as owner:
        moved = place_alerts_at_event_time(owner, random.Random(7), seeded.started_at)
    started = seeded.started_at
    midnight = started.replace(hour=0, minute=0, second=0, microsecond=0)

    # The routine reaches that morning: the office signs in.
    morning = db_session.scalars(
        select(SecurityEvent).where(
            SecurityEvent.source == "vpn",
            SecurityEvent.created_at >= midnight,
            SecurityEvent.created_at < started,
        )
    ).all()
    assert len(morning) >= 20

    alerts = db_session.scalars(
        select(SecurityEvent).where(SecurityEvent.source == DETECTION_SOURCE)
    ).all()
    # Every alert carries the time of its event.
    event_times = {alert.id: alert.occurred_at for alert in alerts}
    assert None not in event_times.values()
    history = [alert for alert in alerts if (alert.occurred_at or started) < started]
    today = [alert for alert in alerts if (alert.occurred_at or started) >= started]
    assert moved == len(history)

    # Every attack the rules are built for was caught where it was placed,
    # besides the routine's known false positives.
    found = Counter(alert.event_type.value for alert in history)
    assert found["password_spray_detected"] >= 5
    assert found["dormant_account_login"] >= 5
    assert found["unfamiliar_sign_in"] >= 5

    # Each alert from the history sits seconds after its event, before today.
    for alert in history:
        delay = (alert.created_at - (alert.occurred_at or started)).total_seconds()
        assert DETECTION_DELAY[0] <= delay <= DETECTION_DELAY[1]
        assert alert.created_at < midnight
    assert len({alert.created_at.date() for alert in history}) >= 10

    # Today: the live attacks, two operators and a promotion to roles that
    # reach every account.
    found_today = Counter(alert.event_type.value for alert in today)
    assert found_today["privileged_role_granted"] == TODAY["privileged-role"] + 3
    # The lockout raises it, from this application's own sign-ins.
    brute_force = db_session.scalars(
        select(SecurityEvent).where(
            SecurityEvent.event_type == SecurityEventType.BRUTE_FORCE_DETECTED
        )
    ).all()
    assert len(brute_force) == TODAY["brute-force"]
    assert all(event.created_at >= started for event in brute_force)

    # The operators' response.
    users = db_session.scalars(select(User)).all()
    assert sum(not user.is_active for user in users) == 2
    assert sum(user.locked_until is not None for user in users) == 1
    invitations = db_session.scalars(select(Invitation)).all()
    open_ = [i for i in invitations if i.accepted_at is None and i.revoked_at is None]
    assert len(open_) == 3
    assert sum(i.revoked_at is not None for i in invitations) == 1
    keys = db_session.scalars(select(ApiKey)).all()
    assert sorted((key.source, key.revoked_at is None) for key in keys) == [
        ("idp", False),
        ("vpn", True),
    ]


# The command line


def test_refuses_any_database_but_the_demos(capsys: pytest.CaptureFixture) -> None:
    code = main(
        [
            "--owner-email",
            OWNER_EMAIL,
            "--database-url",
            "postgresql+psycopg://user:pw@localhost:5432/sentinelcore",
        ]
    )
    assert code == 2
    assert "must be sentinelcore_demo" in capsys.readouterr().err


def test_refuses_a_remote_host(capsys: pytest.CaptureFixture) -> None:
    code = main(
        [
            "--owner-email",
            OWNER_EMAIL,
            "--base-url",
            "https://sentinel.example.com",
            "--database-url",
            "postgresql+psycopg://user:pw@localhost:5432/sentinelcore_demo",
        ]
    )
    assert code == 2
    assert "runs locally" in capsys.readouterr().err


def test_runs_on_its_own_with_every_table_it_updates_resolved() -> None:
    """The tests load the whole app; the command line loads only this module."""
    check = (
        "import simulator.demo\n"
        "from app.models.security_event import SecurityEvent\n"
        "for key in SecurityEvent.__table__.foreign_keys:\n"
        "    key.column\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", check], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
