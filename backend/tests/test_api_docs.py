"""The API's documentation pages and schema, served only when
API_DOCS_ENABLED turns them on (threat model T-58).

Each test builds its own application, so none depends on the local `.env`.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from tests.conftest import build_app

DOCUMENTATION = ["/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"]


def serve(*, api_docs_enabled: bool) -> TestClient:
    return TestClient(build_app(api_docs_enabled=api_docs_enabled))


def test_the_documentation_is_off_unless_turned_on() -> None:
    assert Settings.model_fields["api_docs_enabled"].default is False


@pytest.mark.parametrize("path", DOCUMENTATION)
def test_turned_off_the_documentation_is_not_found(path: str) -> None:
    response = serve(api_docs_enabled=False).get(path)

    assert response.status_code == 404


def test_turned_off_each_documentation_url_is_off_in_its_own_right() -> None:
    # FastAPI serves the pages only along with the schema; each is still
    # turned off, should that ever change.
    off = build_app(api_docs_enabled=False)

    assert (off.docs_url, off.redoc_url, off.openapi_url) == (None, None, None)


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_turned_off_the_documentation_answers_like_any_unknown_path(
    path: str,
) -> None:
    client = serve(api_docs_enabled=False)
    # The same request id, so that header matches too.
    same_request = {"X-Request-ID": "documentation-off"}

    documentation = client.get(path, headers=same_request)
    unknown = client.get("/no-such-page", headers=same_request)

    assert documentation.status_code == unknown.status_code
    assert documentation.content == unknown.content
    assert documentation.headers == unknown.headers


@pytest.mark.parametrize("path", DOCUMENTATION)
def test_turned_on_the_documentation_is_served(path: str) -> None:
    response = serve(api_docs_enabled=True).get(path)

    assert response.status_code == 200
