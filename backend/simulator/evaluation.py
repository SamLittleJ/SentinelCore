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
- Evasive variants are counted apart: the detection rate is that of the
  attacks the rules are built for, and the evasions have their own, with the
  reason each one passes.
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
    # The alert that caught it, which for an evasion can be any rule's.
    caught_by: str | None = None
    variant: str = ""
    evasion: str | None = None


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
class EvasionSummary:
    variant: str
    technique: str
    # The alert of the rule the variant is built to pass under.
    evades: str
    evasion: str
    attacks: int
    detected: int
    caught_by: list[str]


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
    evasive_attacks: int
    evasive_detected: int
    alerts: int
    precision: float
    false_positives_per_1000_sign_ins: float
    rules: list[RuleSummary]
    evasions: list[EvasionSummary]
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
        variant=attack.variant,
        evasion=attack.evasion,
    )
    caught = {
        alert["id"]: alert["event_type"]
        for alert in run.alerts
        if attack.is_caught_by(alert)
    }
    for index, step in enumerate(run.steps):
        first = next((i for i in step.alert_ids if i in caught), None)
        if first is not None:
            detection.detected = True
            detection.caught_by = caught[first]
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
    all_detections = [detect(run) for run in observations.attack_runs]
    detections = [d for d in all_detections if d.evasion is None]
    evasive = [d for d in all_detections if d.evasion is not None]

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

    evasions = []
    for variant in dict.fromkeys(d.variant for d in evasive):
        mine = [d for d in evasive if d.variant == variant]
        evasions.append(
            EvasionSummary(
                variant=variant,
                technique=mine[0].technique,
                evades=mine[0].alert_type,
                evasion=mine[0].evasion or "",
                attacks=len(mine),
                detected=sum(d.detected for d in mine),
                caught_by=sorted({d.caught_by for d in mine if d.caught_by}),
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
        evasive_attacks=len(evasive),
        evasive_detected=sum(d.detected for d in evasive),
        alerts=alerts,
        precision=true_alerts / alerts if alerts else 0.0,
        false_positives_per_1000_sign_ins=(
            1000 * len(false_positives) / attempts if attempts else 0.0
        ),
        rules=rules,
        evasions=evasions,
        detections=all_detections,
        false_positives=false_positives,
        cases=cases,
    )
