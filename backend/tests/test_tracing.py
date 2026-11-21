import io
import json
import logging
from collections.abc import Callable, Generator, Sequence

import pytest
from fastapi.testclient import TestClient
from opentelemetry import propagate
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy.engine import EngineTracer
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core import tracing
from app.core.logging import JsonFormatter
from tests.accounts import PASSWORD, create_account
from tests.conftest import build_app, serve_requests_from, test_engine

EMAIL = "traced@example.com"
Spans = Callable[[], Sequence[ReadableSpan]]


@pytest.fixture()
def traced(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> Generator[tuple[TestClient, Spans]]:
    """An application traced into memory, as the cluster's is into the
    Collector; the instrumentation is removed afterwards. Every header is
    captured, as if someone turned that on: the spans must still drop them."""
    monkeypatch.setenv("OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST", ".*")
    monkeypatch.setenv(
        "OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE", ".*"
    )
    exporter = InMemorySpanExporter()
    app = build_app()
    app.dependency_overrides[get_db] = serve_requests_from(db_session)
    propagator = propagate.get_global_textmap()
    provider = tracing.instrument(app, test_engine, exporter)

    def spans() -> Sequence[ReadableSpan]:
        provider.force_flush()
        return exporter.get_finished_spans()

    try:
        with TestClient(app) as client:
            yield client, spans
    finally:
        FastAPIInstrumentor.uninstrument_app(app)
        EngineTracer.remove_all_event_listeners()
        propagate.set_global_textmap(propagator)
        provider.shutdown()


def server_span(spans: Sequence[ReadableSpan]) -> ReadableSpan:
    (span,) = [span for span in spans if span.kind == SpanKind.SERVER]
    assert span.context is not None
    return span


def trace_of(span: ReadableSpan) -> int:
    assert span.context is not None
    return span.context.trace_id


def sign_in(client: TestClient, headers: dict[str, str] | None = None):
    create_account("traced", EMAIL, PASSWORD)
    return client.post(
        "/auth/login", json={"email": EMAIL, "password": PASSWORD}, headers=headers
    )


def test_a_request_is_traced_with_its_sql_and_its_request_id(
    traced: tuple[TestClient, Spans],
) -> None:
    client, spans = traced

    response = sign_in(client)

    assert response.status_code == 200
    finished = spans()
    request = server_span(finished)
    assert request.name == "POST /auth/login"
    assert request.attributes is not None
    assert request.attributes["http.route"] == "/auth/login"
    assert (
        request.attributes["sentinelcore.request_id"]
        == response.headers["X-Request-ID"]
    )
    assert request.resource.attributes["service.name"] == "sentinelcore-api"
    # The account was created before, outside the request.
    queries = [
        span
        for span in finished
        if span.kind == SpanKind.CLIENT and trace_of(span) == trace_of(request)
    ]
    assert all(span.parent is not None for span in queries)
    assert any(
        "users" in str((span.attributes or {}).get("db.statement", ""))
        for span in queries
    )


def test_spans_keep_no_query_string_address_or_header(
    traced: tuple[TestClient, Spans],
) -> None:
    client, spans = traced

    response = client.post(
        f"/auth/login?email={EMAIL}&token=secret-value",
        json={"email": EMAIL, "password": PASSWORD},
        headers={"User-Agent": "TracedBrowser/1.0", "Cookie": "session=secret"},
    )

    assert response.status_code == 401
    finished = spans()
    written = json.dumps([dict(span.attributes or {}) for span in finished])
    for private in (EMAIL, "traced%40example.com", "secret", "TracedBrowser"):
        assert private not in written
    attributes = server_span(finished).attributes or {}
    assert not any(tracing.is_private(key) for key in attributes)
    assert "/auth/login" in written


@pytest.mark.parametrize("path", ["/health", "/health/ready", "/metrics"])
def test_probes_and_metrics_are_not_traced(
    traced: tuple[TestClient, Spans],
    path: str,
) -> None:
    client, spans = traced

    client.get(path)

    assert not [span for span in spans() if span.kind == SpanKind.SERVER]


def test_a_trace_sent_from_outside_is_not_joined(
    traced: tuple[TestClient, Spans],
) -> None:
    client, spans = traced
    outside = "4bf92f3577b34da6a3ce929d0e0e4736"

    sign_in(client, headers={"traceparent": f"00-{outside}-00f067aa0ba902b7-01"})

    request = server_span(spans())
    assert format(trace_of(request), "032x") != outside
    assert request.parent is None


def test_log_lines_carry_the_request_s_trace(
    traced: tuple[TestClient, Spans],
) -> None:
    client, spans = traced
    # Formatted as it is written, inside the request, as in the cluster.
    lines = io.StringIO()
    handler = logging.StreamHandler(lines)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("sentinelcore.request")
    logger.addHandler(handler)
    try:
        sign_in(client)
    finally:
        logger.removeHandler(handler)

    (line,) = [
        entry
        for entry in map(json.loads, lines.getvalue().splitlines())
        if entry["message"] == "Request completed"
    ]
    request = server_span(spans())
    assert line["trace_id"] == format(trace_of(request), "032x")
    assert request.context is not None
    assert line["span_id"] == format(request.context.span_id, "016x")


def test_nothing_is_traced_without_an_endpoint(db_session: Session) -> None:
    app = build_app(otel_exporter_otlp_endpoint=None)

    assert not hasattr(app.state, "tracer_provider")


def test_a_collector_that_is_down_does_not_fail_requests(
    db_session: Session,
) -> None:
    # Nothing listens on port 9: every export fails, in the exporter's thread.
    app = build_app(otel_exporter_otlp_endpoint="http://127.0.0.1:9")
    app.dependency_overrides[get_db] = serve_requests_from(db_session)
    propagator = propagate.get_global_textmap()
    try:
        with TestClient(app) as client:
            create_account("traced", EMAIL, PASSWORD)
            response = client.post(
                "/auth/login", json={"email": EMAIL, "password": PASSWORD}
            )
        assert response.status_code == 200
        assert hasattr(app.state, "tracer_provider")
    finally:
        FastAPIInstrumentor.uninstrument_app(app)
        EngineTracer.remove_all_event_listeners()
        propagate.set_global_textmap(propagator)
        app.state.tracer_provider.shutdown()
