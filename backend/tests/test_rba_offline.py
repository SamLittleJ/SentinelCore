import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

import simulator.client
from app.models.security_event import SecurityEventType
from simulator.client import SentinelCore
from simulator.freeman import Scored
from simulator.rba import Alert, alerts_of, email_of, run_experiment, to_millisecond
from simulator.rba_offline import (
    Point,
    area,
    curve,
    detected_at,
    differences,
    events_of,
    false_alarms_at,
    replay_dormant,
    replay_spray,
    replay_unfamiliar,
    rule_point,
)
from tests.test_rba import T0, api, login  # noqa: F401

HOME = "198.51.100.7"
LAPTOP = "Mozilla/5.0 (X11; Linux x86_64) Firefox/120.0"
PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1"
DAY = 24 * 60


def keys(alerts):
    return sorted((a.event_type, a.email, a.ip, to_millisecond(a.at)) for a in alerts)


# The replay against the API


def test_the_replay_raises_the_alerts_the_api_raises(
    api: SentinelCore,  # noqa: F811
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Small batches, so that sign-ins at one moment fall on both sides of a
    # batch's end.
    monkeypatch.setattr(simulator.client, "INGEST_BATCH", 4)
    logins = [
        # User 1: a habit, then a new network and device, then a new network
        # on the old device, then back after 100 days.
        *[login(day * DAY, ip=HOME, agent=LAPTOP) for day in range(4)],
        login(5 * DAY, ip="203.0.113.50", agent=PHONE, takeover=True),
        login(6 * DAY, ip="192.0.2.80", agent=LAPTOP),
        login(106 * DAY, ip=HOME, agent=LAPTOP),
        # A spray from one address: 14 emails, several at the same moment,
        # then 10 more, which raise a second alert.
        *[
            login(
                200 * DAY + minute // 3,
                user=100 + minute,
                ip="203.0.113.9",
                success=False,
            )
            for minute in range(14)
        ],
        *[
            login(
                200 * DAY + 10 + minute,
                user=200 + minute,
                ip="203.0.113.9",
                success=False,
            )
            for minute in range(10)
        ],
        # Not an address: skipped by both.
        login(201 * DAY, ip="not an address", success=False),
    ]
    logins.sort(key=lambda item: item.at)

    organization, shift, skipped = run_experiment(
        api, db_session, "RBA replay test", logins, {1}, datetime.now(UTC)
    )
    from_api = [
        replace(alert, at=alert.at - shift)
        for alert in alerts_of(db_session, organization)
    ]
    events = events_of(logins)
    replayed = replay_unfamiliar(events) + replay_dormant(events) + replay_spray(events)

    assert skipped == len(logins) - len(events) == 1
    assert keys(replayed) == keys(from_api)
    assert {a.event_type for a in replayed} == {
        SecurityEventType.UNFAMILIAR_SIGN_IN,
        SecurityEventType.DORMANT_ACCOUNT_LOGIN,
        SecurityEventType.PASSWORD_SPRAY_DETECTED,
    }
    assert (
        sum(a.event_type == SecurityEventType.PASSWORD_SPRAY_DETECTED for a in replayed)
        == 2
    )


# The rules, replayed


def habit(days: int = 4) -> list:
    return [login(day * DAY, ip=HOME, agent=LAPTOP) for day in range(days)]


def test_a_new_network_and_device_alert_and_either_alone_does_not() -> None:
    logins = [
        *habit(),
        login(5 * DAY, ip="203.0.113.50", agent=PHONE),
        login(6 * DAY, ip="198.51.100.99", agent=PHONE),  # same /24
        login(7 * DAY, ip="192.0.2.80", agent=LAPTOP),  # known device
    ]
    events = events_of(logins)

    assert [a.ip for a in replay_unfamiliar(events)] == ["203.0.113.50"]
    # Without the device, a new /24 is enough: twice, the second network
    # being new too.
    assert [a.ip for a in replay_unfamiliar(events, device=False)] == [
        "203.0.113.50",
        "192.0.2.80",
    ]
    # By exact address, the same /24 is a new network as well.
    assert [a.ip for a in replay_unfamiliar(events, "address", device=False)] == [
        "203.0.113.50",
        "198.51.100.99",
        "192.0.2.80",
    ]


def test_by_asn_a_new_address_of_a_known_asn_is_familiar() -> None:
    logins = [
        replace(entry, asn="64500")
        for entry in [*habit(), login(5 * DAY, ip="203.0.113.50", agent=PHONE)]
    ]
    events = events_of(logins)

    assert replay_unfamiliar(events, "ASN") == []
    assert len(replay_unfamiliar(events, "/24")) == 1


def test_the_rule_needs_enough_sign_ins_within_its_lookback() -> None:
    new = login(5 * DAY, ip="203.0.113.50", agent=PHONE)
    # Two sign-ins, under the minimum of three.
    assert replay_unfamiliar(events_of([*habit(2), new])) == []
    assert len(replay_unfamiliar(events_of([*habit(2), new]), min_sign_ins=2)) == 1
    # Four, but out of a three-day lookback.
    assert replay_unfamiliar(events_of([*habit(), new]), lookback_days=3) == []


def test_sign_ins_at_one_moment_do_not_see_each_other() -> None:
    logins = [
        *habit(2),
        login(3 * DAY, ip=HOME, agent=LAPTOP),
        login(3 * DAY, ip="203.0.113.50", agent=PHONE),
    ]
    # The third habit is at the new sign-in's moment: only two are before it.
    assert replay_unfamiliar(events_of(logins)) == []


def test_a_sign_in_without_a_user_agent_is_neither_judged_nor_a_habit() -> None:
    logins = [
        *habit(3),
        login(4 * DAY, agent=""),
        login(5 * DAY, ip="203.0.113.50", agent=""),
    ]
    assert replay_unfamiliar(events_of(logins)) == []


def test_dormant_counts_from_the_previous_success_never_the_first() -> None:
    logins = [
        login(0),
        login(1, success=False),
        login(90 * DAY),  # exactly 90 days after the first success
        login(90 * DAY),  # the same moment: its previous is still the first
        login(100 * DAY),
    ]
    alerts = replay_dormant(events_of(logins))

    assert [a.at for a in alerts] == [T0 + timedelta(days=90)] * 2
    assert replay_dormant(events_of(logins), days=10) != alerts


def failures(
    minutes: list[float], ip: str = "203.0.113.9", first_user: int = 100
) -> list:
    return [
        login(minute, user=first_user + index, ip=ip, success=False)
        for index, minute in enumerate(minutes)
    ]


def test_a_spray_alerts_at_the_threshold_and_again_only_after_as_many_new() -> None:
    logins = failures([float(m) for m in range(25)])
    alerts = replay_spray(events_of(logins))

    assert [a.at for a in alerts] == [
        T0 + timedelta(minutes=9),
        T0 + timedelta(minutes=19),
    ]
    assert len(replay_spray(events_of(logins), min_accounts=5)) == 5


def test_a_spray_counts_only_within_its_window() -> None:
    # Ten emails, but spread over more than fifteen minutes.
    logins = failures([2.0 * m for m in range(10)])
    assert replay_spray(events_of(logins)) == []
    assert len(replay_spray(events_of(logins), window_minutes=20)) == 1


def test_a_spray_sees_every_failure_of_its_moment() -> None:
    # Ten emails at one moment: the first failure already counts all ten.
    alerts = replay_spray(events_of(failures([0.0] * 10)))
    assert [a.at for a in alerts] == [T0]


def test_differences_name_what_changed() -> None:
    expected = {
        "accounts": {"alerts": 3, "recall": {"hits": 1}},
        "weeks": [{"alerts": 0}],
    }
    actual = {
        "accounts": {"alerts": 3, "recall": {"hits": 2}},
        "weeks": [{"alerts": 1}],
    }

    assert differences(expected, expected) == []
    assert differences(expected, actual) == [
        ".accounts.recall.hits: 1 != 2",
        ".weeks[0].alerts: 0 != 1",
    ]


# B2 against the rule


def scored(
    score: float, takeover: bool, eligible: bool = True, user: int = 1, minute: int = 0
) -> Scored:
    return Scored(
        user=user,
        at=T0 + timedelta(minutes=minute),
        takeover=takeover,
        eligible=eligible,
        scores={("interpolation", 90): score},
        parts=None,
    )


KEY = ("interpolation", 90)


def test_the_curve_runs_from_flagging_nothing_to_flagging_everything() -> None:
    entries = [scored(3, True), scored(2, False), scored(1, True), scored(0, False)]
    points = curve(entries, KEY, eligible=False)

    assert [(p.detected.hits, p.false_alarms.hits) for p in points] == [
        (0, 0),
        (1, 0),
        (1, 1),
        (2, 1),
        (2, 2),
    ]
    assert area(points) == pytest.approx(0.75)


def test_the_area_is_one_when_separated_and_a_half_when_tied() -> None:
    separated = [scored(2, True), scored(1, False)]
    tied = [scored(1, True), scored(1, False)]
    assert area(curve(separated, KEY, eligible=False)) == 1
    assert area(curve(tied, KEY, eligible=False)) == 0.5


def test_no_history_scores_highest_and_eligible_keeps_the_rules_subset() -> None:
    entries = [
        scored(math.inf, False, eligible=False),
        scored(1, True),
        scored(0, False),
    ]
    with_history = curve(entries, KEY, eligible=True)
    everything = curve(entries, KEY, eligible=False)

    assert with_history[-1].false_alarms.total == 1
    assert everything[1].false_alarms.hits == 1  # the infinite score first


def test_operating_points_pick_the_best_trade_within_the_limit() -> None:
    entries = [scored(3, True), scored(2, False), scored(1, True), scored(0, False)]
    points = curve(entries, KEY, eligible=False)

    best = detected_at(points, 0.5)
    assert best is not None
    assert (best.detected.hits, best.false_alarms.hits) == (2, 1)
    cheapest = false_alarms_at(points, 0.5)
    assert cheapest is not None
    assert (cheapest.detected.hits, cheapest.false_alarms.hits) == (1, 0)
    assert isinstance(false_alarms_at(points, 1.0), Point)


def test_the_rule_is_placed_on_the_same_sign_ins() -> None:
    entries = [
        scored(0, True, minute=1),
        scored(0, False, minute=2),
        scored(0, False, minute=3, eligible=False),
    ]
    alerts = [
        Alert(
            SecurityEventType.UNFAMILIAR_SIGN_IN,
            email_of(1),
            "203.0.113.50",
            T0 + timedelta(minutes=m),
        )
        for m in (1, 3)
    ]
    rule = rule_point(entries, alerts, eligible=False)
    assert (rule.detected.hits, rule.detected.total) == (1, 1)
    assert (rule.false_alarms.hits, rule.false_alarms.total) == (1, 2)
    eligible = rule_point(entries, alerts, eligible=True)
    assert (eligible.false_alarms.hits, eligible.false_alarms.total) == (0, 1)
