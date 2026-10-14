import base64
import hashlib
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.api.deps import get_db
from app.api.security_headers import SecurityHeadersMiddleware
from app.main import app

COMMON_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cache-control": "no-store",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "cross-origin-opener-policy": "same-origin",
}
SWAGGER_UI = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/"
REDOC = "https://cdn.jsdelivr.net/npm/redoc@2/"


def directives(policy: str) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for directive in policy.split(";"):
        name, *sources = directive.split()
        parsed[name] = sources
    return parsed


def assert_api_headers(headers: dict[str, str]) -> None:
    assert (
        headers["content-security-policy"]
        == "default-src 'none'; frame-ancestors 'none'"
    )
    for name, value in COMMON_HEADERS.items():
        assert headers[name] == value, name
    assert "strict-transport-security" not in headers


def inline_scripts(page: str) -> list[str]:
    return re.findall(r"<script>(.*?)</script>", page, re.DOTALL)


def sha256_source(script: str) -> str:
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    return f"'sha256-{digest}'"


# API responses


@pytest.mark.parametrize(
    ("method", "path", "status_code"),
    [
        ("GET", "/health", 200),
        ("GET", "/users/me", 401),
        ("GET", "/no-such-page", 404),
        ("DELETE", "/health", 405),
        ("POST", "/auth/login", 422),
    ],
)
def test_an_api_response_lets_nothing_run_or_frame_it(
    client: TestClient, method: str, path: str, status_code: int
) -> None:
    response = client.request(method, path, json={})

    assert response.status_code == status_code
    assert_api_headers(dict(response.headers))


def test_an_unhandled_error_carries_the_headers_too() -> None:
    def unreachable_database() -> Session:
        raise RuntimeError("the database is unreachable")

    app.dependency_overrides[get_db] = unreachable_database
    try:
        with TestClient(app, raise_server_exceptions=False) as failing:
            response = failing.get("/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert_api_headers(dict(response.headers))


# Documentation pages


@pytest.mark.parametrize("page", ["/docs", "/docs/oauth2-redirect"])
def test_swagger_ui_runs_its_own_inline_script_and_no_other(
    client: TestClient, page: str
) -> None:
    response = client.get(page)

    assert response.status_code == 200
    scripts = inline_scripts(response.text)
    assert scripts
    script_src = directives(response.headers["content-security-policy"])["script-src"]
    for script in scripts:
        assert sha256_source(script) in script_src
    assert "'unsafe-inline'" not in script_src
    # The package, not the whole CDN.
    assert SWAGGER_UI in script_src
    assert "https://cdn.jsdelivr.net" not in script_src


def test_redoc_loads_its_package_and_runs_no_inline_script(client: TestClient) -> None:
    response = client.get("/redoc")

    assert response.status_code == 200
    assert inline_scripts(response.text) == []
    script_src = directives(response.headers["content-security-policy"])["script-src"]
    assert REDOC in script_src
    assert "'unsafe-inline'" not in script_src
    assert not any(source.startswith("'sha256-") for source in script_src)


@pytest.mark.parametrize("page", ["/docs", "/redoc"])
def test_a_documentation_page_cannot_be_framed_either(
    client: TestClient, page: str
) -> None:
    response = client.get(page)

    policy = directives(response.headers["content-security-policy"])
    assert policy["default-src"] == ["'none'"]
    assert policy["frame-ancestors"] == ["'none'"]
    assert policy["base-uri"] == ["'none'"]
    for name, value in COMMON_HEADERS.items():
        assert response.headers[name] == value, name


# HSTS


@pytest.mark.parametrize(
    ("max_age", "expected"),
    [(0, None), (31_536_000, "max-age=31536000")],
)
def test_hsts_is_sent_only_once_configured(max_age: int, expected: str | None) -> None:
    async def page(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    served = SecurityHeadersMiddleware(
        Starlette(routes=[Route("/", page)]), hsts_max_age=max_age
    )
    with TestClient(served) as test_client:
        response = test_client.get("/")

    assert response.headers.get("strict-transport-security") == expected
