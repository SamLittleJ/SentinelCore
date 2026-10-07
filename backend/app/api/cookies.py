import uuid

from fastapi import Response

from app.core.config import settings
from app.core.security import csrf_token_for

SESSION_COOKIE = "sentinelcore_session"
CSRF_COOKIE = "sentinelcore_csrf"
CSRF_HEADER = "X-CSRF-Token"


def set_auth_cookies(
    response: Response,
    access_token: str,
    session_id: uuid.UUID,
    max_age: int,
) -> None:
    # The token is httpOnly, so page scripts (and XSS) cannot read it.
    response.set_cookie(
        SESSION_COOKIE,
        access_token,
        max_age=max_age,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    # The CSRF token must be readable by the frontend, which echoes it in the
    # X-CSRF-Token header on every state-changing request.
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token_for(session_id),
        max_age=max_age,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=False,
        samesite="strict",
    )


def clear_auth_cookies(response: Response) -> None:
    for name, httponly in ((SESSION_COOKIE, True), (CSRF_COOKIE, False)):
        response.delete_cookie(
            name,
            path="/",
            secure=settings.auth_cookie_secure,
            httponly=httponly,
            samesite="strict",
        )
