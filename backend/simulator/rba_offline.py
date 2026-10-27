"""Command line: python -m simulator.rba_offline --data .rba/rba-dataset.csv

The rules of simulator/rba.py replayed in Python on the same sample, without
the API, so that other thresholds can be tried in minutes rather than an hour
each (`make evaluate-rba-offline`). The replay mirrors what the API stores
and when each rule sees it. It is trusted only as far as it reproduces, at
the application's thresholds, every number of the API run in
docs/evaluation/independent-rba.json: if one differs, nothing is written.

The thresholds tried here are a sensitivity analysis on the evaluation data,
not a tuning: the application's settings stay as they are.
"""

import argparse
import json
import math
import statistics
import sys
import time
from bisect import bisect_left
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.models.security_event import SecurityEventType
from app.services.detection_service import device_of, network_of
from simulator.freeman import INTERPOLATION, MODES, Scored, score_sample
from simulator.rba import (
    DATASET,
    AccountResult,
    Alert,
    Lockout,
    Login,
    Plan,
    Rate,
    Results,
    WeekResult,
    collect,
    data_end,
    email_of,
    event_of,
    measure_accounts,
    measure_week,
    per_thousand,
    percent,
    plan,
    read_logins,
    replay_lockout,
    thresholds,
    to_json,
)


@dataclass(frozen=True)
class Event:
    """A sign-in as the API stores it."""

    login: Login
    ip: str
    user_agent: str | None


def events_of(logins: list[Login]) -> list[Event]:
    """The sign-ins ingestion would store, in the order it stores them; those
    with an invalid address are skipped, as rba.ingest skips them."""
    events: list[Event] = []
    for login in logins:
        event = event_of(login, timedelta())
        if event is not None:
            events.append(Event(login, event["ip_address"], event["user_agent"]))
    return events


# What counts as the same network, for the T1078 variants.
NETWORKS: dict[str, Callable[[Event], str | None]] = {
    "address": lambda event: event.ip,
    "/24": lambda event: network_of(event.ip),
    "ASN": lambda event: event.login.asn,
}


def replay_unfamiliar(
    events: list[Event],
    network: str = "/24",
    device: bool = True,
    lookback_days: int | None = None,
    min_sign_ins: int | None = None,
) -> list[Alert]:
    """As detection_service.detect_unfamiliar_sign_in: a successful sign-in
    with a user agent, after at least `min_sign_ins` such sign-ins in the
    lookback, from a network none of them used and, when `device`, a device
    none of them used. Sign-ins at the same moment do not see each other."""
    lookback = timedelta(
        days=lookback_days or settings.detection_unfamiliar_lookback_days
    )
    minimum = min_sign_ins or settings.detection_unfamiliar_min_sign_ins
    network_of_event = NETWORKS[network]
    habits: dict[int, deque[tuple[datetime, str | None, str]]] = defaultdict(deque)
    alerts = []
    for event in events:
        login = event.login
        if not login.success or not event.user_agent:
            continue
        past = habits[login.user]
        while past and past[0][0] < login.at - lookback:
            past.popleft()
        seen = [habit for habit in past if habit[0] < login.at]
        here = (login.at, network_of_event(event), device_of(event.user_agent))
        if (
            len(seen) >= minimum
            and here[1] not in {habit[1] for habit in seen}
            and not (device and here[2] in {habit[2] for habit in seen})
        ):
            alerts.append(
                Alert(
                    SecurityEventType.UNFAMILIAR_SIGN_IN,
                    email_of(login.user),
                    event.ip,
                    login.at,
                )
            )
        past.append(here)
    return alerts


def replay_dormant(events: list[Event], days: int | None = None) -> list[Alert]:
    """As detection_service.detect_dormant_account_login: a successful sign-in
    `days` or more after the account's previous one. The accounts are created
    when the run starts, after every sign-in's moved time, so a first sign-in
    is never flagged."""
    idle = timedelta(days=days or settings.detection_dormant_days)
    # Each user's latest successful sign-in, and the latest one before it.
    last: dict[int, tuple[datetime, datetime | None]] = {}
    alerts = []
    for event in events:
        login = event.login
        if not login.success:
            continue
        latest, before = last.get(login.user, (None, None))
        previous = latest if latest is None or latest < login.at else before
        if previous is not None and login.at - previous >= idle:
            alerts.append(
                Alert(
                    SecurityEventType.DORMANT_ACCOUNT_LOGIN,
                    email_of(login.user),
                    event.ip,
                    login.at,
                )
            )
        if latest is None or latest < login.at:
            last[login.user] = (login.at, latest)
    return alerts


def replay_spray(
    events: list[Event],
    min_accounts: int | None = None,
    window_minutes: int | None = None,
) -> list[Alert]:
    """As detection_service.detect_password_spray: a failure from an address
    that failed for `min_accounts` different emails within the window, after
    its latest spray alert. Each failure counts those before it in time
    order: the last failure of a moment counts all of that moment, so the
    alerts are the API's whichever failures of a moment the API stores
    together (tests/test_rba_offline.py checks it with small batches)."""
    minimum = min_accounts or settings.detection_spray_min_accounts
    window = timedelta(
        minutes=window_minutes or settings.detection_spray_window_minutes
    )
    by_address: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        if not event.login.success:
            by_address[event.ip].append(event)
    position: dict[str, int] = defaultdict(int)
    latest_alert: dict[str, datetime] = {}
    alerts = []
    for event in events:
        if event.login.success:
            continue
        failures = by_address[event.ip]
        earlier = position[event.ip]
        position[event.ip] += 1
        at = event.login.at
        since = max(at - window, latest_alert.get(event.ip, at - window))
        emails = set()
        while earlier >= 0 and failures[earlier].login.at > since:
            emails.add(failures[earlier].login.user)
            earlier -= 1
        if len(emails) >= minimum:
            alerts.append(
                Alert(SecurityEventType.PASSWORD_SPRAY_DETECTED, None, event.ip, at)
            )
            latest_alert[event.ip] = at
    return alerts


# Reproducing the API run


def replayed(chosen: Plan, accounts: list[Login], weeks: list[list[Login]]) -> dict:
    """What the API run's JSON reports, from the replay at the application's
    thresholds: the parts that must match it exactly."""
    events = events_of(accounts)
    account_result = measure_accounts(
        accounts,
        replay_unfamiliar(events) + replay_dormant(events),
        timedelta(),
        chosen,
        len(accounts) - len(events),
    )
    week_results = []
    for start, week in zip(chosen.weeks, weeks, strict=True):
        week_events = events_of(week)
        week_results.append(
            measure_week(
                start, week, replay_spray(week_events), len(week) - len(week_events)
            )
        )
    results = Results(
        seed=0,
        revision="",
        plan=chosen,
        accounts=account_result,
        weeks=week_results,
        started_at=datetime.now(UTC),
        seconds=0,
    )
    return comparable(json.loads(to_json(results)))


def comparable(report: dict) -> dict:
    return {
        key: report[key]
        for key in ("settings", "window", "population_by_sign_ins", "accounts", "weeks")
    }


def differences(expected: object, actual: object, path: str = "") -> list[str]:
    """Where `actual` departs from `expected`, as JSON paths."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        keys = expected.keys() | actual.keys()
        return [
            difference
            for key in sorted(keys)
            for difference in differences(
                expected.get(key), actual.get(key), f"{path}.{key}"
            )
        ]
    if (
        isinstance(expected, list)
        and isinstance(actual, list)
        and len(expected) == len(actual)
    ):
        return [
            difference
            for index, (one, other) in enumerate(zip(expected, actual, strict=True))
            for difference in differences(one, other, f"{path}[{index}]")
        ]
    return [] if expected == actual else [f"{path}: {expected!r} != {actual!r}"]


# Sensitivity: the rules under other thresholds

UNFAMILIAR_MIN_SIGN_INS = (1, 3, 5)
UNFAMILIAR_LOOKBACK_DAYS = (30, 90, 180)
SPRAY_MIN_ACCOUNTS = tuple(range(2, 11))
LOCKOUT_LIMITS = (3, 5, 10, 20, 100)
DORMANT_DAYS = (30, 90, 180)


@dataclass(frozen=True)
class UnfamiliarVariant:
    network: str
    device: bool
    min_sign_ins: int
    lookback_days: int
    result: AccountResult


def unfamiliar_grid(
    chosen: Plan, accounts: list[Login], events: list[Event]
) -> list[UnfamiliarVariant]:
    return [
        UnfamiliarVariant(
            network,
            device,
            minimum,
            days,
            measure_accounts(
                accounts,
                replay_unfamiliar(events, network, device, days, minimum),
                timedelta(),
                chosen,
                len(accounts) - len(events),
                days,
                minimum,
            ),
        )
        for network in NETWORKS
        for device in (True, False)
        for minimum in UNFAMILIAR_MIN_SIGN_INS
        for days in UNFAMILIAR_LOOKBACK_DAYS
    ]


def spray_grid(chosen: Plan, weeks: list[list[Login]]) -> dict[int, list[WeekResult]]:
    grid: dict[int, list[WeekResult]] = {minimum: [] for minimum in SPRAY_MIN_ACCOUNTS}
    for start, week in zip(chosen.weeks, weeks, strict=True):
        events = events_of(week)
        for minimum in SPRAY_MIN_ACCOUNTS:
            grid[minimum].append(
                measure_week(
                    start,
                    week,
                    replay_spray(events, minimum),
                    len(week) - len(events),
                    minimum,
                )
            )
    return grid


# B2 against the T1078 rule


@dataclass(frozen=True)
class Point:
    """Flagging every sign-in scored at least `threshold`; None flags none."""

    threshold: float | None
    detected: Rate
    false_alarms: Rate


def curve(scored: list[Scored], key: tuple[str, int], eligible: bool) -> list[Point]:
    """The ROC curve of one variant of B2, from the strictest threshold to
    the loosest; `eligible` keeps only the sign-ins the rule can judge."""
    chosen = [entry for entry in scored if entry.eligible or not eligible]
    positives = sorted(entry.scores[key] for entry in chosen if entry.takeover)
    negatives = sorted(entry.scores[key] for entry in chosen if not entry.takeover)
    points = [Point(None, Rate(0, len(positives)), Rate(0, len(negatives)))]
    for threshold in sorted(set(positives) | set(negatives), reverse=True):
        points.append(
            Point(
                threshold,
                Rate(
                    len(positives) - bisect_left(positives, threshold), len(positives)
                ),
                Rate(
                    len(negatives) - bisect_left(negatives, threshold), len(negatives)
                ),
            )
        )
    return points


def area(points: list[Point]) -> float:
    """The area under the curve, by trapezoids: it runs from (0, 0), flagging
    nothing, to (1, 1), flagging everything."""
    total = 0.0
    previous = (0.0, 0.0)
    for point in points:
        here = (point.false_alarms.value or 0.0, point.detected.value or 0.0)
        total += (here[0] - previous[0]) * (here[1] + previous[1]) / 2
        previous = here
    return total


def detected_at(points: list[Point], false_alarms: float) -> Point | None:
    """The point detecting most with at most this share of false alarms."""
    return next(
        (p for p in reversed(points) if (p.false_alarms.value or 0) <= false_alarms),
        None,
    )


def false_alarms_at(points: list[Point], detected: float) -> Point | None:
    """The point with fewest false alarms detecting at least this share."""
    return next((p for p in points if (p.detected.value or 0) >= detected), None)


def rule_point(scored: list[Scored], alerts: list[Alert], eligible: bool) -> Point:
    """The T1078 rule at the application's thresholds, as a point on B2's
    axes: the same sign-ins, the same labels."""
    flagged = {(alert.email, alert.at) for alert in alerts}
    chosen = [entry for entry in scored if entry.eligible or not eligible]
    hits = [(email_of(entry.user), entry.at) in flagged for entry in chosen]
    takeovers = [entry.takeover for entry in chosen]
    return Point(
        None,
        Rate(
            sum(h and t for h, t in zip(hits, takeovers, strict=True)), sum(takeovers)
        ),
        Rate(
            sum(h and not t for h, t in zip(hits, takeovers, strict=True)),
            len(chosen) - sum(takeovers),
        ),
    )


# The run

# B2's history lengths: the rule's lookback first, as the main one, then
# Freeman's six months.
HISTORY_DAYS = (90, 180)
MAIN = (INTERPOLATION, HISTORY_DAYS[0])
# Where the curve is reported: the most detected within each false-alarm share.
CURVE_FALSE_ALARMS = (0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0)


@dataclass
class Offline:
    plan: Plan
    logins: int
    unfamiliar: list[UnfamiliarVariant]
    dormant_per_thousand: dict[int, float]
    spray: dict[int, list[WeekResult]]
    lockout: dict[int, list[Lockout]]
    scored: list[Scored]
    rule_alerts: list[Alert]


class Mismatch(Exception):
    """The replay does not reproduce the API run."""


def evaluate(data: Path, expected: dict, args: argparse.Namespace) -> Offline:
    chosen = plan(read_logins(data), data_end(data), args.users, args.weeks, args.seed)
    accounts, weeks = collect(read_logins(data), chosen)
    wrong = differences(comparable(expected), replayed(chosen, accounts, weeks))
    if wrong:
        raise Mismatch("\n".join(wrong))
    print("The replay reproduces the API run.", flush=True)
    events = events_of(accounts)
    return Offline(
        plan=chosen,
        logins=len(accounts),
        unfamiliar=unfamiliar_grid(chosen, accounts, events),
        dormant_per_thousand={
            days: per_thousand(len(replay_dormant(events, days)), len(accounts))
            for days in DORMANT_DAYS
        },
        spray=spray_grid(chosen, weeks),
        lockout={
            limit: [replay_lockout(week, limit) for week in weeks]
            for limit in LOCKOUT_LIMITS
        },
        scored=score_sample(
            read_logins(data),
            chosen.users,
            chosen.start,
            chosen.end,
            HISTORY_DAYS,
            settings.detection_unfamiliar_lookback_days,
            settings.detection_unfamiliar_min_sign_ins,
        ),
        rule_alerts=replay_unfamiliar(events),
    )


SUBSETS = (("with history", True), ("all", False))
VARIANTS = [(mode, days) for mode in MODES for days in HISTORY_DAYS]
DETECTED_SHARES = (0.9, 0.99)


@dataclass(frozen=True)
class Comparison:
    """One variant of B2 on one subset of sign-ins, beside the rule."""

    rule: Point
    area: float
    at_rule_false_alarms: Point | None
    at_rule_detected: Point | None
    detected_at: dict[float, Point | None]
    false_alarms_at: dict[float, Point | None]


def compare(offline: Offline, key: tuple[str, int], eligible: bool) -> Comparison:
    rule = rule_point(offline.scored, offline.rule_alerts, eligible)
    points = curve(offline.scored, key, eligible)
    return Comparison(
        rule=rule,
        area=area(points),
        at_rule_false_alarms=detected_at(points, rule.false_alarms.value or 0),
        at_rule_detected=false_alarms_at(points, rule.detected.value or 0),
        detected_at={s: detected_at(points, s) for s in CURVE_FALSE_ALARMS},
        false_alarms_at={s: false_alarms_at(points, s) for s in DETECTED_SHARES},
    )


def median_terms(scored: list[Scored], takeover: bool) -> dict[str, float]:
    """The median of each term of B2's main score, in log10, over the
    sign-ins with history: takeovers, or the others."""
    chosen = [
        entry.parts
        for entry in scored
        if entry.eligible and entry.takeover == takeover and entry.parts
    ]
    names = list(chosen[0]) if chosen else []
    return {
        name: statistics.median(parts[name] for parts in chosen) / math.log(10)
        for name in names
    }


def rate_json(value: Rate) -> dict:
    return {
        "hits": value.hits,
        "total": value.total,
        "value": value.value,
        "interval": value.interval,
    }


def point_json(value: Point | None) -> dict | None:
    if value is None:
        return None
    return {
        "threshold": value.threshold,
        "detected": rate_json(value.detected),
        "false_alarms": rate_json(value.false_alarms),
    }


def report_json(offline: Offline, revision: str, seconds: float) -> str:
    def b2(subset: bool) -> dict:
        result = {}
        for mode, days in VARIANTS:
            c = compare(offline, (mode, days), subset)
            result[f"{mode}, {days} days"] = {
                "rule": point_json(c.rule),
                "area_under_curve": c.area,
                "detected_at_rule_false_alarms": point_json(c.at_rule_false_alarms),
                "false_alarms_at_rule_detected": point_json(c.at_rule_detected),
                "detected_at_false_alarms": {
                    f"{s:g}": point_json(p) for s, p in c.detected_at.items()
                },
                "false_alarms_at_detected": {
                    f"{s:g}": point_json(p) for s, p in c.false_alarms_at.items()
                },
            }
        return result

    return json.dumps(
        {
            "dataset": DATASET,
            "revision": revision,
            "seconds": round(seconds),
            "settings": thresholds(),
            "window": [offline.plan.start.isoformat(), offline.plan.end.isoformat()],
            "b2": {name: b2(subset) for name, subset in SUBSETS},
            "b2_terms_log10_median": {
                "takeovers": median_terms(offline.scored, True),
                "others": median_terms(offline.scored, False),
            },
            "unfamiliar": [
                {
                    "network": v.network,
                    "device": v.device,
                    "min_sign_ins": v.min_sign_ins,
                    "lookback_days": v.lookback_days,
                    "recall": rate_json(v.result.recall),
                    "recall_eligible": rate_json(v.result.recall_eligible),
                    "precision": rate_json(v.result.precision),
                    "false_alarms_per_1000": v.result.false_alarms_per_thousand,
                }
                for v in offline.unfamiliar
            ],
            "dormant_per_1000": offline.dormant_per_thousand,
            "spray": {
                minimum: [
                    {
                        "start": week.start.isoformat(),
                        "attack_ips_at_threshold": week.attack_ips_at_threshold,
                        "recall": rate_json(week.recall),
                        "precision": rate_json(week.precision),
                        "false_alarms_per_1000": week.false_alarms_per_thousand,
                    }
                    for week in weeks
                ]
                for minimum, weeks in offline.spray.items()
            },
            "lockout": {
                limit: [asdict(week) for week in weeks]
                for limit, weeks in offline.lockout.items()
            },
        },
        indent=2,
    )


def detected(value: Point | None) -> str:
    return "—" if value is None else percent(value.detected)


def false_alarms(value: Point | None) -> str:
    return "—" if value is None else percent(value.false_alarms)


def to_markdown(offline: Offline, revision: str, seconds: float) -> str:
    main = {name: compare(offline, MAIN, subset) for name, subset in SUBSETS}
    takeovers = median_terms(offline.scored, True)
    others = median_terms(offline.scored, False)
    lines = [
        "# Baselines and thresholds on the RBA login data set",
        "",
        f"Generated by `make evaluate-rba-offline` (commit `{revision}`) in "
        f"{seconds / 60:.0f} minutes, on the sample of `independent-rba.md`. "
        "The rules are replayed in Python (`backend/simulator/rba_offline.py`): "
        "at the application's thresholds the replay reproduced every number of "
        "the API run in `independent-rba.json`, or this file would not have "
        "been written. Every other threshold below is a sensitivity analysis "
        "on the evaluation data; no setting was changed because of it. Data: "
        "*Login Data Set for Risk-Based Authentication*, Wiefling et al., 2022, "
        "[DOI 10.5281/zenodo.6782155](https://doi.org/10.5281/zenodo.6782155), "
        "[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).",
        "",
        "## B2: the Freeman et al. risk score against the T1078 rule",
        "",
        "Each successful sign-in of the sampled users, labelled by the "
        "takeover flag. B2 scores each one; flagging every score above a "
        "threshold trades takeovers detected against false alarms, the share "
        "of the other sign-ins flagged. The rule is one such trade. *With "
        "history* keeps the sign-ins that came after at least "
        f"{settings.detection_unfamiliar_min_sign_ins} successful ones in "
        f"{settings.detection_unfamiliar_lookback_days} days, the only ones "
        "the rule judges: the main comparison. B2 is the interpolated score "
        f"with {MAIN[1]} days of history (Method, below).",
        "",
        "| Sign-ins | T1078: detected | T1078: false alarms "
        "| B2: detected at T1078's false alarms "
        "| B2: false alarms at T1078's detection | B2: area under the curve |",
        "| --- | --- | --- | --- | --- | --- |",
        *(
            f"| {name.capitalize()} | {percent(c.rule.detected)} | "
            f"{percent(c.rule.false_alarms)} | {detected(c.at_rule_false_alarms)} | "
            f"{false_alarms(c.at_rule_detected)} | {c.area:.3f} |"
            for name, c in main.items()
        ),
        "",
        "An area under the curve of 0.5 is what random scores give; below it, "
        "the score ranks the takeovers as less risky than the other sign-ins.",
        "",
        "B2 at the operating points the papers report, with history: Freeman "
        "et al. give the takeovers detected at 10% false alarms; Wiefling et "
        "al. fix the share detected and count the legitimate sign-ins asked "
        "to authenticate again.",
        "",
        "| Operating point | B2 |",
        "| --- | --- |",
        *(
            f"| Detected at {s:.0%} false alarms | "
            f"{detected(main['with history'].detected_at[s])} |"
            for s in (0.01, 0.1)
        ),
        *(
            f"| False alarms at {s:.0%} detected | "
            f"{false_alarms(main['with history'].false_alarms_at[s])} |"
            for s in DETECTED_SHARES
        ),
        "",
        "The curve, with history: the most takeovers B2 detects within each "
        "share of false alarms.",
        "",
        "| False alarms at most | Detected |",
        "| --- | --- |",
        *(
            f"| {s:.1%} | {detected(p)} |"
            for s, p in main["with history"].detected_at.items()
        ),
        "",
        "Every variant, with history. *Back-off* is Freeman's Eq. 10 in place "
        "of the interpolation. *Uniform attacker* is ours, not the papers', "
        "and was added after the first results showed B2 below random: it "
        "drops p(x), so only how unfamiliar a sign-in is to its user counts. "
        "Being chosen after seeing this data, its result here is a "
        "hypothesis for other data, not a finding.",
        "",
        "| Variant | Area under the curve | Detected at T1078's false alarms "
        "| False alarms at T1078's detection |",
        "| --- | --- | --- | --- |",
    ]
    for mode, days in VARIANTS:
        c = compare(offline, (mode, days), True)
        lines.append(
            f"| {mode}, {days} days | {c.area:.3f} | "
            f"{detected(c.at_rule_false_alarms)} | "
            f"{false_alarms(c.at_rule_detected)} |"
        )
    lines += [
        "",
        "What drives the main score: the median of each of its terms, in "
        "log10, over the sign-ins with history. A term higher for the "
        "takeovers pushes them up the ranking.",
        "",
        "| Term | Takeovers | Others |",
        "| --- | --- | --- |",
        *(
            f"| {name} | {takeovers[name]:.2f} | {others.get(name, math.nan):.2f} |"
            for name in takeovers
        ),
        "",
        "Freeman's model takes an attacker's address and user agent to be "
        "drawn like everyone's: p(x | attack) is estimated by p(x), the "
        "value's share of all sign-ins. Where the takeovers come from values "
        "rarer in the whole data than the other sign-ins' values, p(x) lowers "
        "their score more than their novelty to the user, 1 / p(x | u, "
        "legit), raises it. Freeman et al. correct p(x) with a reputation of "
        "each value, p(A | x), which this data set does not provide; using "
        "its attacker label in its place would fit the baseline to the "
        "labels it is judged by.",
        "",
        "## T1078: unfamiliar network and device, other thresholds",
        "",
        "*Network* is what counts as the same network: the exact address, "
        "its /24 (the rule's), or its ASN, which the application does not "
        "know. *Device needed* is the rule's: a sign-in alerts only from a "
        "new network and a new device; without it, a new network is enough. "
        "**Bold** is the application's setting.",
        "",
        "| Network | Device needed | Sign-ins before | Days back | Detected "
        "| … with history | Alerts on takeovers | False alarms / 1,000 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for v in offline.unfamiliar:
        mark = (
            "**"
            if (
                v.network == "/24"
                and v.device
                and v.min_sign_ins == settings.detection_unfamiliar_min_sign_ins
                and v.lookback_days == settings.detection_unfamiliar_lookback_days
            )
            else ""
        )
        r = v.result
        lines.append(
            f"| {mark}{v.network}{mark} | {'yes' if v.device else 'no'} | "
            f"{v.min_sign_ins} | {v.lookback_days} | {percent(r.recall)} | "
            f"{percent(r.recall_eligible)} | {percent(r.precision)} | "
            f"{r.false_alarms_per_thousand:.2f} |"
        )
    lines += [
        "",
        "*… with history* counts the takeovers after at least that many "
        "sign-ins within that many days, so its total changes with them.",
        "",
        "## Dormant account, other idle periods",
        "",
        "No label judges these alerts: only how often they fire.",
        "",
        "| Idle for at least | Alerts per 1,000 sign-ins |",
        "| --- | --- |",
        *(
            f"| {days} days"
            f"{' (setting)' if days == settings.detection_dormant_days else ''} "
            f"| {value:.2f} |"
            for days, value in offline.dormant_per_thousand.items()
        ),
        "",
        "## Password spray (T1110.003), other thresholds",
        "",
        f"Different emails one address must fail on within "
        f"{settings.detection_spray_window_minutes} minutes, per week of "
        "`independent-rba.md`; the setting is "
        f"{settings.detection_spray_min_accounts}.",
        "",
        "| Emails | "
        + " | ".join(
            f"Week of {w.start:%Y-%m-%d}: flagged (precision; false alarms / 1,000)"
            for w in offline.spray[SPRAY_MIN_ACCOUNTS[0]]
        )
        + " |",
        "| --- |" + " --- |" * len(offline.plan.weeks),
    ]
    for minimum, weeks in offline.spray.items():
        lines.append(
            f"| {minimum} | "
            + " | ".join(
                f"{percent(w.recall)} ({percent(w.precision)}; "
                f"{w.false_alarms_per_thousand:.2f})"
                for w in weeks
            )
            + " |"
        )
    lines += [
        "",
        "## B1, lockout, other limits",
        "",
        f"Failures within {settings.login_failure_window_minutes} minutes that "
        f"lock the email for {settings.login_lockout_minutes}; the setting is "
        f"{settings.login_max_failed_attempts}, and NIST SP 800-63B allows up "
        "to 100. Per week: attacker attempts denied, and legitimate users "
        "denied at least once.",
        "",
        "| Failures | "
        + " | ".join(f"Week of {start:%Y-%m-%d}" for start in offline.plan.weeks)
        + " |",
        "| --- |" + " --- |" * len(offline.plan.weeks),
    ]
    for limit, weeks in offline.lockout.items():
        lines.append(
            f"| {limit} | "
            + " | ".join(
                f"{percent(Rate(w.attack_denied, w.attack_attempts))}; "
                f"{w.legitimate_users_denied} "
                f"user{'' if w.legitimate_users_denied == 1 else 's'}"
                for w in weeks
            )
            + " |"
        )
    lines += [
        "",
        "## Method",
        "",
        "- **B2.** Freeman et al., *Who Are You? A Statistical Approach to "
        "Measuring User Authenticity*, NDSS 2016, as Wiefling et al. used it "
        "on this data's source (*Pump Up Password Security!*, ACM TOPS 2023, "
        "DOI 10.1145/3546069): Wiefling's Eq. 1, Freeman's Eq. 7 without the "
        "reputation term. Features: the address, with its ASN and country; "
        "the user agent, with its browser, OS and device type. Each level is "
        "Freeman's Eq. 9 with Eq. 8 smoothing (M the distinct values seen in "
        "the group), combined by Eq. 11 with Wiefling's weights (address 0.6, "
        "ASN 0.3, country 0.1; user agent 0.53, browser 0.27, OS 0.19, device "
        "type 0.01), which come from an earlier study. Reading those weights "
        "as Eq. 11's coefficients is ours: Wiefling gives the weights, not "
        "the formula. No weights were learned (Freeman's Eq. 13): that would "
        "fit the labels.",
        "- **B2's state.** p(x) and p(u | legit) count every successful "
        "sign-in of the whole data before the one scored, in time order, as "
        "Wiefling replayed it. A user's history is their successful sign-ins "
        f"of the last {MAIN[1]} days (Freeman used six months: the "
        f"{HISTORY_DAYS[1]}-day variant), from the window's start only, as "
        "the API run saw. A user with none gets the highest score: neither "
        "paper scores one, so that choice is ours.",
        "- **The rule as a point.** Its alerts at the application's "
        "thresholds, on the same sign-ins and labels as B2; false alarms are "
        "a share of the successful non-takeover sign-ins, not per 1,000 of "
        "all sign-ins as in `independent-rba.md`.",
        "- **Intervals.** 95% Wilson score intervals.",
        "",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m simulator.rba_offline",
        description="Baselines and thresholds on the RBA login data set.",
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--users", type=int, default=20_000)
    parser.add_argument("--weeks", type=int, default=3)
    parser.add_argument("--revision", default="unknown")
    parser.add_argument("--out", type=Path, default=Path("../docs/evaluation"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    expected = json.loads((args.out / "independent-rba.json").read_text())
    if (expected["seed"], expected["settings"]) != (args.seed, thresholds()):
        print(
            "Refusing to run: the API run used another seed or other settings.",
            file=sys.stderr,
        )
        return 2
    started = time.monotonic()
    try:
        offline = evaluate(args.data, expected, args)
    except Mismatch as error:
        print(
            f"The replay differs from the API run; nothing written.\n{error}",
            file=sys.stderr,
        )
        return 1
    seconds = time.monotonic() - started
    (args.out / "independent-rba-baselines.json").write_text(
        report_json(offline, args.revision, seconds) + "\n"
    )
    (args.out / "independent-rba-baselines.md").write_text(
        to_markdown(offline, args.revision, seconds)
    )
    print(f"Written to {args.out}/independent-rba-baselines.md and .json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
