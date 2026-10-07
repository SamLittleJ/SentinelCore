import uuid
from collections.abc import Generator

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from app.core.config import settings
from app.core.security import csrf_token_for
from app.main import app
from app.models.security_event import SecurityEvent, SecurityEventType
from app.models.user import User, UserRole

PASSWORD = "testpassword"


@pytest.fixture()
def browser(client: TestClient) -> Generator[TestClient]:
    """A client on https, so Secure cookies are stored and sent back.

    Depends on `client` for the test database override.
    """
    with TestClient(app, base_url="https://testserver") as browser_client:
        yield browser_client


def register(client: TestClient, username: str = "testuser") -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201


def browser_login(browser: TestClient, username: str = "testuser"):
    return browser.post(
        "/auth/session",
        json={"email": f"{username}@example.com", "password": PASSWORD},
    )


def set_cookie_headers(response) -> dict[str, str]:
    headers = response.headers.get_list("set-cookie")
    return {header.split("=", 1)[0]: header for header in headers}


def session_id_from_cookie(browser: TestClient) -> uuid.UUID:
    token = browser.cookies[SESSION_COOKIE]
    claims = jwt.decode(token, options={"verify_signature": False})
    return uuid.UUID(claims["jti"])


def csrf_headers(browser: TestClient) -> dict[str, str]:
    return {CSRF_HEADER: browser.cookies[CSRF_COOKIE]}


# Browser login


def test_browser_login_sets_hardened_cookies_and_no_token_in_body(
    browser: TestClient,
) -> None:
    register(browser)

    response = browser_login(browser)

    assert response.status_code == 204
    assert response.content == b""

    cookies = set_cookie_headers(response)
    session_cookie = cookies[SESSION_COOKIE].lower()
    csrf_cookie = cookies[CSRF_COOKIE].lower()
    max_age = f"max-age={settings.access_token_expire_minutes * 60}"

    for header in (session_cookie, csrf_cookie):
        assert "secure" in header
        assert "samesite=strict" in header
        assert "path=/" in header
        assert max_age in header
    assert "httponly" in session_cookie
    assert "httponly" not in csrf_cookie


def test_csrf_cookie_is_bound_to_the_session(browser: TestClient) -> None:
    register(browser)
    browser_login(browser)

    assert browser.cookies[CSRF_COOKIE] == csrf_token_for(
        session_id_from_cookie(browser)
    )


def test_session_cookie_authenticates_requests(browser: TestClient) -> None:
    register(browser)
    browser_login(browser)

    response = browser.get("/users/me")

    assert response.status_code == 200
    assert response.json()["username"] == "testuser"


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        ("text/plain", '{"email": "testuser@example.com", "password": "testpassword"}'),
        (
            "application/x-www-form-urlencoded",
            "email=testuser%40example.com&password=x",
        ),
    ],
)
def test_browser_login_rejects_non_json_bodies(
    browser: TestClient,
    content_type: str,
    body: str,
) -> None:
    # HTML forms can only send these content types, so another site cannot
    # log a victim into an account with a form (login CSRF).
    register(browser)

    response = browser.post(
        "/auth/session", content=body, headers={"content-type": content_type}
    )

    assert response.status_code == 422
    assert "set-cookie" not in response.headers


def test_browser_login_shares_brute_force_protection(
    browser: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "login_max_failed_attempts", 2)
    register(browser)

    statuses = [
        browser.post(
            "/auth/session",
            json={"email": "testuser@example.com", "password": "wrongpassword"},
        ).status_code
        for _ in range(2)
    ]

    assert statuses == [401, 429]
    assert browser_login(browser).status_code == 429
    assert SESSION_COOKIE not in browser.cookies


def test_cookie_secure_flag_follows_settings(
    browser: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_cookie_secure", False)
    register(browser)

    cookies = set_cookie_headers(browser_login(browser))

    assert "secure" not in cookies[SESSION_COOKIE].lower()
    assert "secure" not in cookies[CSRF_COOKIE].lower()


# CSRF protection


@pytest.mark.parametrize(
    "csrf_value",
    [None, "", "wrong-token", "other-session"],
)
def test_cookie_requests_that_change_state_require_a_valid_csrf_token(
    browser: TestClient,
    db_session: Session,
    csrf_value: str | None,
) -> None:
    register(browser)
    browser_login(browser)

    headers: dict[str, str] = {}
    if csrf_value == "other-session":
        headers[CSRF_HEADER] = csrf_token_for(uuid.uuid4())
    elif csrf_value is not None:
        headers[CSRF_HEADER] = csrf_value

    response = browser.post("/auth/logout", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token missing or invalid"
    # The session was not revoked.
    assert browser.get("/users/me").status_code == 200


def test_cookie_request_with_csrf_token_succeeds(
    browser: TestClient,
    db_session: Session,
) -> None:
    register(browser, "owneruser")
    owner = db_session.scalar(select(User).where(User.username == "owneruser"))
    assert owner is not None
    owner.role = UserRole.OWNER
    db_session.commit()
    register(browser, "target")
    target = db_session.scalar(select(User).where(User.username == "target"))
    assert target is not None
    browser_login(browser, "owneruser")

    response = browser.patch(
        f"/admin/users/{target.id}/role",
        json={"role": "admin"},
        headers=csrf_headers(browser),
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_safe_methods_do_not_need_a_csrf_token(browser: TestClient) -> None:
    register(browser)
    browser_login(browser)

    assert browser.get("/users/me/sessions").status_code == 200


def test_bearer_requests_do_not_need_a_csrf_token(client: TestClient) -> None:
    # Browsers never attach an Authorization header on their own, so bearer
    # requests cannot be forged by another site.
    register(client)
    token = client.post(
        "/auth/login",
        json={"email": "testuser@example.com", "password": PASSWORD},
    ).json()["access_token"]

    response = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204


def test_authorization_header_takes_precedence_over_the_cookie(
    browser: TestClient,
) -> None:
    register(browser, "alice")
    register(browser, "bob")
    browser_login(browser, "alice")
    bob_token = browser.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": PASSWORD},
    ).json()["access_token"]

    response = browser.get(
        "/users/me", headers={"Authorization": f"Bearer {bob_token}"}
    )

    assert response.json()["username"] == "bob"


@pytest.mark.parametrize("cookie_value", ["not-a-jwt", ""])
def test_invalid_session_cookie_is_rejected(
    browser: TestClient,
    cookie_value: str,
) -> None:
    browser.cookies.set(SESSION_COOKIE, cookie_value, domain="testserver")

    response = browser.get("/users/me")

    assert response.status_code == 401


def test_missing_credentials_return_401(browser: TestClient) -> None:
    response = browser.get("/users/me")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


# Logout


@pytest.mark.parametrize("path", ["/auth/logout", "/auth/logout-all"])
def test_cookie_logout_revokes_the_session_and_clears_cookies(
    browser: TestClient,
    path: str,
) -> None:
    register(browser)
    browser_login(browser)
    old_token = browser.cookies[SESSION_COOKIE]

    response = browser.post(path, headers=csrf_headers(browser))

    assert response.status_code == 204
    cookies = set_cookie_headers(response)
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        assert "max-age=0" in cookies[name].lower()
    assert SESSION_COOKIE not in browser.cookies
    assert CSRF_COOKIE not in browser.cookies

    # The token is revoked, not just forgotten by the browser.
    browser.cookies.set(SESSION_COOKIE, old_token, domain="testserver")
    assert browser.get("/users/me").status_code == 401


def test_browser_login_records_the_usual_events(
    browser: TestClient,
    db_session: Session,
) -> None:
    register(browser)
    browser_login(browser)

    event_types = set(db_session.scalars(select(SecurityEvent.event_type)).all())
    assert SecurityEventType.LOGIN_SUCCESS in event_types
