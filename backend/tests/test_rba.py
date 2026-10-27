import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.security_event import SecurityEventType
from app.schemas.user import UserCreate
from app.services.user_service import create_owner
from simulator.client import SentinelCore
from simulator.rba import (
    HISTORY,
    WEEK,
    Alert,
    Login,
    Plan,
    Rate,
    alerts_of,
    data_end,
    draw_users,
    draw_weeks,
    eligible_takeovers,
    email_of,
    event_of,
    measure_accounts,
    measure_week,
    peak_emails,
    plan,
    replay_lockout,
    run_experiment,
    shift_to_now,
    wilson,
)

OWNER_EMAIL = "owner@example.com"
OWNER_PASSWORD = "owner-password-1"
T0 = datetime(2021, 1, 4, 9, tzinfo=UTC)
HEADER = (
    "index,Login Timestamp,User ID,Round-Trip Time [ms],IP Address,Country,Region,"
    "City,ASN,User Agent String,Browser Name and Version,OS Name and Version,"
    "Device Type,Login Successful,Is Attack IP,Is Account Takeover\n"
)


def login(
    minutes: float,
    user: int = 1,
    ip: str = "198.51.100.7",
    agent: str = "Mozilla/5.0 (X11; Linux x86_64) Firefox/120.0",
    success: bool = True,
    attack_ip: bool = False,
    takeover: bool = False,
) -> Login:
    return Login(
        at=T0 + timedelta(minutes=minutes),
        user=user,
        ip=ip,
        user_agent=agent,
        success=success,
        attack_ip=attack_ip,
        takeover=takeover,
    )


# Rates


def test_wilson_matches_known_intervals() -> None:
    low, high = wilson(30, 30) or (0, 0)
    assert round(low, 3) == 0.886
    assert high == 1.0
    low, high = wilson(5, 10) or (0, 0)
    assert (round(low, 3), round(high, 3)) == (0.237, 0.763)
    assert wilson(0, 0) is None
    assert Rate(0, 0).value is None


# Sampling


def test_users_are_drawn_in_proportion_and_the_same_for_one_seed() -> None:
    # 900 users who sign in rarely, 90 sometimes, 10 often.
    counts = {user: 1 for user in range(900)}
    counts |= {user: 20 for user in range(900, 990)}
    counts |= {user: 60 for user in range(990, 1000)}

    drawn = draw_users(counts, {0, 1}, 100, random.Random(7))

    assert drawn == draw_users(counts, {0, 1}, 100, random.Random(7))
    assert not drawn & {0, 1}
    assert sum(user < 900 for user in drawn) == 90
    assert sum(900 <= user < 990 for user in drawn) == 9
    assert sum(user >= 990 for user in drawn) == 1


def test_weeks_fall_inside_the_window_without_overlapping() -> None:
    start = T0 - HISTORY
    weeks = draw_weeks(start, T0, 3, random.Random(1))

    assert weeks == sorted(weeks)
    assert all(start <= week and week + WEEK <= T0 for week in weeks)
    assert all(b - a >= WEEK for a, b in zip(weeks, weeks[1:], strict=False))


def test_the_plan_keeps_takeovers_in_the_window_and_counts_those_before() -> None:
    end = T0 + timedelta(days=1)
    logins = [
        login(0, user=1, takeover=True),
        login(10, user=2),
        login(-(HISTORY.days + 5) * 24 * 60, user=3, takeover=True),
        login(20, user=3),
        # After the window: neither in it nor before it.
        login(2 * 24 * 60, user=4, takeover=True),
    ]

    chosen = plan(logins, end, users=10, weeks=1, seed=3)

    assert chosen.takeover_users == {1}
    assert chosen.takeover_users_before_start == 1
    assert {1, 2, 3} <= chosen.users


def test_the_end_of_the_data_is_read_from_its_last_line(tmp_path: Path) -> None:
    data = tmp_path / "rba.csv"
    data.write_text(
        HEADER
        + "0,2021-02-28 23:59:58.756,-43,,10.0.0.1,NO,-,-,1,UA,B,O,mobile,"
        + "True,False,False\n"
    )
    assert data_end(data) == datetime(2021, 2, 28, 23, 59, 58, 756001, tzinfo=UTC)


# Replaying


def test_an_event_keeps_its_order_and_skips_what_is_no_address() -> None:
    shift = shift_to_now(T0, T0 + timedelta(days=30))
    event = event_of(login(0, agent="x" * 300, success=False), shift)

    assert event is not None
    assert event["event_type"] == "login_failed"
    assert event["occurred_at"] == (T0 + timedelta(days=30, hours=-1)).isoformat()
    assert len(event["user_agent"]) == 255
    assert event["email"] == email_of(1)
    assert event_of(login(0, ip="-"), shift) is None


# B1: the lockout


def test_the_lockout_denies_whoever_comes_while_it_lasts() -> None:
    attack = [
        login(m, success=False, attack_ip=True, ip="203.0.113.9") for m in range(5)
    ]
    logins = [
        *attack,
        # The owner of the email, while the lockout lasts, then after it.
        login(6),
        login(7),
        # A wrong password from an unmarked address: not counted as legitimate.
        login(8, success=False),
        login(25),
        login(26, success=False, attack_ip=True, ip="203.0.113.9"),
    ]

    result = replay_lockout(logins)

    assert result.lockouts == 1
    assert result.legitimate_denied == 2
    assert result.legitimate_users_denied == 1
    assert result.attack_denied == 0
    assert (result.attack_attempts, result.legitimate_attempts) == (6, 3)


def test_a_success_or_a_long_pause_resets_the_failures() -> None:
    logins = [
        *[login(m, success=False) for m in range(4)],
        login(4),
        *[login(5 + m, success=False) for m in range(4)],
        *[login(30 + m, success=False) for m in range(4)],
    ]
    assert replay_lockout(logins).lockouts == 0


# Measuring


def test_takeovers_count_as_eligible_only_after_enough_history() -> None:
    logins = [
        login(0, takeover=True),
        login(10),
        login(20),
        login(30),
        login(40, takeover=True),
    ]
    assert eligible_takeovers(logins) == {(1, T0 + timedelta(minutes=40))}


def test_the_peak_counts_emails_within_the_window_only() -> None:
    # Twelve emails, one every ten minutes: at most two in any 15 minutes.
    slow = [login(10 * m, user=m, success=False) for m in range(12)]
    assert peak_emails(slow) == 2
    assert peak_emails([login(m, user=m, success=False) for m in range(12)]) == 12


def test_only_spray_alerts_flag_an_address() -> None:
    logins = [
        login(m, user=m, ip="203.0.113.9", success=False, attack_ip=True)
        for m in range(3)
    ]
    alerts = [
        Alert(SecurityEventType.UNFAMILIAR_SIGN_IN, None, "198.51.100.7", T0),
        Alert(SecurityEventType.PASSWORD_SPRAY_DETECTED, None, "203.0.113.9", T0),
    ]
    result = measure_week(T0, logins, alerts, 0)
    assert (result.flagged_ips, result.alerts) == (1, 1)


# Through the API


@pytest.fixture()
def api(client: TestClient, db_session: Session) -> SentinelCore:
    create_owner(
        db_session,
        UserCreate(username="owner", email=OWNER_EMAIL, password=OWNER_PASSWORD),
    )
    api = SentinelCore(client)
    api.log_in(OWNER_EMAIL, OWNER_PASSWORD)
    return api


def chosen(users: set[int], takeover_users: set[int]) -> Plan:
    return Plan(
        start=T0 - HISTORY,
        end=T0 + timedelta(days=1),
        users=users,
        takeover_users=takeover_users,
        takeover_users_before_start=0,
        weeks=[],
    )


def test_a_takeover_from_a_new_network_and_device_is_caught_and_matched(
    api: SentinelCore, db_session: Session
) -> None:
    habit = "Mozilla/5.0 (X11; Linux x86_64) Firefox/120.0"
    logins = [
        *[login(day * 24 * 60, ip="198.51.100.7", agent=habit) for day in range(4)],
        login(5 * 24 * 60, ip="203.0.113.50", agent="curl/8.0", takeover=True),
        # Another user, always from the same place: no alert.
        *[login(day * 24 * 60 + 1, user=2) for day in range(6)],
    ]
    logins.sort(key=lambda item: item.at)
    now = datetime.now(UTC)

    organization, shift, skipped = run_experiment(
        api, db_session, "RBA test", logins, {1, 2}, now
    )
    result = measure_accounts(
        logins, alerts_of(db_session, organization), shift, chosen({1, 2}, {1}), skipped
    )

    assert result.alerts == 1
    assert result.recall.hits == result.recall.total == 1
    assert result.precision.hits == 1
    assert result.takeover_eligible == 1
    assert result.false_alarms_per_thousand == 0


def test_a_spraying_address_is_flagged_and_a_quiet_one_is_not(
    api: SentinelCore, db_session: Session
) -> None:
    spray = [
        login(m, user=100 + m, ip="203.0.113.9", success=False, attack_ip=True)
        for m in range(12)
    ]
    # Labelled an attacker, but it fails only twice: under the threshold.
    quiet = [
        login(30 + m, user=200 + m, ip="203.0.113.10", success=False, attack_ip=True)
        for m in range(2)
    ]
    ordinary = [login(m, user=300 + m, ip=f"198.51.100.{m + 1}") for m in range(20)]
    logins = sorted([*spray, *quiet, *ordinary], key=lambda item: item.at)

    organization, _, skipped = run_experiment(
        api, db_session, "RBA week test", logins, None, datetime.now(UTC)
    )
    result = measure_week(T0, logins, alerts_of(db_session, organization), skipped)

    assert result.attack_ips == 2
    assert (result.attack_peak, result.attack_ips_at_threshold) == (12, 1)
    assert result.flagged_ips == 1
    assert (result.recall.hits, result.recall.total) == (1, 2)
    assert result.precision.value == 1
    assert result.false_alarms_per_thousand == 0
