"""Falco's alerts, sent by falcosidekick to POST /ingest/runtime (phase E3).

The alerts in tests/data/falco_alerts.json were sent by falcosidekick on
kind; each test gives them the current time. Each test builds its own
application, with or without FALCO_INGEST_TOKEN, so none depends on the
local `.env`.
"""

import copy
import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings, settings
from app.models.security_event import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from tests.conftest import build_app, serve_requests_from

TOKEN = "falco-ingest-token-for-sentinelcore-tests"
ALERTS = json.loads((Path(__file__).parent / "data" / "falco_alerts.json").read_text())
OUTCOMES = "sentinelcore_runtime_alerts_total"


def alert(name: str, at: datetime | None = None, **changes: Any) -> dict[str, Any]:
    """One of the recorded alerts, at `at` (now by default)."""
    body = copy.deepcopy(ALERTS[name])
    body["time"] = (at or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
    body.update(changes)
    return body


def serve(db_session: Session, token: str | None) -> TestClient:
    app = build_app(falco_ingest_token=SecretStr(token) if token else None)
    app.dependency_overrides[get_db] = serve_requests_from(db_session)
    return TestClient(app)


@pytest.fixture()
def falco(db_session: Session) -> Generator[TestClient]:
    with serve(db_session, TOKEN) as client:
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        yield client


def stored(db_session: Session) -> list[SecurityEvent]:
    return list(
        db_session.scalars(select(SecurityEvent).order_by(SecurityEvent.id)).all()
    )


def outcome(name: str) -> float:
    return REGISTRY.get_sample_value(OUTCOMES, {"outcome": name}) or 0


# The token


def test_without_a_token_the_endpoint_answers_like_any_unknown_path(
    db_session: Session,
) -> None:
    client = serve(db_session, None)
    same_request = {"X-Request-ID": "runtime-off", "Authorization": f"Bearer {TOKEN}"}

    runtime = client.post("/ingest/runtime", json=alert("shell"), headers=same_request)
    unknown = client.post("/no-such-page", json=alert("shell"), headers=same_request)

    assert runtime.status_code == 404
    assert (runtime.content, runtime.headers) == (unknown.content, unknown.headers)
    assert stored(db_session) == []


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer wrong-token", f"Basic {TOKEN}", TOKEN, f"Bearer {TOKEN}x"],
)
def test_a_missing_or_wrong_token_gets_the_same_refusal(
    db_session: Session, authorization: str | None
) -> None:
    client = serve(db_session, TOKEN)
    headers = {"X-Request-ID": "runtime-refused"}
    if authorization is not None:
        headers["Authorization"] = authorization

    response = client.post("/ingest/runtime", json=alert("shell"), headers=headers)
    reference = client.post(
        "/ingest/runtime",
        json=alert("shell"),
        headers={"X-Request-ID": "runtime-refused", "Authorization": "Bearer no"},
    )

    assert response.status_code == 401
    assert (response.content, response.headers) == (
        reference.content,
        reference.headers,
    )
    assert stored(db_session) == []


def test_the_token_is_off_unless_set() -> None:
    assert Settings.model_fields["falco_ingest_token"].default is None


def test_an_empty_token_means_none() -> None:
    changed = Settings.model_validate(
        {**settings.model_dump(), "falco_ingest_token": ""}
    )
    assert changed.falco_ingest_token is None


def test_a_short_token_is_refused() -> None:
    with pytest.raises(ValidationError, match="FALCO_INGEST_TOKEN"):
        Settings.model_validate(
            {**settings.model_dump(), "falco_ingest_token": "x" * 31}
        )


# The alerts kept


@pytest.mark.parametrize(
    ("name", "event_type", "severity", "technique"),
    [
        (
            "shell",
            SecurityEventType.CONTAINER_SHELL_DETECTED,
            SecuritySeverity.INCIDENT,
            "T1059",
        ),
        (
            "sensitive_read",
            SecurityEventType.SENSITIVE_FILE_READ,
            SecuritySeverity.INCIDENT,
            "T1003.008",
        ),
        (
            "network_redirect",
            SecurityEventType.CONTAINER_NETWORK_TOOL,
            SecuritySeverity.WARN,
            "T1059.004",
        ),
    ],
)
def test_each_known_rule_is_stored_as_its_own_platform_alert(
    falco: TestClient,
    db_session: Session,
    name: str,
    event_type: SecurityEventType,
    severity: SecuritySeverity,
    technique: str,
) -> None:
    at = datetime.now(UTC) - timedelta(minutes=3)

    response = falco.post("/ingest/runtime", json=alert(name, at))

    assert response.status_code == 204
    [event] = stored(db_session)
    assert event.event_type == event_type
    assert event.severity == severity
    assert event.mitre_technique == technique
    assert event.source == "falco"
    assert event.organization_id is None
    assert event.occurred_at == at
    fields = ALERTS[name]["output_fields"]
    for value in (
        fields["k8s.ns.name"],
        fields["k8s.pod.name"],
        fields["container.name"],
    ):
        assert value in event.message


def test_the_message_is_the_servers_own(falco: TestClient, db_session: Session) -> None:
    falco.post("/ingest/runtime", json=alert("shell"))

    [event] = stored(db_session)
    assert event.message == (
        "Shell with a terminal in container backend of pod "
        "sentinelcore-backend-5479b6c7f5-j2qnn (namespace sentinelcore)"
    )
    # The command line is the attacker's, and may carry a password.
    assert ALERTS["shell"]["output_fields"]["proc.cmdline"] not in event.message


def test_a_sensitive_read_names_the_file(
    falco: TestClient, db_session: Session
) -> None:
    falco.post("/ingest/runtime", json=alert("sensitive_read"))

    [event] = stored(db_session)
    assert "/etc/shadow" in event.message


def test_a_stored_alert_is_counted(falco: TestClient) -> None:
    before = outcome("stored")
    falco.post("/ingest/runtime", json=alert("shell"))
    assert outcome("stored") == before + 1


# The alerts not kept


def test_an_unknown_rule_is_answered_alike_and_not_stored(
    falco: TestClient, db_session: Session
) -> None:
    before = outcome("ignored")

    ignored = falco.post("/ingest/runtime", json=alert("unknown_rule"))
    kept = falco.post("/ingest/runtime", json=alert("shell"))

    assert (ignored.status_code, ignored.content) == (kept.status_code, kept.content)
    assert [event.event_type for event in stored(db_session)] == [
        SecurityEventType.CONTAINER_SHELL_DETECTED
    ]
    assert outcome("ignored") == before + 1


def test_the_same_alert_within_ten_minutes_is_stored_once(
    falco: TestClient, db_session: Session
) -> None:
    first = datetime.now(UTC) - timedelta(minutes=20)
    before = outcome("duplicate")

    falco.post("/ingest/runtime", json=alert("shell", first))
    again = falco.post(
        "/ingest/runtime", json=alert("shell", first + timedelta(minutes=9))
    )

    assert again.status_code == 204
    assert len(stored(db_session)) == 1
    assert outcome("duplicate") == before + 1


def test_the_same_alert_after_ten_minutes_is_stored_again(
    falco: TestClient, db_session: Session
) -> None:
    first = datetime.now(UTC) - timedelta(minutes=30)

    falco.post("/ingest/runtime", json=alert("shell", first))
    falco.post("/ingest/runtime", json=alert("shell", first + timedelta(minutes=11)))

    assert len(stored(db_session)) == 2


def test_another_pod_is_not_a_duplicate(falco: TestClient, db_session: Session) -> None:
    other = alert("shell")
    other["output_fields"]["k8s.pod.name"] = "sentinelcore-backend-5479b6c7f5-zzzzz"

    falco.post("/ingest/runtime", json=alert("shell"))
    falco.post("/ingest/runtime", json=other)

    assert len(stored(db_session)) == 2


def test_another_rule_on_the_same_pod_is_not_a_duplicate(
    falco: TestClient, db_session: Session
) -> None:
    falco.post("/ingest/runtime", json=alert("shell"))
    falco.post("/ingest/runtime", json=alert("network_redirect"))

    assert len(stored(db_session)) == 2


# What is refused


def test_an_unexpected_field_is_refused(falco: TestClient, db_session: Session) -> None:
    response = falco.post("/ingest/runtime", json=alert("shell", severity="info"))

    assert response.status_code == 422
    assert stored(db_session) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("k8s.pod.name", "Not_A_Pod"),
        ("k8s.pod.name", "a" * 254),
        ("k8s.ns.name", None),
        ("container.name", "../../etc"),
    ],
)
def test_a_known_rule_without_valid_names_is_refused(
    falco: TestClient, db_session: Session, field: str, value: str | None
) -> None:
    body = alert("shell")
    body["output_fields"][field] = value

    assert falco.post("/ingest/runtime", json=body).status_code == 422
    assert stored(db_session) == []


def test_a_sensitive_read_without_a_file_is_refused(
    falco: TestClient, db_session: Session
) -> None:
    body = alert("sensitive_read")
    body["output_fields"]["fd.name"] = None

    assert falco.post("/ingest/runtime", json=body).status_code == 422


@pytest.mark.parametrize(
    "at",
    [
        datetime.now(UTC) + timedelta(hours=1),
        datetime.now(UTC) - timedelta(days=400),
    ],
)
def test_an_alert_out_of_time_is_refused(
    falco: TestClient, db_session: Session, at: datetime
) -> None:
    assert falco.post("/ingest/runtime", json=alert("shell", at)).status_code == 422
    assert stored(db_session) == []
