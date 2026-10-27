import math
from dataclasses import replace
from datetime import timedelta

import pytest

from simulator.freeman import (
    BACKOFF,
    FEATURES,
    INTERPOLATION,
    UNIFORM_ATTACKER,
    Counts,
    Model,
    score_sample,
)
from tests.test_rba import T0, login

AGENT = "Mozilla/5.0 (X11; Linux x86_64) Firefox/120.0"


def sign_in(minutes: float, user: int, ip: str, asn: str = "64500", **rest):
    return replace(
        login(minutes, user=user, ip=ip, agent=AGENT, **rest),
        asn=asn,
        country="NO",
        browser="Firefox 120",
        os="Linux",
        device_type="desktop",
    )


ADDRESS = FEATURES[0]


def test_eq_8_reserves_a_share_for_the_unseen_and_eq_9_scales_by_the_group() -> None:
    counts = Counts(ADDRESS)
    for entry in (sign_in(0, 1, "a"), sign_in(1, 1, "a"), sign_in(2, 2, "b")):
        counts.add(entry)

    # Three sign-ins, two distinct values: seen 2/(3+2), unseen 1/(3+2); the
    # one ASN and country hold all three, so their level gives the same.
    assert counts.estimates(sign_in(3, 1, "a")) == pytest.approx([0.4, 0.4, 0.4])
    assert counts.estimates(sign_in(3, 1, "new")) == pytest.approx([0.2, 0.2, 0.2])
    # An ASN never seen gives 0 at its level.
    assert counts.estimates(sign_in(3, 1, "new", asn="64501")) == pytest.approx(
        [0.2, 0.0, 0.2]
    )


def test_a_group_level_is_its_share_of_the_group_times_the_groups_share() -> None:
    counts = Counts(ADDRESS)
    for entry in (
        sign_in(0, 1, "a"),
        sign_in(1, 1, "a"),
        sign_in(2, 2, "b", asn="64501"),
    ):
        counts.add(entry)
    elsewhere = sign_in(3, 1, "new", asn="64501")

    # In ASN 64501: one sign-in, one value, so 1/(1+1), times its 1/3 share.
    assert counts.estimates(elsewhere)[1] == pytest.approx(1 / 6)
    # Back-off takes that finest seen group, not the value's own 1/(3+2).
    assert counts.probability(elsewhere, BACKOFF) == pytest.approx(1 / 6)


def test_interpolation_weighs_the_levels_and_back_off_takes_the_finest_seen() -> None:
    counts = Counts(ADDRESS)
    for entry in (sign_in(0, 1, "a"), sign_in(1, 1, "a")):
        counts.add(entry)
    elsewhere = sign_in(2, 1, "new", asn="64501")  # a new ASN, a known country

    # Levels: 1/3, 0, 1/3 with weights 0.6, 0.3, 0.1.
    assert counts.probability(elsewhere, INTERPOLATION) == pytest.approx(0.7 / 3)
    assert counts.probability(elsewhere, BACKOFF) == pytest.approx(1 / 3)
    assert counts.probability(sign_in(2, 1, "a"), BACKOFF) == pytest.approx(2 / 3)


def test_the_score_matches_a_hand_computation() -> None:
    model = Model()
    history = [sign_in(0, 1, "a"), sign_in(1, 1, "a")]
    for entry in [*history, sign_in(2, 2, "b")]:
        model.learn(entry)
    new = sign_in(3, 1, "new")

    # p(u | attack) 1/2 over p(u | legit) 2/3; the address 0.2 overall over
    # 1/3 for the user; the user agent 3/4 overall over 2/3 for the user.
    expected = math.log((0.5 / (2 / 3)) * (0.2 / (1 / 3)) * (0.75 / (2 / 3)))
    assert model.score(new, history, INTERPOLATION) == pytest.approx(expected)
    # Without p(x): only how new the sign-in is to the user.
    uniform = math.log((0.5 / (2 / 3)) * (1 / (1 / 3)) * (1 / (2 / 3)))
    assert model.score(new, history, UNIFORM_ATTACKER) == pytest.approx(uniform)
    parts = model.parts(new, history, INTERPOLATION)
    assert parts is not None
    assert sum(parts.values()) == pytest.approx(expected)


def test_a_familiar_sign_in_scores_lower_than_a_new_one_with_the_same_counts() -> None:
    model = Model()
    history = [sign_in(minute, 1, "a") for minute in range(3)]
    for entry in [*history, sign_in(3, 2, "b"), sign_in(4, 3, "c")]:
        model.learn(entry)

    familiar = model.score(sign_in(5, 1, "a"), history, INTERPOLATION)
    # "b" is seen as often overall as "a" less the user's own sign-ins.
    new = model.score(sign_in(5, 1, "b"), history, INTERPOLATION)
    assert new > familiar


def test_no_history_scores_highest() -> None:
    model = Model()
    model.learn(sign_in(0, 1, "a"))
    assert model.score(sign_in(1, 1, "a"), [], INTERPOLATION) == math.inf
    assert model.parts(sign_in(1, 1, "a"), [], INTERPOLATION) is None


def test_the_sample_is_scored_before_it_is_learned_and_only_its_own() -> None:
    start = T0 + timedelta(minutes=10)
    end = T0 + timedelta(days=200)
    logins = [
        sign_in(0, 1, "a"),  # before the window: learned, not in the history
        *[sign_in(10 + day * 24 * 60, 1, "a") for day in range(4)],
        sign_in(20, 2, "a"),  # not sampled: learned, not scored
        sign_in(30, 1, "a", success=False),  # a failure: neither
        sign_in(150 * 24 * 60, 1, "new", takeover=True),
    ]
    logins.sort(key=lambda entry: entry.at)

    scored = score_sample(logins, {1}, start, end, (90, 180), 90, 3)

    # Each score uses the data before it only: as a model that learned those.
    model = Model()
    for entry in logins[:-1]:
        model.learn(entry)
    history = [entry for entry in logins[1:-1] if entry.user == 1 and entry.success]
    expected = model.score(logins[-1], history, INTERPOLATION)

    assert [entry.takeover for entry in scored] == [False] * 4 + [True]
    # The first in the window has no history in it.
    assert scored[0].scores[INTERPOLATION, 90] == math.inf
    assert scored[0].parts is None
    assert [entry.eligible for entry in scored] == [False, False, False, True, False]
    # 150 days on, 90 days of history hold nothing; 180 days hold four.
    last = scored[-1]
    assert last.scores[INTERPOLATION, 90] == math.inf
    assert last.scores[INTERPOLATION, 180] == pytest.approx(expected)
    assert set(last.scores) == {
        (mode, days)
        for mode in (INTERPOLATION, BACKOFF, UNIFORM_ATTACKER)
        for days in (90, 180)
    }
