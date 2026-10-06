import json
import logging
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.logging import JsonFormatter, TextFormatter, request_id_var
from app.main import app
from app.models.user import User, UserRole


def metric_value(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def request_count(method: str, route: str, status_code: str) -> float:
    return metric_value(
        "sentinelcore_http_requests_total",
        method=method,
        route=route,
        status_code=status_code,
    )


def security_event_count(event_type: str, severity: str) -> float:
    return metric_value(
        "sentinelcore_security_events_total",
        event_type=event_type,
        severity=severity,
    )


def register(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword",
        },
    )
    assert response.status_code == 201


def _raise_operational_error(*args: object, **kwargs: object) -> None:
    raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def override_db_with_failing_execute(db_session: Session) -> None:
    def broken_db() -> Generator[Session]:
        db_session.execute = _raise_operational_error  # type: ignore[method-assign]
        yield db_session

    app.dependency_overrides[get_db] = broken_db


# Request ids


def test_request_id_is_generated_when_missing(client: TestClient) -> None:
    response = client.get("/health")

    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32
    int(request_id, 16)


def test_valid_incoming_request_id_is_reused(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace-123.abc_DEF"})

    assert response.headers["X-Request-ID"] == "trace-123.abc_DEF"


@pytest.mark.parametrize(
    "incoming",
    ["has spaces", "x" * 65, "bad\nnewline", "semi;colon"],
)
def test_unsafe_incoming_request_id_is_replaced(
    client: TestClient,
    incoming: str,
) -> None:
    response = client.get("/health", headers={"X-Request-ID": incoming})

    assert response.headers["X-Request-ID"] != incoming
    assert len(response.headers["X-Request-ID"]) == 32


# Request logging


def test_each_request_writes_one_structured_log_record(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="sentinelcore.request"):
        response = client.get("/admin/users/42")

    records = [r for r in caplog.records if r.name == "sentinelcore.request"]
    assert len(records) == 1

    record = records[0]
    assert record.getMessage() == "Request completed"
    assert record.__dict__["method"] == "GET"
    assert record.__dict__["route"] == "/admin/users/{user_id}"
    assert record.__dict__["path"] == "/admin/users/42"
    assert record.__dict__["status_code"] == response.status_code == 401
    assert record.__dict__["duration_ms"] >= 0


def test_logs_written_during_a_request_carry_its_request_id(
    client: TestClient,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    override_db_with_failing_execute(db_session)
    captured: list[str | None] = []

    class CaptureRequestId(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(request_id_var.get())

    handler = CaptureRequestId()
    health_logger = logging.getLogger("app.api.routes.health")
    health_logger.addHandler(handler)
    try:
        response = client.get("/health/ready", headers={"X-Request-ID": "trace-42"})
    finally:
        health_logger.removeHandler(handler)

    assert response.status_code == 503
    assert captured == ["trace-42"]


def test_json_formatter_includes_request_id_and_extra_fields() -> None:
    record = logging.LogRecord(
        "sentinelcore.test",
        logging.INFO,
        __file__,
        1,
        "Something %s",
        ("happened",),
        None,
    )
    record.__dict__["route"] = "/health"

    token = request_id_var.set("abc123")
    try:
        entry = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert entry["level"] == "INFO"
    assert entry["logger"] == "sentinelcore.test"
    assert entry["message"] == "Something happened"
    assert entry["request_id"] == "abc123"
    assert entry["route"] == "/health"
    assert entry["timestamp"].endswith("+00:00")


def test_text_formatter_includes_request_id_and_extra_fields() -> None:
    record = logging.LogRecord(
        "sentinelcore.test", logging.WARNING, __file__, 1, "Careful", None, None
    )
    record.__dict__["status_code"] = 503

    token = request_id_var.set("abc123")
    try:
        line = TextFormatter().format(record)
    finally:
        request_id_var.reset(token)

    assert "WARNING" in line
    assert "[abc123]" in line
    assert "sentinelcore.test: Careful" in line
    assert line.endswith("status_code=503")


# HTTP metrics


def test_metrics_use_route_templates_not_raw_paths(client: TestClient) -> None:
    before = request_count("GET", "/admin/users/{user_id}", "401")

    client.get("/admin/users/1")
    client.get("/admin/users/2")

    assert request_count("GET", "/admin/users/{user_id}", "401") == before + 2
    assert (
        metric_value(
            "sentinelcore_http_requests_total",
            method="GET",
            route="/admin/users/1",
            status_code="401",
        )
        == 0
    )


def test_unknown_paths_and_methods_share_bounded_labels(client: TestClient) -> None:
    unmatched_before = request_count("GET", "unmatched", "404")
    other_before = request_count("OTHER", "/health", "405")

    client.get("/no/such/path/123")
    client.get("/another/missing/path")
    client.request("BREW", "/health")

    assert request_count("GET", "unmatched", "404") == unmatched_before + 2
    assert request_count("OTHER", "/health", "405") == other_before + 1


def test_request_duration_is_observed(client: TestClient) -> None:
    before = metric_value(
        "sentinelcore_http_request_duration_seconds_count",
        method="GET",
        route="/health",
    )

    client.get("/health")

    assert (
        metric_value(
            "sentinelcore_http_request_duration_seconds_count",
            method="GET",
            route="/health",
        )
        == before + 1
    )


# Security event metrics


def test_security_events_are_counted(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "login_max_failed_attempts", 2)
    register(client)

    failed_before = security_event_count("login_failed", "warn")
    incident_before = security_event_count("brute_force_detected", "incident")
    blocked_before = security_event_count("login_blocked", "warn")

    for _ in range(2):
        client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )
    client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "testpassword"},
    )

    assert security_event_count("login_failed", "warn") == failed_before + 2
    assert security_event_count("brute_force_detected", "incident") == (
        incident_before + 1
    )
    assert security_event_count("login_blocked", "warn") == blocked_before + 1


def test_user_change_security_events_are_counted(
    client: TestClient,
    db_session: Session,
) -> None:
    for username in ("owneruser", "targetuser"):
        client.post(
            "/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "testpassword",
            },
        )
    owner = db_session.scalar(select(User).where(User.username == "owneruser"))
    target = db_session.scalar(select(User).where(User.username == "targetuser"))
    assert owner is not None and target is not None
    owner.role = UserRole.OWNER
    db_session.commit()

    token = client.post(
        "/auth/login",
        json={"email": "owneruser@example.com", "password": "testpassword"},
    ).json()["access_token"]
    before = security_event_count("user_deactivated", "info")

    response = client.patch(
        f"/admin/users/{target.id}/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert security_event_count("user_deactivated", "info") == before + 1


# /metrics endpoint


def test_metrics_endpoint_is_open_without_configured_token(
    client: TestClient,
) -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "sentinelcore_http_requests_total" in response.text


@pytest.mark.parametrize("configured", [None, ""])
def test_empty_metrics_token_means_no_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    configured: str | None,
) -> None:
    monkeypatch.setattr(
        settings,
        "metrics_token",
        None if configured is None else SecretStr(configured),
    )

    assert client.get("/metrics").status_code == 200


@pytest.mark.parametrize(
    ("authorization", "expected_status"),
    [
        (None, 401),
        ("Bearer wrong-token", 401),
        ("s3cret-token", 401),
        ("Bearer s3cret-token", 200),
    ],
)
def test_metrics_endpoint_requires_configured_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    authorization: str | None,
    expected_status: int,
) -> None:
    monkeypatch.setattr(settings, "metrics_token", SecretStr("s3cret-token"))
    headers = {"Authorization": authorization} if authorization else {}

    response = client.get("/metrics", headers=headers)

    assert response.status_code == expected_status
    if expected_status == 401:
        assert response.headers["WWW-Authenticate"] == "Bearer"


def test_metrics_endpoint_is_not_in_openapi_schema(client: TestClient) -> None:
    assert "/metrics" not in client.get("/openapi.json").json()["paths"]


# Health checks


def test_readiness_reports_database_ok(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_readiness_reports_unavailable_database(
    client: TestClient,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    override_db_with_failing_execute(db_session)

    with caplog.at_level(logging.ERROR, logger="app.api.routes.health"):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    assert "database unavailable" in caplog.text
    # Liveness does not depend on the database.
    assert client.get("/health").status_code == 200
