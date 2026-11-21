"""The canary's synthetic traffic (app/canary_traffic.py): it reads the
database and writes nothing, and keeps its pace."""

import urllib.request
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import canary_traffic
from app.models.api_key import ApiKey
from app.models.api_key_usage import ApiKeyUsage
from app.models.audit_log import AuditLog
from app.models.security_event import SecurityEvent
from app.services.api_key_service import KEY_SCHEME
from tests.conftest import system_session

WRITTEN = (SecurityEvent, AuditLog, ApiKeyUsage, ApiKey)


def row_counts() -> dict[str, int]:
    with system_session() as db:
        return {
            model.__tablename__: db.scalar(select(func.count()).select_from(model)) or 0
            for model in WRITTEN
        }


@pytest.fixture()
def counts_before(client: TestClient) -> Generator[dict[str, int]]:
    yield row_counts()


def through(client: TestClient, request: urllib.request.Request) -> int:
    path = request.full_url.removeprefix("http://canary:8000")
    response = client.post(
        path, content=request.data, headers=dict(request.header_items())
    )
    return response.status_code


def test_the_request_is_refused_without_writing_anything(
    client: TestClient, db_session: Session, counts_before: dict[str, int]
) -> None:
    statuses = [
        through(client, canary_traffic.request_for("http://canary:8000/"))
        for _ in range(20)
    ]

    assert statuses == [401] * 20
    assert row_counts() == counts_before


def test_each_request_carries_a_new_key_of_the_ingestion_scheme() -> None:
    keys = {
        canary_traffic.request_for("http://canary:8000").get_header("Authorization", "")
        for _ in range(50)
    }

    assert len(keys) == 50
    for header in keys:
        scheme, _, token = header.removeprefix("Bearer ").partition("_")
        prefix, _, secret = token.partition("_")
        assert scheme == KEY_SCHEME and prefix and secret


@pytest.mark.parametrize(
    ("status", "name"),
    [(202, "2xx"), (401, "4xx"), (429, "4xx"), (500, "5xx"), (None, "no answer")],
)
def test_answers_are_counted_by_class(status: int | None, name: str) -> None:
    assert canary_traffic.status_class(status) == name


def test_it_sends_rate_times_seconds_requests_on_a_fixed_schedule() -> None:
    now = [0.0]
    sent_at: list[float] = []

    def sender(_: urllib.request.Request) -> int:
        sent_at.append(now[0])
        now[0] += 0.05  # each answer takes a little time
        return 401

    def sleep(seconds: float) -> None:
        now[0] += seconds

    counts = canary_traffic.run(
        "http://canary:8000",
        seconds=2,
        rate=5,
        sender=sender,
        clock=lambda: now[0],
        sleep=sleep,
    )

    assert counts == {"4xx": 10}
    assert sent_at == pytest.approx([i / 5 for i in range(10)])


def test_it_fails_only_when_nothing_answered(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(canary_traffic, "send", lambda _: None)
    monkeypatch.setattr(canary_traffic.time, "sleep", lambda _: None)
    with pytest.raises(SystemExit) as exit_info:
        canary_traffic.main(
            ["--url", "http://canary:8000", "--seconds", "1", "--rate", "3"]
        )
    assert exit_info.value.code == 1
    assert "no answer: 3" in capsys.readouterr().out

    answers = iter([None, 500, 401])
    monkeypatch.setattr(canary_traffic, "send", lambda _: next(answers))
    canary_traffic.main(
        ["--url", "http://canary:8000", "--seconds", "1", "--rate", "3"]
    )
    assert capsys.readouterr().out.strip() == "4xx: 1, 5xx: 1, no answer: 1"
