"""The attacks the simulator plays, one per MITRE ATT&CK technique detected.

Each attack is a list of steps. Most are sign-ins reported through
ingestion, dated during the hour before the run, so their pace is that of a
real attack. Brute force and role changes cannot be reported: the lockout
counts only this application's own sign-ins, and roles change only through
its API. Those steps happen for real, when they are sent.

An attack also says which alert would mean it was caught, and which emails,
addresses or accounts that alert would name.

Evasive variants are built to pass under one rule, the way a careful
attacker would. They measure what the rules miss, so any alert that names
them counts as catching them, whichever rule raised it. Why each one passes
assumes the default thresholds (`backend/.env.example`).
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from simulator.population import (
    ATTACKER_DEVICE,
    IDLE_DAYS,
    Organization,
    SignIn,
    user_agent,
)

ATTACKS_PER_TECHNIQUE = 5
# Attempts a few seconds apart, fast enough to be done in minutes.
SPRAY_INTERVAL = timedelta(seconds=30)
# Emails tried per spray: real ones mixed with guesses.
SPRAY_EMAILS = (10, 14)
SPRAY_GUESSES = 3
# More than the lockout threshold: the attacker keeps going after it.
BRUTE_FORCE_ATTEMPTS = 8
# Slow enough that at most eight attempts fall in the 15-minute window.
SLOW_SPRAY_INTERVAL = timedelta(minutes=2)
DISTRIBUTED_SPRAY_ADDRESSES = 12


@dataclass(frozen=True)
class Step:
    """`ingest` reports a sign-in; `wrong_password` signs in for real with a
    wrong password; `grant_admin` makes an account an admin, as the owner."""

    kind: Literal["ingest", "wrong_password", "grant_admin"]
    sign_in: SignIn | None = None
    email: str | None = None
    user_id: int | None = None


@dataclass(frozen=True)
class Attack:
    name: str
    technique: str
    # For an evasive variant, the alert of the rule it is built to pass under.
    alert_type: str
    description: str
    steps: list[Step]
    emails: frozenset[str] = frozenset()
    ip_addresses: frozenset[str] = frozenset()
    target_user_ids: frozenset[int] = field(default_factory=frozenset)
    # Why an evasive variant passes under its rule; None for the others.
    evasion: str | None = None

    @property
    def variant(self) -> str:
        """The name without its number: "slow-spray-2" is a "slow-spray"."""
        return self.name.rsplit("-", 1)[0]

    def is_caught_by(self, alert: dict) -> bool:
        type_matches = (
            self.evasion is not None or alert["event_type"] == self.alert_type
        )
        return type_matches and (
            alert["email"] in self.emails
            or alert["ip_address"] in self.ip_addresses
            or alert["target_user_id"] in self.target_user_ids
        )


def plan_attacks(
    rng: random.Random,
    now: datetime,
    organization: Organization,
    user_ids: dict[str, int],
) -> list[Attack]:
    """The attacks, in the order they are played: the evasive variants, which
    happen earlier, then the attacks the rules are built for. Each targets
    people or addresses of its own, so no attack prepares the ground for
    another."""
    active = organization.active
    attacker_agent = user_agent(ATTACKER_DEVICE, 0)
    attacks = plan_evasions(rng, now, organization)
    start = now - timedelta(hours=1)

    for n in range(ATTACKS_PER_TECHNIQUE):
        ip = f"203.0.113.{10 + n}"
        count = rng.randint(*SPRAY_EMAILS)
        emails = spray_targets(rng, organization, count)
        first = start + timedelta(minutes=8 * n)
        attacks.append(
            Attack(
                name=f"spray-{n + 1}",
                technique="T1110.003",
                alert_type="password_spray_detected",
                description=(
                    f"{count} emails, one attempt each, every "
                    f"{SPRAY_INTERVAL.seconds} seconds from {ip}"
                ),
                steps=[
                    Step(
                        "ingest",
                        SignIn(
                            first + SPRAY_INTERVAL * index,
                            False,
                            email,
                            ip,
                            attacker_agent,
                        ),
                    )
                    for index, email in enumerate(emails)
                ],
                ip_addresses=frozenset({ip}),
            )
        )

    for n, person in enumerate(organization.dormant):
        ip = f"203.0.113.{100 + n}"
        attacks.append(
            Attack(
                name=f"dormant-{n + 1}",
                technique="T1078",
                alert_type="dormant_account_login",
                description="A sign-in with the stolen password of an account "
                "unused for over 100 days",
                steps=[
                    Step(
                        "ingest",
                        SignIn(
                            start + timedelta(minutes=45 + n),
                            True,
                            person.email,
                            ip,
                            attacker_agent,
                        ),
                    )
                ],
                emails=frozenset({person.email}),
            )
        )

    for n, person in enumerate(active[0:5]):
        ip = f"203.0.113.{120 + n}"
        attacks.append(
            Attack(
                name=f"unfamiliar-{n + 1}",
                technique="T1078",
                alert_type="unfamiliar_sign_in",
                description="A sign-in with the stolen password of an active "
                "account, from the attacker's network and computer",
                steps=[
                    Step(
                        "ingest",
                        SignIn(
                            start + timedelta(minutes=52 + n),
                            True,
                            person.email,
                            ip,
                            attacker_agent,
                        ),
                    )
                ],
                emails=frozenset({person.email}),
            )
        )

    for n, person in enumerate(active[5:10]):
        attacks.append(
            Attack(
                name=f"brute-force-{n + 1}",
                technique="T1110.001",
                alert_type="brute_force_detected",
                description="Wrong passwords for one account, through the "
                "application's own sign-in",
                steps=[Step("wrong_password", email=person.email)]
                * BRUTE_FORCE_ATTEMPTS,
                emails=frozenset({person.email}),
            )
        )

    for n, person in enumerate(active[10:15]):
        user_id = user_ids[person.email]
        attacks.append(
            Attack(
                name=f"privileged-role-{n + 1}",
                technique="T1098",
                alert_type="privileged_role_granted",
                description="A taken-over owner account makes an accomplice an admin",
                steps=[Step("grant_admin", user_id=user_id)],
                target_user_ids=frozenset({user_id}),
            )
        )
    return attacks


def spray_targets(
    rng: random.Random, organization: Organization, count: int
) -> list[str]:
    """`count` emails to try: real ones mixed with a few guesses."""
    real = rng.sample(
        [person.email for person in organization.active], count - SPRAY_GUESSES
    )
    guesses = [f"{name}@sim.example.com" for name in ("admin", "it", "hr")]
    return rng.sample(real + guesses, count)


def plan_evasions(
    rng: random.Random, now: datetime, organization: Organization
) -> list[Attack]:
    """Five of each evasive variant, between four hours and 75 minutes before
    the run, before the other attacks."""
    attacker_agent = user_agent(ATTACKER_DEVICE, 0)
    start = now - timedelta(hours=4)
    attacks: list[Attack] = []

    for n in range(ATTACKS_PER_TECHNIQUE):
        ip = f"203.0.113.{30 + n}"
        count = rng.randint(*SPRAY_EMAILS)
        first = start + timedelta(minutes=30 * n)
        attacks.append(
            Attack(
                name=f"slow-spray-{n + 1}",
                technique="T1110.003",
                alert_type="password_spray_detected",
                description=f"{count} emails, one attempt every "
                f"{SLOW_SPRAY_INTERVAL.seconds // 60} minutes from {ip}",
                steps=[
                    Step(
                        "ingest",
                        SignIn(
                            first + SLOW_SPRAY_INTERVAL * index,
                            False,
                            email,
                            ip,
                            attacker_agent,
                        ),
                    )
                    for index, email in enumerate(
                        spray_targets(rng, organization, count)
                    )
                ],
                ip_addresses=frozenset({ip}),
                evasion="At most eight attempts fall in the 15-minute window, "
                "under the threshold of ten emails",
            )
        )

    for n in range(ATTACKS_PER_TECHNIQUE):
        addresses = [
            f"198.51.100.{n * DISTRIBUTED_SPRAY_ADDRESSES + k + 1}"
            for k in range(DISTRIBUTED_SPRAY_ADDRESSES)
        ]
        first = now - timedelta(minutes=110 - 4 * n)
        emails = spray_targets(rng, organization, DISTRIBUTED_SPRAY_ADDRESSES)
        attacks.append(
            Attack(
                name=f"distributed-spray-{n + 1}",
                technique="T1110.003",
                alert_type="password_spray_detected",
                description=f"{DISTRIBUTED_SPRAY_ADDRESSES} emails, one attempt "
                f"every {SPRAY_INTERVAL.seconds} seconds, each from another "
                "address",
                steps=[
                    Step(
                        "ingest",
                        SignIn(
                            first + SPRAY_INTERVAL * index,
                            False,
                            email,
                            address,
                            attacker_agent,
                        ),
                    )
                    for index, (email, address) in enumerate(
                        zip(emails, addresses, strict=True)
                    )
                ],
                ip_addresses=frozenset(addresses),
                evasion="The rule counts emails per address, and each address "
                "tries one",
            )
        )

    for n, person in enumerate(organization.active[20:25]):
        ip = f"203.0.113.{140 + n}"
        attacks.append(
            Attack(
                name=f"copied-user-agent-{n + 1}",
                technique="T1078",
                alert_type="unfamiliar_sign_in",
                description="A sign-in with the stolen password of an active "
                "account, from the attacker's network, sending the victim's own "
                "user agent",
                steps=[
                    Step(
                        "ingest",
                        SignIn(
                            now - timedelta(minutes=85 - n),
                            True,
                            person.email,
                            ip,
                            user_agent(person.laptop, 0),
                        ),
                    )
                ],
                emails=frozenset({person.email}),
                evasion="The device looks known, and the rule needs both a new "
                "network and a new device",
            )
        )

    for n, person in enumerate(organization.idle):
        ip = f"203.0.113.{160 + n}"
        attacks.append(
            Attack(
                name=f"idle-account-{n + 1}",
                technique="T1078",
                alert_type="dormant_account_login",
                description="A sign-in with the stolen password of an account "
                f"unused for {IDLE_DAYS} days, from the attacker's network and "
                "computer",
                steps=[
                    Step(
                        "ingest",
                        SignIn(
                            now - timedelta(minutes=78 - n),
                            True,
                            person.email,
                            ip,
                            attacker_agent,
                        ),
                    )
                ],
                emails=frozenset({person.email}),
                evasion=f"{IDLE_DAYS} days is under the 90-day threshold, and the "
                "account has too few recent sign-ins for the unfamiliar sign-in "
                "rule to judge it",
            )
        )
    return attacks
