"""Security headers on every response (threat model T-01, T-03).

The API answers with JSON, which a browser never has to run as a page, so its
policy allows nothing: no scripts, no styles, no framing. Swagger UI and ReDoc
are pages: they load their code from a CDN and Swagger UI starts with an
inline script, so those pages get a policy that allows exactly that code.
"""

import base64
import hashlib
import re
from collections.abc import Awaitable, Callable

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

API_POLICY = "default-src 'none'; frame-ancestors 'none'"

# FastAPI's default docs_url, its OAuth2 redirect page and redoc_url.
DOCUMENTATION_PAGES = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})
# The packages FastAPI loads them from. A whole CDN would let an injected tag
# load any package published on npm.
SWAGGER_UI = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/"
REDOC = "https://cdn.jsdelivr.net/npm/redoc@2/"

_INLINE_SCRIPT = re.compile(rb"<script>(.*?)</script>", re.DOTALL)


def common_headers(hsts_max_age: int) -> dict[str, str]:
    """The headers every response carries, besides its policy."""
    headers = {
        # A response is only what its Content-Type says, never sniffed as HTML.
        "X-Content-Type-Options": "nosniff",
        # frame-ancestors, for browsers that predate it.
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        # Security data stays out of the browser's and proxies' caches.
        "Cache-Control": "no-store",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
        "Cross-Origin-Opener-Policy": "same-origin",
    }
    if hsts_max_age > 0:
        headers["Strict-Transport-Security"] = f"max-age={hsts_max_age}"
    return headers


def _script_hash(script: bytes) -> str:
    digest = base64.b64encode(hashlib.sha256(script).digest()).decode()
    return f"'sha256-{digest}'"


def documentation_policy(page: bytes) -> str:
    """The policy for a documentation page: its CDN code and its own inline
    scripts, named by hash, so no other inline script can run."""
    scripts = [SWAGGER_UI, REDOC, *map(_script_hash, _INLINE_SCRIPT.findall(page))]
    return "; ".join(
        [
            "default-src 'none'",
            f"script-src {' '.join(scripts)}",
            # ReDoc and Swagger UI style their elements as they draw them.
            f"style-src {SWAGGER_UI} https://fonts.googleapis.com 'unsafe-inline'",
            "font-src https://fonts.gstatic.com",
            # FastAPI's favicon and ReDoc's logo.
            "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly",
            "connect-src 'self'",
            # ReDoc searches in a worker it creates from a blob.
            "worker-src blob:",
            "frame-ancestors 'none'",
            "base-uri 'none'",
            "form-action 'none'",
        ]
    )


class SecurityHeadersMiddleware:
    """Adds the headers to every HTTP response the application produces."""

    def __init__(
        self, app: ASGIApp, hsts_max_age: int = 0, documentation: bool = False
    ) -> None:
        self.app = app
        self.headers = common_headers(hsts_max_age)
        # Without the documentation, its paths are unknown ones like any other,
        # and answer with the API's policy.
        self.documentation_pages = DOCUMENTATION_PAGES if documentation else frozenset()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["path"] in self.documentation_pages:
            await self._documentation_page(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                self._add_headers(message, API_POLICY)
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _add_headers(self, start: Message, policy: str) -> None:
        headers = MutableHeaders(scope=start)
        headers["Content-Security-Policy"] = policy
        for name, value in self.headers.items():
            headers[name] = value

    async def _documentation_page(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        # The policy names the page's inline scripts by hash, so the page is
        # held until its body is complete. These pages are a few kilobytes.
        start: Message = {}
        body = bytearray()

        async def send_when_complete(message: Message) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                start = message
            elif message["type"] == "http.response.body":
                body.extend(message.get("body", b""))
                if not message.get("more_body", False):
                    self._add_headers(start, documentation_policy(bytes(body)))
                    await send(start)
                    await send({"type": "http.response.body", "body": bytes(body)})
            else:
                await send(message)

        await self.app(scope, receive, send_when_complete)


def internal_error_handler(
    hsts_max_age: int,
) -> Callable[[Request, Exception], Awaitable[Response]]:
    """The answer to an unhandled error, with the headers.

    Starlette answers such an error outside every middleware, in
    ServerErrorMiddleware, so the headers cannot come from the middleware.
    """
    headers = {"Content-Security-Policy": API_POLICY, **common_headers(hsts_max_age)}

    async def internal_error(request: Request, exc: Exception) -> Response:
        return PlainTextResponse(
            "Internal Server Error", status_code=500, headers=headers
        )

    return internal_error
