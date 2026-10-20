"""Plays a simulation against a running SentinelCore and records what
happened, without judging it (that is evaluation.py's job).

1. Invite the organization's people and report their thirty days of
   routine through ingestion, oldest first. When the simulator can send from
   other addresses, invite a neighbour organization's people too, and let
   people of both mistype their password behind a shared VPN. Then collect
   every alert raised.
2. Play the attacks one at a time and one step at a time. After each step,
   collect the new alerts, so the step that raised an alert is known.
3. Revoke the simulator's API key, whatever happened.
"""

import random
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from simulator.attacks import (
    NEIGHBOUR_PEOPLE,
    Attack,
    Step,
    plan_attacks,
    plan_shared_vpn,
)
from simulator.client import SentinelCore
from simulator.population import (
    BenignCase,
    Organization,
    Person,
    build_organization,
    make_people,
)

NEIGHBOUR_DOMAIN = "neighbour.example.com"


@dataclass
class StepResult:
    occurred_at: datetime
    latency_ms: float
    alert_ids: list[int]


@dataclass
class AttackRun:
    attack: Attack
    steps: list[StepResult] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)


@dataclass
class Observations:
    seed: int
    started_at: datetime
    # Alerts from before the run change how rules that count from their latest
    # alert (password spray, brute force) behave.
    earlier_alerts: bool
    finished_at: datetime
    people: int
    routine_sign_ins: int
    routine_failures: int
    routine_ingest_ms: float
    cases: list[BenignCase]
    routine_alerts: list[dict]
    attack_runs: list[AttackRun]


def play_step(api: SentinelCore, step: Step) -> tuple[datetime, float]:
    """Sends `step`; returns when it happened and how long the request took."""
    if step.kind == "ingest" and step.sign_in is not None:
        return step.sign_in.occurred_at, api.ingest([step.sign_in.payload()])
    sent_at = datetime.now(UTC)
    if step.kind == "wrong_password" and step.email is not None:
        return sent_at, api.sign_in_with_wrong_password(step.email, step.address)
    if step.kind == "grant_admin" and step.user_id is not None:
        return sent_at, api.grant_admin(step.user_id)
    raise ValueError(f"Incomplete {step.kind} step")


def add_neighbour(
    api: SentinelCore, seed: int, tag: str, organization: Organization
) -> list[Person]:
    """A second organization, with people and nothing else, for the sprays
    across organizations. Its people come from a generator of their own, so
    the first organization and the attacks stay what the seed made them."""
    # Simulated behaviour, not a secret.
    rng = random.Random(seed + 1)  # nosec B311
    taken = frozenset(person.handle for person in organization.people)
    people = make_people(rng, tag, NEIGHBOUR_PEOPLE, NEIGHBOUR_DOMAIN, taken=taken)
    neighbour_id = api.create_organization(
        f"Simulation {tag} neighbour", f"sim-{tag}-neighbour"
    )
    for person in people:
        api.add_person(
            f"{person.handle}.{tag}",
            person.email,
            person.password,
            organization_id=neighbour_id,
        )
    return people


def simulate(api: SentinelCore, seed: int) -> Observations:
    """Runs the simulation through `api`, already signed in as an owner.

    Without `api.from_address`, every request comes from the simulator's own
    address, so the sprays across organizations are left out."""
    # Simulated behaviour, not a secret: a seed must give the same run.
    rng = random.Random(seed)  # nosec B311
    started_at = datetime.now(UTC)
    # Keeps this run's accounts apart from an earlier run's on the same database.
    tag = secrets.token_hex(3)
    organization = build_organization(rng, started_at, tag)
    last_id = api.latest_alert_id()
    earlier_alerts = last_id > 0

    organization_id = api.create_organization(f"Simulation {tag}", f"sim-{tag}")
    key_id = api.create_api_key(organization_id)
    try:
        user_ids = {
            person.email: api.add_person(
                f"{person.handle}.{tag}",
                person.email,
                person.password,
                organization_id=organization_id,
            )
            for person in organization.people
        }
        routine = [sign_in.payload() for sign_in in organization.sign_ins]
        ingest_started = time.perf_counter()
        api.ingest(routine)
        routine_ms = (time.perf_counter() - ingest_started) * 1000
        cases = list(organization.cases)
        neighbour = None
        if api.from_address is not None:
            neighbour = add_neighbour(api, seed, tag, organization)
            vpn, typos = plan_shared_vpn(organization, neighbour)
            for step in typos:
                play_step(api, step)
            cases.append(vpn)
        routine_alerts = api.alerts_after(last_id)
        if routine_alerts:
            last_id = routine_alerts[-1]["id"]

        runs = []
        attacks = plan_attacks(rng, started_at, organization, user_ids, neighbour)
        for attack in attacks:
            run = AttackRun(attack)
            for step in attack.steps:
                occurred_at, latency_ms = play_step(api, step)
                new_alerts = api.alerts_after(last_id)
                if new_alerts:
                    last_id = new_alerts[-1]["id"]
                run.steps.append(
                    StepResult(
                        occurred_at, latency_ms, [alert["id"] for alert in new_alerts]
                    )
                )
                run.alerts += new_alerts
            runs.append(run)
    finally:
        api.revoke_api_key(key_id)
        api.close_senders()

    return Observations(
        seed=seed,
        started_at=started_at,
        earlier_alerts=earlier_alerts,
        finished_at=datetime.now(UTC),
        people=len(organization.people),
        routine_sign_ins=sum(sign_in.succeeded for sign_in in organization.sign_ins),
        routine_failures=sum(
            not sign_in.succeeded for sign_in in organization.sign_ins
        ),
        routine_ingest_ms=routine_ms,
        cases=cases,
        routine_alerts=routine_alerts,
        attack_runs=runs,
    )
