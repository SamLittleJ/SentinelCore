"""B2: the risk score of Freeman et al. (NDSS 2016), as Wiefling et al. (ACM
TOPS 2023) applied it to the data set this one comes from.

For a successful sign-in x of user u, with features k (the address and the
user agent), Wiefling's Eq. 1, which is Freeman's Eq. 7 without the
reputation term:

    score = prod_k p(x_k) / p(x_k | u, legit)  *  p(u | attack) / p(u | legit)

The higher, the riskier. p(x_k) counts every successful sign-in of the data
before x, and p(x_k | u, legit) u's successful sign-ins in the history
window; p(u | attack) is 1 / the users seen so far, and p(u | legit) u's
share of the successful sign-ins so far.

Each feature is estimated at several levels: the address on its own, within
its ASN and within its country; the user agent on its own, within its
browser, its OS and its device type. Level h gives p(x | h) p(h) (Freeman
Eq. 9), with p(x | h) smoothed by Freeman Eq. 8, M being the distinct values
seen in h (his best model's choice), and p(h) not smoothed. The levels are
combined by Freeman's linear interpolation (Eq. 11) with Wiefling's weights
(§4.3), which come from an earlier study, not from this data. Reading those
weights as Eq. 11's coefficients is ours: Wiefling gives the weights, not
the formula. Freeman's back-off (Eq. 10), with every alpha 1, is a variant.

A user with no successful sign-in in the window is given the highest risk:
neither paper scores one (Freeman: "not designed to protect accounts that
have no login history"), so this choice is ours.
"""

import math
from collections import Counter, deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from simulator.rba import Login

INTERPOLATION = "interpolation"
BACKOFF = "backoff"
# Ours, not the papers': p(x | attack) taken as uniform, so only how
# unfamiliar x is to the user counts (interpolated as the main variant).
UNIFORM_ATTACKER = "uniform attacker"
MODES = (INTERPOLATION, BACKOFF, UNIFORM_ATTACKER)
FEATURE_NAMES = ("address", "user agent")


@dataclass(frozen=True)
class Feature:
    value: Callable[[Login], str]
    # The groups above the value, finest first, and every level's weight:
    # the value's own level first (Wiefling §4.3).
    groups: tuple[Callable[[Login], str], ...]
    weights: tuple[float, ...]


FEATURES = (
    Feature(
        value=lambda login: login.ip,
        groups=(lambda login: login.asn, lambda login: login.country),
        weights=(0.6, 0.3, 0.1),
    ),
    Feature(
        value=lambda login: login.user_agent,
        groups=(
            lambda login: login.browser,
            lambda login: login.os,
            lambda login: login.device_type,
        ),
        weights=(0.53, 0.27, 0.19, 0.01),
    ),
)


class Counts:
    """How often one feature's values were seen, and per group of each level
    its sign-ins and distinct values.

    shortcut: a value is counted as its group's, which holds because every
    address of the data has one ASN and one country, and every user agent
    one browser, OS and device type (checked on the whole data set); data
    where that fails needs counts per group and value."""

    def __init__(self, feature: Feature) -> None:
        self.feature = feature
        self.total = 0
        self.values: Counter[str] = Counter()
        self.sign_ins: list[Counter[str]] = [Counter() for _ in feature.groups]
        self.distinct: list[Counter[str]] = [Counter() for _ in feature.groups]

    def add(self, login: Login) -> None:
        value = self.feature.value(login)
        new = self.values[value] == 0
        self.total += 1
        self.values[value] += 1
        for level, group_of in enumerate(self.feature.groups):
            group = group_of(login)
            self.sign_ins[level][group] += 1
            self.distinct[level][group] += new

    def estimates(self, login: Login) -> list[float]:
        """Eq. 8 for the value on its own, then Eq. 9 for each group: 0 when
        the group was never seen."""
        count = self.values[self.feature.value(login)]
        own = (count or 1) / (self.total + len(self.values))
        result = [own]
        for level, group_of in enumerate(self.feature.groups):
            group = group_of(login)
            in_group = self.sign_ins[level][group]
            unseen = self.distinct[level][group]
            within = (count or 1) / (in_group + unseen) if in_group else 0.0
            result.append(within * in_group / self.total)
        return result

    def probability(self, login: Login, mode: str) -> float:
        if self.total == 0:
            return 0.0
        estimates = self.estimates(login)
        if mode != BACKOFF:
            return sum(
                weight * estimate
                for weight, estimate in zip(
                    self.feature.weights, estimates, strict=True
                )
            )
        # Back-off: the value's own estimate when it was seen, else the
        # finest group that was, else the value's smoothed share of unseen.
        if self.values[self.feature.value(login)]:
            return estimates[0]
        return next((estimate for estimate in estimates[1:] if estimate), estimates[0])


class Model:
    """The global side of the score: every successful sign-in, in time
    order, learned after it is scored."""

    def __init__(self) -> None:
        self.features = [Counts(feature) for feature in FEATURES]
        self.users: Counter[int] = Counter()
        self.total = 0

    def learn(self, login: Login) -> None:
        if not login.success:
            return
        for counts in self.features:
            counts.add(login)
        self.users[login.user] += 1
        self.total += 1

    def parts(
        self, login: Login, history: Iterable[Login], mode: str
    ) -> dict[str, float] | None:
        """The terms of the log of the score of `login` given the user's
        `history`, or None when the user has no history to compare with."""
        own = [Counts(feature) for feature in FEATURES]
        for past in history:
            for counts in own:
                counts.add(past)
        if own[0].total == 0 or self.total == 0 or not self.users[login.user]:
            return None
        terms = {
            "p(u | attack)": math.log(1 / len(self.users)),
            "1 / p(u | legit)": -math.log(self.users[login.user] / self.total),
        }
        for name, overall, user in zip(FEATURE_NAMES, self.features, own, strict=True):
            if mode != UNIFORM_ATTACKER:
                terms[f"p({name})"] = math.log(overall.probability(login, mode))
            terms[f"1 / p({name} | u, legit)"] = -math.log(
                user.probability(login, mode)
            )
        return terms

    def score(self, login: Login, history: Iterable[Login], mode: str) -> float:
        """The log of the score; infinite, the highest, without history."""
        terms = self.parts(login, history, mode)
        return math.inf if terms is None else sum(terms.values())


@dataclass(frozen=True)
class Scored:
    """One successful sign-in of a sampled user, its label and its scores."""

    user: int
    at: datetime
    takeover: bool
    # Enough successful sign-ins before it for the T1078 rule to judge it.
    eligible: bool
    scores: dict[tuple[str, int], float]
    # The main variant's terms, to show what drives its score.
    parts: dict[str, float] | None


def score_sample(
    logins: Iterable[Login],
    users: set[int],
    start: datetime,
    end: datetime,
    history_days: tuple[int, ...],
    lookback_days: int,
    min_sign_ins: int,
) -> list[Scored]:
    """One pass over the whole data, in time order: each successful sign-in
    of `users` in [start, end) is scored, under each mode and history
    length, before the model learns it. A user's history holds only their
    sign-ins from `start`, as the API run saw only those."""
    model = Model()
    longest = timedelta(days=max(history_days))
    histories: dict[int, deque[Login]] = {}
    scored = []
    for login in logins:
        if login.success and login.user in users and start <= login.at < end:
            past = histories.setdefault(login.user, deque())
            while past and past[0].at < login.at - longest:
                past.popleft()
            lookback = login.at - timedelta(days=lookback_days)
            scores = {}
            windows = {
                days: [
                    entry
                    for entry in past
                    if entry.at >= login.at - timedelta(days=days)
                ]
                for days in history_days
            }
            for days, window in windows.items():
                for mode in MODES:
                    scores[mode, days] = model.score(login, window, mode)
            scored.append(
                Scored(
                    user=login.user,
                    at=login.at,
                    takeover=login.takeover,
                    eligible=sum(entry.at >= lookback for entry in past)
                    >= min_sign_ins,
                    scores=scores,
                    parts=model.parts(login, windows[history_days[0]], MODES[0]),
                )
            )
            past.append(login)
        model.learn(login)
    return scored
