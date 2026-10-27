"""A synthetic organization and its routine sign-ins: thirty days by
default, longer for the demo.

Everything is drawn from one seeded random generator, so a seed always gives
the same people, devices and sign-ins. Times are relative to `now`, the start
of the run, so the history always ends the day before.

Besides plain routine, the history holds benign cases: things real people do
that a rule could mistake for an attack. Some must stay quiet (a browser
update, a trip with a known laptop); some are known limits of the rules and
are expected to alert (a new laptop on a trip, a password change day at an
office behind one address).
"""

import random
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# One placeholder, {v}, for the browser's version.
DEVICES = {
    "firefox-linux": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:{v}.0) Gecko/20100101 Firefox/{v}.0"
    ),
    "chrome-windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36"
    ),
    "edge-windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36 Edg/{v}.0.0.0"
    ),
    "safari-mac": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/{v}.0 Safari/605.1.15"
    ),
    "chrome-android": (
        "Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{v}.0.0.0 Mobile Safari/537.36"
    ),
    "safari-iphone": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{v}.0 Mobile/15E148 "
        "Safari/604.1"
    ),
    # Used by nobody in the organization: one is the attackers', the other a
    # laptop someone buys during the month.
    "firefox-windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{v}.0) Gecko/20100101 "
        "Firefox/{v}.0"
    ),
    "chrome-linux": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36"
    ),
}
LAPTOPS = ("firefox-linux", "chrome-windows", "edge-windows", "safari-mac")
PHONES = ("chrome-android", "safari-iphone")
ATTACKER_DEVICE = "firefox-windows"
NEW_LAPTOP = "chrome-linux"

BROWSER_VERSION = 140
# Every browser updates on this day of the history.
BROWSER_UPDATE_DAY = 15

# Documentation and benchmarking address ranges, never routed on the internet.
OFFICE_IP = "192.0.2.10"
# Reserved for examples (RFC 2606): no real company owns it.
DOMAIN = "sim.example.com"
HOTEL_NETWORK = "100.64.50."
CONFERENCE_NETWORK = "100.64.70."

HISTORY_DAYS = 30
# Days before the run on which the benign cases happen.
TRIP_DAYS = (20, 19)
NEW_PHONE_DAY = 22
NEW_LAPTOP_DAY = 25
# The first workday from this one on.
PASSWORD_CHANGE_DAY = 10
PASSWORD_CHANGE_PEOPLE = 12
LEAVE_STARTED_DAY = 110
LEAVE_ENDED_DAY = 3
ROUTINE_TYPO_RATE = 0.08
EVENING_SIGN_IN_RATE = 0.4
WEEKEND_SIGN_IN_RATE = 0.3

FIRST_NAMES = (
    "ana", "andrei", "bianca", "cristian", "diana", "elena", "florin",
    "gabriela", "ioana", "lucian", "maria", "mihai", "nicoleta", "ovidiu",
    "paula", "radu", "sorina", "stefan", "teodora", "victor", "alina",
    "bogdan", "carmen", "dan", "irina", "marius",
)  # fmt: skip
LAST_NAMES = (
    "pop", "ionescu", "marin", "stan", "dumitru", "georgescu", "toma",
    "munteanu", "rusu", "lazar", "matei", "ene", "barbu", "dinu",
)  # fmt: skip
ACTIVE_PEOPLE = 25
DORMANT_PEOPLE = 5
# Unused for a while, but less than the dormant account rule's 90 days.
IDLE_PEOPLE = 5
IDLE_DAYS = 85


def user_agent(device: str, day: int) -> str:
    """The user agent of `device` on `day` days before the run, before or
    after the browser update."""
    version = BROWSER_VERSION + (1 if day <= BROWSER_UPDATE_DAY else 0)
    return DEVICES[device].format(v=version)


@dataclass(frozen=True)
class Person:
    handle: str
    email: str
    # Random, sent only to accept the invitation, and never written anywhere.
    password: str = field(repr=False)
    # Index of the home network; every sign-in from home gets a new address in it.
    home: int
    laptop: str
    phone: str | None

    def home_address(self, rng: random.Random) -> str:
        if self.home % 4 == 3:
            return f"2001:db8:{self.home:x}::{rng.randint(2, 0xFFFF):x}"
        return f"198.18.{self.home}.{rng.randint(2, 254)}"


@dataclass(frozen=True)
class SignIn:
    occurred_at: datetime
    succeeded: bool
    email: str
    ip_address: str | None
    user_agent: str | None

    def payload(self) -> dict:
        return {
            "event_type": "login_success" if self.succeeded else "login_failed",
            "occurred_at": self.occurred_at.isoformat(),
            "email": self.email,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


@dataclass(frozen=True)
class BenignCase:
    """Routine behaviour that a rule could mistake for an attack.

    `expected_alert` is the alert the rules' design predicts for it, or None
    when it should stay quiet. Alerts raised during the routine are put down
    to the first case whose emails or addresses they name.
    """

    name: str
    description: str
    expected_alert: str | None
    emails: frozenset[str] = frozenset()
    ip_addresses: frozenset[str] = frozenset()


@dataclass
class Organization:
    active: list[Person]
    dormant: list[Person]
    idle: list[Person]
    # Back from a long leave; none in a quiet organization.
    returning: Person | None
    sign_ins: list[SignIn]
    cases: list[BenignCase]
    domain: str = DOMAIN

    @property
    def people(self) -> list[Person]:
        returning = [self.returning] if self.returning else []
        return [*self.active, *self.dormant, *self.idle, *returning]


def make_people(
    rng: random.Random,
    tag: str,
    count: int = ACTIVE_PEOPLE + DORMANT_PEOPLE + IDLE_PEOPLE + 1,
    domain: str = DOMAIN,
    first_home: int = 0,
    taken: frozenset[str] = frozenset(),
) -> list[Person]:
    """`count` distinct people; `tag`, when given, keeps their emails apart
    from earlier runs on the same database. Usernames are unique across the
    platform, so handles in `taken`, another organization's, are left out;
    home networks are numbered from `first_home`."""
    names = [
        (first, last)
        for first in FIRST_NAMES
        for last in LAST_NAMES
        if f"{first}.{last}" not in taken
    ]
    chosen = rng.sample(names, count)
    people = []
    for index, (first, last) in enumerate(chosen):
        handle = f"{first}.{last}"
        local_part = f"{handle}.{tag}" if tag else handle
        home = first_home + index
        people.append(
            Person(
                handle=handle,
                email=f"{local_part}@{domain}",
                password=secrets.token_urlsafe(18),
                home=home,
                laptop=rng.choice(LAPTOPS),
                phone=rng.choice((*PHONES, None)),
            )
        )
    return people


def at(day_start: datetime, hour: float, rng: random.Random, spread: float) -> datetime:
    """A moment `hour` hours into the day, plus up to `spread` hours."""
    return day_start + timedelta(hours=hour + rng.uniform(0, spread))


def sign_in_with_typos(
    when: datetime, person: Person, ip: str, agent: str, typos: int
) -> list[SignIn]:
    """`typos` failed attempts a few seconds apart, then the sign-in."""
    attempts = [
        SignIn(
            when - timedelta(seconds=20 * (typos - n)), False, person.email, ip, agent
        )
        for n in range(typos)
    ]
    return [*attempts, SignIn(when, True, person.email, ip, agent)]


def usual_day(
    rng: random.Random,
    person: Person,
    day_start: datetime,
    first_day: bool,
    office_ip: str,
    laptop: str,
    phone: str,
    old_password_at: datetime | None = None,
) -> list[SignIn]:
    """One ordinary day of `person`: the office on workdays, with an
    occasional typo, often home in the evening, and home now and then at the
    weekend. On `old_password_at` they type their old password once first."""
    if first_day:
        # The organization is older than the window: everyone has used the
        # office and home before, which the first day stands for.
        office = SignIn(
            at(day_start, 8.5, rng, 1.5), True, person.email, office_ip, laptop
        )
        home = person.home_address(rng)
        return [
            office,
            SignIn(at(day_start, 18, rng, 4), True, person.email, home, phone),
        ]
    if day_start.weekday() < 5:
        if old_password_at is not None:
            when, typos = old_password_at, 1
        else:
            when = at(day_start, 8.5, rng, 1.5)
            typos = 1 if rng.random() < ROUTINE_TYPO_RATE else 0
        sign_ins = sign_in_with_typos(when, person, office_ip, laptop, typos)
        if rng.random() < EVENING_SIGN_IN_RATE:
            home = person.home_address(rng)
            sign_ins.append(
                SignIn(at(day_start, 18, rng, 4), True, person.email, home, phone)
            )
        return sign_ins
    if rng.random() < WEEKEND_SIGN_IN_RATE:
        home = person.home_address(rng)
        return [SignIn(at(day_start, 10, rng, 10), True, person.email, home, phone)]
    return []


def build_organization(
    rng: random.Random,
    now: datetime,
    tag: str,
    history_days: int = HISTORY_DAYS,
    through_now: bool = False,
    *,
    domain: str = DOMAIN,
    office_ip: str = OFFICE_IP,
    first_home: int = 0,
    taken: frozenset[str] = frozenset(),
) -> Organization:
    """The organization and `history_days` of its routine, ending the day
    before `now`, or at `now` itself when `through_now`: the demo shows this
    morning too. The demo gives each of its organizations its own email
    domain, office address and home networks."""
    people = make_people(rng, tag, domain=domain, first_home=first_home, taken=taken)
    active = people[:ACTIVE_PEOPLE]
    dormant = people[ACTIVE_PEOPLE : ACTIVE_PEOPLE + DORMANT_PEOPLE]
    idle = people[ACTIVE_PEOPLE + DORMANT_PEOPLE : -1]
    returning = people[-1]
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Who does what, among the people no attack touches (see attacks.py).
    travellers = active[15:17]
    new_phone = active[17]
    new_laptop = active[18]
    rotation_day = next(
        day
        for day in range(PASSWORD_CHANGE_DAY, 0, -1)
        if (midnight - timedelta(days=day)).weekday() < 5
    )
    rotating = rng.sample(range(ACTIVE_PEOPLE), PASSWORD_CHANGE_PEOPLE)

    sign_ins: list[SignIn] = []
    for day in range(history_days, -1 if through_now else 0, -1):
        day_start = midnight - timedelta(days=day)
        workday = day_start.weekday() < 5
        for index, person in enumerate(active):
            laptop = user_agent(person.laptop, day)
            phone = user_agent(person.phone, day) if person.phone else laptop
            if person in travellers and day in TRIP_DAYS:
                ip = f"{HOTEL_NETWORK}{rng.randint(2, 254)}"
                sign_ins.append(
                    SignIn(at(day_start, 8, rng, 2), True, person.email, ip, laptop)
                )
                continue
            if person is new_laptop and day == NEW_LAPTOP_DAY:
                ip = f"{CONFERENCE_NETWORK}{rng.randint(2, 254)}"
                agent = user_agent(NEW_LAPTOP, day)
                sign_ins.append(
                    SignIn(at(day_start, 9, rng, 1), True, person.email, ip, agent)
                )
                continue
            if person is new_phone and day <= NEW_PHONE_DAY:
                phone = user_agent(next(d for d in PHONES if d != person.phone), day)
            # Everyone types the old password once after the change.
            old_password_at = (
                day_start + timedelta(hours=9, minutes=rotating.index(index))
                if workday and day == rotation_day and index in rotating
                else None
            )
            sign_ins += usual_day(
                rng,
                person,
                day_start,
                day == history_days,
                office_ip,
                laptop,
                phone,
                old_password_at,
            )

    # Accounts that were used long ago, or a while ago, and then left alone;
    # attackers wake them up later. The returning person is back from a long
    # leave, for real.
    for person, first_day, last_day in [
        *((person, 200, 100) for person in dormant),
        *((person, IDLE_DAYS + 7 * 12, IDLE_DAYS) for person in idle),
        (returning, 160, LEAVE_STARTED_DAY),
    ]:
        for day in range(first_day, last_day - 1, -7):
            day_start = midnight - timedelta(days=day)
            sign_ins.append(
                SignIn(
                    at(day_start, 9, rng, 8),
                    True,
                    person.email,
                    person.home_address(rng),
                    DEVICES[person.laptop].format(v=BROWSER_VERSION - 4),
                )
            )
    for day in range(LEAVE_ENDED_DAY, 0, -1):
        day_start = midnight - timedelta(days=day)
        agent = user_agent(returning.laptop, day)
        sign_ins.append(
            SignIn(at(day_start, 8.5, rng, 1), True, returning.email, office_ip, agent)
        )

    cases = [
        BenignCase(
            "new_laptop_on_a_trip",
            "Signs in once from a conference network on a laptop bought there",
            "unfamiliar_sign_in",
            emails=frozenset({new_laptop.email}),
        ),
        BenignCase(
            "back_from_leave",
            "Back at the office after more than "
            f"{LEAVE_STARTED_DAY - LEAVE_ENDED_DAY - 7} days away",
            "dormant_account_login",
            emails=frozenset({returning.email}),
        ),
        BenignCase(
            "password_change_day",
            f"{PASSWORD_CHANGE_PEOPLE} people type their old password once from "
            "09:00, behind the office's single address",
            "password_spray_detected",
            ip_addresses=frozenset({office_ip}),
        ),
        BenignCase(
            "trip_with_known_laptop",
            "Two people sign in from a hotel for two days with their usual laptop",
            None,
            emails=frozenset(person.email for person in travellers),
        ),
        BenignCase(
            "new_phone",
            "Starts signing in from home on a new phone",
            None,
            emails=frozenset({new_phone.email}),
        ),
        BenignCase(
            "routine",
            "Office sign-ins on workdays (with an occasional typo), evenings and "
            f"weekends from home, and a browser update on day {BROWSER_UPDATE_DAY}",
            None,
            emails=frozenset(person.email for person in people),
        ),
    ]
    if through_now:
        sign_ins = [sign_in for sign_in in sign_ins if sign_in.occurred_at < now]
    sign_ins.sort(key=lambda sign_in: sign_in.occurred_at)
    return Organization(active, dormant, idle, returning, sign_ins, cases, domain)


def build_quiet_organization(
    rng: random.Random,
    now: datetime,
    size: int,
    history_days: int = HISTORY_DAYS,
    through_now: bool = False,
    *,
    domain: str,
    office_ip: str,
    first_home: int,
    taken: frozenset[str] = frozenset(),
) -> Organization:
    """`size` people who only keep to their routine: nobody away for long,
    travelling or on a new device, and no password change day. Nothing in
    their history looks like an attack, so a rule that fires on it is a false
    positive. The demo's organizations besides the attacked one."""
    people = make_people(rng, "", size, domain, first_home, taken)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    sign_ins: list[SignIn] = []
    for day in range(history_days, -1 if through_now else 0, -1):
        day_start = midnight - timedelta(days=day)
        for person in people:
            laptop = user_agent(person.laptop, day)
            phone = user_agent(person.phone, day) if person.phone else laptop
            sign_ins += usual_day(
                rng, person, day_start, day == history_days, office_ip, laptop, phone
            )
    if through_now:
        sign_ins = [sign_in for sign_in in sign_ins if sign_in.occurred_at < now]
    sign_ins.sort(key=lambda sign_in: sign_in.occurred_at)
    routine = BenignCase(
        "routine",
        "Office sign-ins on workdays (with an occasional typo), evenings and "
        "weekends from home",
        None,
        emails=frozenset(person.email for person in people),
    )
    return Organization(people, [], [], None, sign_ins, [routine], domain)
