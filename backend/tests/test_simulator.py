import random
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.api_key import ApiKey
from app.schemas.user import UserCreate
from app.services.user_service import create_owner
from simulator.__main__ import main
from simulator.attacks import Attack, Step
from simulator.client import SentinelCore
from simulator.evaluation import evaluate
from simulator.population import (
    BenignCase,
    SignIn,
    build_organization,
)
from simulator.report import to_json, to_markdown
from simulator.runner import AttackRun, Observations, StepResult, simulate

OWNER_EMAIL = "owner@example.com"
OWNER_PASSWORD = "owner-password-1"
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


@pytest.fixture()
def api(client: TestClient, db_session: Session) -> SentinelCore:
    # As `python -m app.cli create-owner` does.
    create_owner(
        db_session,
        UserCreate(username="owner", email=OWNER_EMAIL, password=OWNER_PASSWORD),
    )
    api = SentinelCore(client)
    api.log_in_owner(OWNER_EMAIL, OWNER_PASSWORD)
    return api


# The whole simulation, in-process


def test_every_attack_is_detected_and_every_false_positive_is_explained(
    api: SentinelCore,
    db_session: Session,
) -> None:
    evaluation = evaluate(simulate(api, seed=7))

    assert evaluation.attacks == 25
    assert evaluation.detected == 25
    expected_steps = {
        "password_spray_detected": settings.detection_spray_min_accounts,
        "brute_force_detected": settings.login_max_failed_attempts,
        "dormant_account_login": 1,
        "unfamiliar_sign_in": 1,
        "privileged_role_granted": 1,
    }
    for detection in evaluation.detections:
        if detection.evasion is None:
            assert detection.steps_to_detect == expected_steps[detection.alert_type]
    assert {rule.detected for rule in evaluation.rules} == {5}
    # The rules' known limits: every evasive variant passes, unseen by any rule.
    assert {(e.variant, e.attacks, e.detected) for e in evaluation.evasions} == {
        ("slow-spray", 5, 0),
        ("distributed-spray", 5, 0),
        ("copied-user-agent", 5, 0),
        ("idle-account", 5, 0),
    }
    # Only the benign cases that the rules' design cannot tell from attacks.
    assert Counter(fp.cause for fp in evaluation.false_positives) == {
        "new_laptop_on_a_trip": 1,
        "back_from_leave": 1,
        "password_change_day": 1,
    }
    assert all(case.as_expected for case in evaluation.cases)
    # The simulator's key does not outlive the run.
    keys = db_session.scalars(select(ApiKey)).all()
    assert [key.revoked_at is not None for key in keys] == [True]


# The organization


def test_a_seed_always_gives_the_same_organization() -> None:
    first = build_organization(random.Random(3), NOW, "tag")
    second = build_organization(random.Random(3), NOW, "tag")

    assert first.sign_ins == second.sign_ins
    assert [p.email for p in first.people] == [p.email for p in second.people]


def test_the_history_is_in_the_past_and_within_what_ingestion_accepts() -> None:
    organization = build_organization(random.Random(3), NOW, "tag")

    times = [sign_in.occurred_at for sign_in in organization.sign_ins]
    assert times == sorted(times)
    assert max(times) < NOW
    assert min(times) > NOW - timedelta(days=365)


def test_passwords_stay_out_of_reprs() -> None:
    organization = build_organization(random.Random(3), NOW, "tag")
    person = organization.active[0]

    assert person.password not in repr(person)


# Evaluation


def ingest(at: datetime, email: str = "victim@example.com") -> Step:
    return Step("ingest", SignIn(at, False, email, "203.0.113.5", None))


def alert(alert_id: int, event_type: str, **fields) -> dict:
    return {
        "id": alert_id,
        "event_type": event_type,
        "email": None,
        "ip_address": None,
        "target_user_id": None,
        "message": f"alert {alert_id}",
        **fields,
    }


def observations(runs: list[AttackRun], routine_alerts: list[dict]) -> Observations:
    return Observations(
        seed=1,
        started_at=NOW,
        earlier_alerts=False,
        finished_at=NOW + timedelta(seconds=5),
        people=2,
        routine_sign_ins=90,
        routine_failures=10,
        routine_ingest_ms=100.0,
        cases=[
            BenignCase(
                "office",
                "office",
                None,
                ip_addresses=frozenset({"192.0.2.10"}),
            )
        ],
        routine_alerts=routine_alerts,
        attack_runs=runs,
    )


def spray(name: str = "spray-1") -> Attack:
    return Attack(
        name=name,
        technique="T1110.003",
        alert_type="password_spray_detected",
        description="spray",
        steps=[ingest(NOW + timedelta(seconds=30 * n)) for n in range(3)],
        ip_addresses=frozenset({"203.0.113.5"}),
    )


def test_detection_is_timed_from_the_first_step_to_the_one_that_raised_it() -> None:
    caught = alert(5, "password_spray_detected", ip_address="203.0.113.5")
    run = AttackRun(
        spray(),
        steps=[
            StepResult(NOW, 10.0, []),
            StepResult(NOW + timedelta(seconds=30), 12.0, []),
            StepResult(NOW + timedelta(seconds=60), 14.0, [5]),
        ],
        alerts=[caught],
    )

    [detection] = evaluate(observations([run], [])).detections

    assert detection.detected
    assert detection.steps_to_detect == 3
    assert detection.seconds_to_detect == 60
    assert detection.latency_ms == 14.0


def test_an_alert_that_names_something_else_does_not_count_as_detection() -> None:
    elsewhere = alert(5, "password_spray_detected", ip_address="198.51.100.1")
    run = AttackRun(
        spray(),
        steps=[StepResult(NOW, 10.0, [5])],
        alerts=[elsewhere],
    )

    evaluation = evaluate(observations([run], []))

    assert not evaluation.detections[0].detected
    assert evaluation.detection_rate == 0
    assert [fp.cause for fp in evaluation.false_positives] == ["during spray-1"]
    assert evaluation.precision == 0


def evasive_spray() -> Attack:
    return Attack(
        name="slow-spray-1",
        technique="T1110.003",
        alert_type="password_spray_detected",
        description="slow spray",
        steps=[ingest(NOW + timedelta(minutes=2 * n)) for n in range(3)],
        ip_addresses=frozenset({"203.0.113.5"}),
        evasion="too slow",
    )


def test_an_evasion_is_caught_by_any_alert_that_names_it() -> None:
    # Not the rule it passes under, but another one that names its address.
    other = alert(5, "unfamiliar_sign_in", ip_address="203.0.113.5")
    run = AttackRun(
        evasive_spray(),
        steps=[StepResult(NOW, 10.0, []), StepResult(NOW, 10.0, [5])],
        alerts=[other],
    )

    evaluation = evaluate(observations([run], []))

    [detection] = evaluation.detections
    assert detection.detected
    assert detection.caught_by == "unfamiliar_sign_in"
    assert evaluation.false_positives == []
    [summary] = evaluation.evasions
    assert (summary.variant, summary.detected, summary.caught_by) == (
        "slow-spray",
        1,
        ["unfamiliar_sign_in"],
    )


def test_evasions_are_counted_apart_from_the_detection_rate() -> None:
    caught = AttackRun(
        spray(),
        steps=[StepResult(NOW, 10.0, [5])],
        alerts=[alert(5, "password_spray_detected", ip_address="203.0.113.5")],
    )
    missed = AttackRun(evasive_spray(), steps=[StepResult(NOW, 10.0, [])])

    evaluation = evaluate(observations([caught, missed], []))

    assert (evaluation.attacks, evaluation.detected) == (1, 1)
    assert evaluation.detection_rate == 1
    assert (evaluation.evasive_attacks, evaluation.evasive_detected) == (1, 0)
    [rule] = [r for r in evaluation.rules if r.alert_type == "password_spray_detected"]
    assert rule.attacks == 1
    markdown = to_markdown(evaluation)
    assert "**Evasive variants detected:** 0 of 1" in markdown
    assert (
        "| `slow-spray` | T1110.003 | Password spray | too slow | 0/1 | — |" in markdown
    )
    assert "| slow-spray-1 *(evasive)* |" in markdown


def test_routine_alerts_are_false_positives_put_down_to_their_case() -> None:
    routine = [
        alert(1, "password_spray_detected", ip_address="192.0.2.10"),
        alert(2, "unfamiliar_sign_in", email="nobody@example.com"),
    ]

    evaluation = evaluate(observations([], routine))

    assert [fp.cause for fp in evaluation.false_positives] == ["office", "unexplained"]
    assert evaluation.false_positives_per_1000_sign_ins == 20
    [office] = evaluation.cases
    assert office.alerts == ["password_spray_detected"]
    assert not office.as_expected


def test_the_report_has_every_rule_and_attack() -> None:
    run = AttackRun(
        spray(),
        steps=[StepResult(NOW, 10.0, [5])],
        alerts=[alert(5, "password_spray_detected", ip_address="203.0.113.5")],
    )
    evaluation = evaluate(observations([run], []))

    markdown = to_markdown(evaluation)
    assert "| Password spray | T1110.003 | 1/1 (100%) |" in markdown
    assert "| Brute force | T1110.001 | 0/0 (0%) |" in markdown
    assert "| spray-1 | T1110.003 | spray | yes | 1 of 3 |" in markdown
    assert '"detection_rate": 1.0' in to_json(evaluation)


def test_the_report_warns_when_the_database_was_not_fresh() -> None:
    fresh = evaluate(observations([], []))
    reused = evaluate(observations([], []))
    reused.earlier_alerts = True

    assert "Not a fresh database" not in to_markdown(fresh)
    assert "Not a fresh database" in to_markdown(reused)


def test_a_run_on_a_used_database_says_so_and_a_fresh_one_is_timed(
    api: SentinelCore,
) -> None:
    first = evaluate(simulate(api, seed=7))
    second = evaluate(simulate(api, seed=7))

    assert not first.earlier_alerts
    assert second.earlier_alerts
    # On a fresh database, the tenth email of a spray is tried nine intervals
    # after the first: detection is timed in attack time.
    [spray] = [r for r in first.rules if r.alert_type == "password_spray_detected"]
    assert spray.median_seconds_to_detect == 9 * 30
    assert spray.median_latency_ms is not None


# Command line


def test_the_simulator_refuses_hosts_other_than_localhost(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["--base-url", "https://example.com", "--owner-email", OWNER_EMAIL])

    assert code == 2
    assert "Refusing to attack example.com" in capsys.readouterr().err
