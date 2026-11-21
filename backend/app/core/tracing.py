"""Traces of each request and of its SQL queries, sent over OTLP/HTTP to the
cluster's OpenTelemetry Collector (observability/), which passes them to
Tempo. On only when OTEL_EXPORTER_OTLP_ENDPOINT is set (create_app)."""

from fastapi import FastAPI
from opentelemetry import propagate
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy.engine import EngineTracer
from opentelemetry.metrics import NoOpMeter
from opentelemetry.propagators.textmap import (
    CarrierT,
    Getter,
    Setter,
    TextMapPropagator,
    default_getter,
    default_setter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from sqlalchemy import Engine

SERVICE_NAME = "sentinelcore-api"
# Not traced: the probes and Prometheus call them every few seconds.
EXCLUDED_URLS = "/health,/metrics"
# What could carry personal data or a secret: the query string (an email, a
# token), the whole URL, the sender's address and its headers. The span keeps
# the method, the route, the path and the status. Old and new names, since
# the instrumentation writes either.
PRIVATE_ATTRIBUTES = frozenset(
    {
        "url.query",
        "url.full",
        "http.url",
        "client.address",
        "client.port",
        "net.peer.ip",
        "net.peer.port",
        "http.client_ip",
        "user_agent.original",
        "user_agent.synthetic.type",
        "http.user_agent",
    }
)
PRIVATE_PREFIXES = ("http.request.header.", "http.response.header.")


class NoPropagation(TextMapPropagator):
    """Reads no trace context from a request, and writes none: a trace
    starts in the API. An empty CompositePropagator would hand the
    instrumentation no context at all, which it cannot start a span from."""

    def extract(
        self,
        carrier: CarrierT,
        context: Context | None = None,
        getter: Getter[CarrierT] = default_getter,
    ) -> Context:
        return context if context is not None else Context()

    def inject(
        self,
        carrier: CarrierT,
        context: Context | None = None,
        setter: Setter[CarrierT] = default_setter,
    ) -> None:
        return None

    @property
    def fields(self) -> set[str]:
        return set()


def is_private(attribute: str) -> bool:
    return attribute in PRIVATE_ATTRIBUTES or attribute.startswith(PRIVATE_PREFIXES)


class DropPrivateAttributes(SpanProcessor):
    """Passes `then` a copy of each finished span without the private
    attributes: an ended span cannot be changed, and the instrumentation
    writes them before any hook runs."""

    def __init__(self, then: SpanProcessor) -> None:
        self._then = then

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        self._then.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        attributes = {
            key: value
            for key, value in (span.attributes or {}).items()
            if not is_private(key)
        }
        self._then.on_end(
            ReadableSpan(
                name=span.name,
                context=span.context,
                parent=span.parent,
                resource=span.resource,
                attributes=attributes,
                events=span.events,
                links=span.links,
                kind=span.kind,
                status=span.status,
                start_time=span.start_time,
                end_time=span.end_time,
                instrumentation_scope=span.instrumentation_scope,
            )
        )

    def shutdown(self) -> None:
        self._then.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._then.force_flush(timeout_millis)


def otlp_exporter(endpoint: str) -> SpanExporter:
    return OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces", timeout=5)


def instrument(app: FastAPI, engine: Engine, exporter: SpanExporter) -> TracerProvider:
    """Traces `app`'s requests and `engine`'s queries into `exporter`.

    Spans leave in batches, from a thread of their own: a Collector that is
    down costs dropped spans, never a slower or failed request.
    """
    # A trace starts here: a traceparent header sent from outside could
    # otherwise join a request to a trace the sender chose.
    propagate.set_global_textmap(NoPropagation())
    # service.name here; service.version, the environment and the pod's name
    # from OTEL_RESOURCE_ATTRIBUTES, which the Helm chart sets.
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    provider.add_span_processor(
        DropPrivateAttributes(
            BatchSpanProcessor(
                exporter, max_queue_size=2048, export_timeout_millis=5000
            )
        )
    )
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls=EXCLUDED_URLS,
        # The ASGI send and receive steps of each request: noise.
        exclude_spans=["receive", "send"],
    )
    # The engine's own listeners, not SQLAlchemyInstrumentor: that one
    # declares SQLAlchemy < 2.1 and does nothing on 2.1, and with its check
    # skipped it imports sqlalchemy.ext.asyncio, which needs greenlet. The
    # engine events EngineTracer listens to are unchanged in 2.1.
    # shortcut: EngineTracer is the instrumentation's own module, not its
    # documented entry point; back to SQLAlchemyInstrumentor().instrument(
    # engine=...) once a release declares SQLAlchemy 2.1.
    EngineTracer(
        provider.get_tracer("opentelemetry.instrumentation.sqlalchemy"),
        engine,
        NoOpMeter("sentinelcore").create_up_down_counter("db.client.connections.usage"),
    )
    return provider
