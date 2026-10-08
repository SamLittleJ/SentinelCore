from prometheus_client import Counter, Histogram

from app.models.security_event import SecurityEventType, SecuritySeverity

# Label values must come from small, fixed sets: every distinct combination
# becomes a separate time series in Prometheus.
KNOWN_HTTP_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
)
UNMATCHED_ROUTE = "unmatched"

HTTP_REQUESTS = Counter(
    "sentinelcore_http_requests_total",
    "HTTP requests handled, by route template and status code.",
    ["method", "route", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "sentinelcore_http_request_duration_seconds",
    "Time spent handling HTTP requests, by route template.",
    ["method", "route"],
)

SESSIONS_DELETED = Counter(
    "sentinelcore_sessions_deleted_total",
    "Expired or revoked sessions deleted by the cleanup task.",
)

SECURITY_EVENTS = Counter(
    "sentinelcore_security_events_total",
    "Security events recorded, by type and severity.",
    ["event_type", "severity"],
)

# Labelled by the source of the API key: one series per source an owner
# created a key for, so the label set stays small.
INGESTED_EVENTS = Counter(
    "sentinelcore_ingested_events_total",
    "Security events received through the ingestion endpoint, by source.",
    ["source"],
)


def record_http_request(
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    method = method if method in KNOWN_HTTP_METHODS else "OTHER"
    HTTP_REQUESTS.labels(method=method, route=route, status_code=status_code).inc()
    HTTP_REQUEST_DURATION.labels(method=method, route=route).observe(duration_seconds)


def record_security_event(
    event_type: SecurityEventType,
    severity: SecuritySeverity,
) -> None:
    SECURITY_EVENTS.labels(event_type=event_type.value, severity=severity.value).inc()
