"""The attacks the simulator plays, one per MITRE ATT&CK technique detected.

Each attack is a list of steps. Most are sign-ins reported through
ingestion, dated during the hour before the run, so their pace is that of a
real attack. Brute force and role changes cannot be reported: the lockout
counts only this application's own sign-ins, and roles change only through
its API. Those steps happen for real, when they are sent.

An attack also says which alert would mean it was caught, and which emails,
addresses or accounts that alert would name.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from simulator.population import (
    ATTACKER_DEVICE,
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
    alert_type: str
    description: str
    steps: list[Step]
    emails: frozenset[str] = frozenset()
    ip_addresses: frozenset[str] = frozenset()
    target_user_ids: frozenset[int] = field(default_factory=frozenset)

    def is_caught_by(self, alert: dict) -> bool:
        return alert["event_type"] == self.alert_type and (
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
    """The attacks, in the order they are played. Each targets people of its
    own, so no attack prepares the ground for another."""
    active = organization.active
    attacker_agent = user_agent(ATTACKER_DEVICE, 0)
    start = now - timedelta(hours=1)
    attacks: list[Attack] = []

    for n in range(ATTACKS_PER_TECHNIQUE):
        ip = f"203.0.113.{10 + n}"
        count = rng.randint(*SPRAY_EMAILS)
        real = rng.sample([person.email for person in active], count - SPRAY_GUESSES)
        guesses = [f"{name}@sim.example.com" for name in ("admin", "it", "hr")]
        emails = rng.sample(real + guesses, count)
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
