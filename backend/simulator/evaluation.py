"""Turns what a simulation observed into detection metrics.

- An attack is detected when an alert it would raise (Attack.is_caught_by)
  appears while it is played. The first such alert gives its time to detect.
- Every other alert is a false positive: raised by the routine, or by an
  attack but naming something else. Routine alerts are put down to the
  benign case they name, so each one has a cause.
- Time to detect is measured in attack time, from the attack's first step to
  the step after which the alert appeared, and in steps. The pipeline
  latency is the duration of the request that raised the alert; detection
  runs inside it, so the alert exists when the request returns.
"""

from dataclasses import dataclass
from statistics import median

from simulator.client import ALERTS
from simulator.runner import AttackRun, Observations

TECHNIQUES = {alert_type: technique for alert_type, technique, _ in ALERTS}


@dataclass
class Detection:
    attack: str
    technique: str
    alert_type: str
    description: str
    steps: int
    detected: bool
    steps_to_detect: int | None = None
    seconds_to_detect: float | None = None
    latency_ms: float | None = None


@dataclass
class FalsePositive:
    alert_type: str
    technique: str
    cause: str
    message: str


@dataclass
class RuleSummary:
    alert_type: str
    technique: str
    attacks: int
    detected: int
    detection_rate: float
    median_steps_to_detect: float | None
    median_seconds_to_detect: float | None
    max_seconds_to_detect: float | None
    median_latency_ms: float | None
    max_latency_ms: float | None
    false_positives: int


@dataclass
class CaseOutcome:
    name: str
    description: str
    expected_alert: str | None
    alerts: list[str]
    as_expected: bool


@dataclass
class Evaluation:
    seed: int
    started_at: str
    earlier_alerts: bool
    duration_seconds: float
    people: int
    routine_sign_ins: int
    routine_failures: int
    routine_ingest_ms: float
    attacks: int
    detected: int
    detection_rate: float
    alerts: int
    precision: float
    false_positives_per_1000_sign_ins: float
    rules: list[RuleSummary]
    detections: list[Detection]
    false_positives: list[FalsePositive]
    cases: list[CaseOutcome]


def detect(run: AttackRun) -> Detection:
    attack = run.attack
    detection = Detection(
        attack=attack.name,
        technique=attack.technique,
        alert_type=attack.alert_type,
        description=attack.description,
        steps=len(attack.steps),
        detected=False,
    )
    caught = {alert["id"] for alert in run.alerts if attack.is_caught_by(alert)}
    for index, step in enumerate(run.steps):
        if caught & set(step.alert_ids):
            detection.detected = True
            detection.steps_to_detect = index + 1
            elapsed = step.occurred_at - run.steps[0].occurred_at
            detection.seconds_to_detect = elapsed.total_seconds()
            detection.latency_ms = step.latency_ms
            break
    return detection


def cause_of(alert: dict, observations: Observations) -> str:
    for case in observations.cases:
        if alert["email"] in case.emails or alert["ip_address"] in case.ip_addresses:
            return case.name
    return "unexplained"


def middle(values: list[float]) -> float | None:
    return median(values) if values else None


def highest(values: list[float]) -> float | None:
    return max(values) if values else None


def evaluate(observations: Observations) -> Evaluation:
    detections = [detect(run) for run in observations.attack_runs]

    false_positives = [
        FalsePositive(
            alert["event_type"],
            TECHNIQUES.get(alert["event_type"], ""),
            cause_of(alert, observations),
            alert["message"],
        )
        for alert in observations.routine_alerts
    ]
    true_alerts = 0
    for run in observations.attack_runs:
        for alert in run.alerts:
            if run.attack.is_caught_by(alert):
                true_alerts += 1
            else:
                false_positives.append(
                    FalsePositive(
                        alert["event_type"],
                        TECHNIQUES.get(alert["event_type"], ""),
                        f"during {run.attack.name}",
                        alert["message"],
                    )
                )

    rules = []
    for alert_type, technique in TECHNIQUES.items():
        mine = [d for d in detections if d.alert_type == alert_type]
        found = [d for d in mine if d.detected]
        seconds = [
            d.seconds_to_detect for d in found if d.seconds_to_detect is not None
        ]
        steps = [float(d.steps_to_detect) for d in found if d.steps_to_detect]
        latencies = [d.latency_ms for d in found if d.latency_ms is not None]
        rules.append(
            RuleSummary(
                alert_type=alert_type,
                technique=technique,
                attacks=len(mine),
                detected=len(found),
                detection_rate=len(found) / len(mine) if mine else 0.0,
                median_steps_to_detect=middle(steps),
                median_seconds_to_detect=middle(seconds),
                max_seconds_to_detect=highest(seconds),
                median_latency_ms=middle(latencies),
                max_latency_ms=highest(latencies),
                false_positives=sum(
                    fp.alert_type == alert_type for fp in false_positives
                ),
            )
        )

    cases = []
    for case in observations.cases:
        raised = [
            alert["event_type"]
            for alert in observations.routine_alerts
            if cause_of(alert, observations) == case.name
        ]
        expected = [case.expected_alert] if case.expected_alert else []
        cases.append(
            CaseOutcome(
                case.name,
                case.description,
                case.expected_alert,
                raised,
                as_expected=raised == expected,
            )
        )

    detected = sum(d.detected for d in detections)
    alerts = true_alerts + len(false_positives)
    attempts = observations.routine_sign_ins + observations.routine_failures
    return Evaluation(
        seed=observations.seed,
        earlier_alerts=observations.earlier_alerts,
        started_at=observations.started_at.isoformat(timespec="seconds"),
        duration_seconds=(
            observations.finished_at - observations.started_at
        ).total_seconds(),
        people=observations.people,
        routine_sign_ins=observations.routine_sign_ins,
        routine_failures=observations.routine_failures,
        routine_ingest_ms=observations.routine_ingest_ms,
        attacks=len(detections),
        detected=detected,
        detection_rate=detected / len(detections) if detections else 0.0,
        alerts=alerts,
        precision=true_alerts / alerts if alerts else 0.0,
        false_positives_per_1000_sign_ins=(
            1000 * len(false_positives) / attempts if attempts else 0.0
        ),
        rules=rules,
        detections=detections,
        false_positives=false_positives,
        cases=cases,
    )
