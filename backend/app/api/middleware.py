import logging
import re
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from app.api.deps import get_client_ip
from app.core.logging import request_id_var
from app.core.metrics import UNMATCHED_ROUTE, record_http_request

REQUEST_ID_HEADER = "X-Request-ID"
# Incoming ids are reused so a request can be traced across services, but only
# when they are short and safe to write into logs and headers.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")

logger = logging.getLogger("sentinelcore.request")


def _route_template(request: Request) -> str:
    # The template (/admin/users/{user_id}) keeps metric labels bounded,
    # unlike the raw path (/admin/users/42).
    route = request.scope.get("route")
    return getattr(route, "path", UNMATCHED_ROUTE)


async def observe_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    incoming_id = request.headers.get(REQUEST_ID_HEADER)
    if incoming_id is not None and _VALID_REQUEST_ID.fullmatch(incoming_id):
        request_id = incoming_id
    else:
        request_id = uuid4().hex

    context_token = request_id_var.set(request_id)
    started = time.perf_counter()
    # Stays 500 if the endpoint raises before producing a response.
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    finally:
        duration = time.perf_counter() - started
        route = _route_template(request)
        record_http_request(request.method, route, status_code, duration)
        logger.info(
            "Request completed",
            extra={
                "method": request.method,
                "route": route,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 2),
                "client_ip": get_client_ip(request),
            },
        )
        request_id_var.reset(context_token)
