"""An API key's hourly event counts, and the volume spike rule that compares
them (T1499).

The counts follow the database clock at arrival, which tests cannot move, so
they write a key's earlier days straight into `api_key_usage`."""

# The ingestion fixtures are imported, so each test parameter naming one
# looks like a redefinition to Ruff.
# ruff: noqa: F811

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

import app.services.detection_service as detection_service
from app.api.deps import get_client_ip
from app.core.config import Settings, settings
from app.core.database import database_now
from app.main import app
from app.models.api_key import ApiKey
from app.models.api_key_usage import ApiKeyUsage
from app.models.security_event import (
    DETECTION_SOURCE,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
)
from app.services import session_cleanup
from app.services.api_key_usage_service import delete_old_usage
from tests.conftest import TestingSessionLocal
from tests.test_ingestion import (  # noqa: F401  Fixtures.
    event,
    ingest,
    issue_key,
    key,
    owner,
    small_bucket,
)

SENDER = "203.0.113.9"


@pytest.fixture(autouse=True)
def sender_address(client: TestClient) -> None:
    """The address the batches come from; the test client has none."""
    app.dependency_overrides[get_client_ip] = lambda: SENDER


def the_key(db: Session, name: str = "Corporate VPN") -> ApiKey:
    db.expire_all()
    api_key = db.scalar(select(ApiKey).where(ApiKey.name == name))
    assert api_key is not None
    return api_key


def today(db: Session) -> datetime:
    """The start of the current UTC day, by the database clock."""
    now = database_now(db).astimezone(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def usage(db: Session, name: str = "Corporate VPN") -> list[ApiKeyUsage]:
    db.expire_all()
    return list(
        db.scalars(
            select(ApiKeyUsage)
            .where(ApiKeyUsage.api_key_id == the_key(db, name).id)
            .order_by(ApiKeyUsage.hour)
        ).all()
    )


def history(db: Session, *busiest: int, days_ago: int = 1, hours: int = 1) -> None:
    """Earlier days of the key's traffic: the busiest hour of each day, from
    `days_ago` days back and further, each spread over `hours` equal hours."""
    api_key = the_key(db)
    start = today(db)
    for offset, count in enumerate(busiest):
        day = start - timedelta(days=days_ago + offset)
        for hour in range(hours):
            db.add(
                ApiKeyUsage(
                    api_key_id=api_key.id,
                    organization_id=api_key.organization_id,
                    hour=day + timedelta(hours=9 + hour),
                    received=count,
                    refused=0,
                )
            )
    db.commit()


def spikes(db: Session) -> list[SecurityEvent]:
    db.expire_all()
    return list(
        db.scalars(
            select(SecurityEvent).where(
                SecurityEvent.event_type == SecurityEventType.API_KEY_VOLUME_SPIKE
            )
        ).all()
    )


# Counting arrivals


def test_each_batch_is_counted_in_its_keys_current_utc_hour(
    client: TestClient, db_session: Session, key: str
) -> None:
    ingest(client, key, [event()] * 3)
    ingest(client, key, [event()] * 2)

    [hour] = usage(db_session)
    now = database_now(db_session).astimezone(UTC)
    assert hour.hour == now.replace(minute=0, second=0, microsecond=0)
    assert (hour.received, hour.refused) == (5, 0)
    assert hour.organization_id == the_key(db_session).organization_id


def test_batches_count_when_they_arrive_not_when_their_events_say(
    client: TestClient, db_session: Session, key: str
) -> None:
    last_week = (datetime.now(UTC) - timedelta(days=7)).isoformat()

    ingest(client, key, [event(occurred_at=last_week)] * 3)

    [hour] = usage(db_session)
    assert hour.hour >= today(db_session)


def test_refused_batches_count_too(
    client: TestClient, db_session: Session, key: str, small_bucket: None
) -> None:
    assert ingest(client, key, [event()] * 3).status_code == 202
    assert ingest(client, key, [event()] * 3).status_code == 429

    [hour] = usage(db_session)
    assert (hour.received, hour.refused) == (6, 3)


def test_batches_without_a_valid_key_or_body_are_not_counted(
    client: TestClient, db_session: Session, key: str
) -> None:
    assert ingest(client, key[:-1] + "x", [event()]).status_code == 401
    invalid = [event(event_type="password_changed")]
    assert ingest(client, key, invalid).status_code == 422

    assert usage(db_session) == []


def test_each_key_is_counted_apart(
    client: TestClient, db_session: Session, owner: dict[str, str], key: str
) -> None:
    other = issue_key(client, owner, "Identity provider")
    ingest(client, key, [event()] * 3)
    ingest(client, other, [event()] * 2)

    assert [hour.received for hour in usage(db_session)] == [3]
    assert [hour.received for hour in usage(db_session, "Identity provider")] == [2]


# The volume spike rule


def test_an_hour_far_above_the_usual_raises_an_alert(
    client: TestClient, db_session: Session, key: str
) -> None:
    history(db_session, *[30] * 7)

    assert ingest(client, key, [event()] * 100).status_code == 202

    [alert] = spikes(db_session)
    api_key = the_key(db_session)
    assert alert.severity == SecuritySeverity.WARN
    assert alert.source == DETECTION_SOURCE
    assert alert.mitre_technique == "T1499"
    assert alert.organization_id == api_key.organization_id
    assert alert.ip_address == SENDER
    assert alert.occurred_at is not None
    assert alert.user_id is None and alert.email is None
    assert f"API key {api_key.prefix} (Corporate VPN) sent 100 events" in (
        alert.message
    )
    assert "3.3 times its usual busiest hour (30 events)" in alert.message
    assert key.split("_", 2)[2] not in alert.message


def test_an_hour_below_the_factor_raises_none(
    client: TestClient, db_session: Session, key: str
) -> None:
    history(db_session, *[34] * 7)

    ingest(client, key, [event()] * 101)

    assert spikes(db_session) == []


def test_a_quiet_key_needs_the_minimum_number_of_events(
    client: TestClient, db_session: Session, key: str
) -> None:
    history(db_session, *[1] * 7)

    ingest(client, key, [event()] * 99)
    assert spikes(db_session) == []

    ingest(client, key, [event()])
    assert len(spikes(db_session)) == 1


def test_a_key_with_too_few_days_is_still_learning(
    client: TestClient, db_session: Session, key: str
) -> None:
    history(db_session, *[10] * 6)

    ingest(client, key, [event()] * 500)

    assert spikes(db_session) == []


def test_days_before_the_lookback_are_not_compared(
    client: TestClient, db_session: Session, key: str
) -> None:
    lookback = settings.detection_volume_lookback_days
    history(db_session, *[10] * 3, days_ago=1)
    history(db_session, *[10] * 4, days_ago=lookback + 1)

    ingest(client, key, [event()] * 500)

    assert spikes(db_session) == []


def test_today_does_not_count_toward_the_usual(
    client: TestClient, db_session: Session, key: str
) -> None:
    history(db_session, *[30] * 7)
    # Another hour of today, busier than the spike to come.
    api_key = the_key(db_session)
    current = database_now(db_session).astimezone(UTC).hour
    db_session.add(
        ApiKeyUsage(
            api_key_id=api_key.id,
            organization_id=api_key.organization_id,
            hour=today(db_session) + timedelta(hours=1 if current == 0 else 0),
            received=1000,
            refused=0,
        )
    )
    db_session.commit()

    ingest(client, key, [event()] * 100)

    assert len(spikes(db_session)) == 1


def test_the_usual_is_the_median_of_the_days(
    client: TestClient, db_session: Session, key: str
) -> None:
    # One unusual day does not move the median (10), as it would a mean (149).
    history(db_session, *[10] * 6, 980)

    ingest(client, key, [event()] * 100)

    [alert] = spikes(db_session)
    assert "(10 events)" in alert.message


def test_the_usual_is_each_days_busiest_hour_not_its_total(
    client: TestClient, db_session: Session, key: str
) -> None:
    # Each day had three hours of 40 events: 120 in all.
    history(db_session, *[40] * 7, hours=3)

    ingest(client, key, [event()] * 119)
    assert spikes(db_session) == []

    ingest(client, key, [event()])
    [alert] = spikes(db_session)
    assert "(40 events)" in alert.message


def test_an_hour_alerts_once(client: TestClient, db_session: Session, key: str) -> None:
    history(db_session, *[30] * 7)

    ingest(client, key, [event()] * 100)
    ingest(client, key, [event()] * 100)

    assert len(spikes(db_session)) == 1
    [hour] = [hour for hour in usage(db_session) if hour.hour >= today(db_session)]
    assert hour.alerted_at is not None
    assert hour.received == 200


def test_the_next_hour_may_alert_again(
    client: TestClient, db_session: Session, key: str
) -> None:
    history(db_session, *[30] * 7)
    ingest(client, key, [event()] * 100)
    # The alerted hour becomes an earlier one.
    db_session.execute(
        update(ApiKeyUsage)
        .where(ApiKeyUsage.alerted_at.is_not(None))
        .values(hour=ApiKeyUsage.hour - timedelta(hours=1))
    )
    db_session.commit()

    ingest(client, key, [event()] * 100)

    assert len(spikes(db_session)) == 2


def test_a_flood_the_rate_limit_refuses_still_alerts(
    client: TestClient, db_session: Session, key: str, small_bucket: None
) -> None:
    history(db_session, *[30] * 7)

    assert ingest(client, key, [event()] * 100).status_code == 429

    [alert] = spikes(db_session)
    assert "sent 100 events" in alert.message


def test_a_failing_rule_never_fails_the_batch(
    client: TestClient,
    db_session: Session,
    key: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    history(db_session, *[30] * 7)

    def broken(*args: object) -> float:
        raise RuntimeError("rule failed")

    monkeypatch.setattr(detection_service, "usual_busiest_hour", broken)

    with caplog.at_level(logging.ERROR):
        response = ingest(client, key, [event()] * 100)

    assert response.status_code == 202
    assert response.json() == {"accepted": 100}
    assert spikes(db_session) == []
    [record] = [r for r in caplog.records if r.getMessage() == "Detection failed"]
    assert record.__dict__["api_key_prefix"] == the_key(db_session).prefix


def test_the_alert_is_not_returned_to_the_sender(
    client: TestClient, db_session: Session, key: str
) -> None:
    history(db_session, *[30] * 7)

    response = ingest(client, key, [event()] * 100)

    assert response.json() == {"accepted": 100}
    assert len(spikes(db_session)) == 1


# Keeping the counts


def test_old_hours_are_deleted_by_whole_days(db_session: Session, key: str) -> None:
    retention = 30
    history(db_session, 5, days_ago=retention)
    history(db_session, 6, days_ago=retention + 1)

    assert delete_old_usage(db_session, retention) == 1

    assert [hour.received for hour in usage(db_session)] == [5]


def test_the_periodic_cleanup_deletes_old_hours(
    db_session: Session,
    key: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(session_cleanup, "SessionLocal", TestingSessionLocal)
    retention = settings.api_key_usage_retention_days
    history(db_session, 5, days_ago=retention)
    history(db_session, 6, 7, days_ago=retention + 1)

    with caplog.at_level(logging.INFO, logger="app.services.session_cleanup"):
        session_cleanup.run_session_cleanup()

    assert [hour.received for hour in usage(db_session)] == [5]
    record = next(r for r in caplog.records if r.name == session_cleanup.__name__)
    assert record.__dict__["deleted_api_key_usage_hours"] == 2


# Settings


URL, SECRET_KEY = "postgresql://unused", "x" * 32


def test_the_rule_must_be_able_to_judge_and_keep_its_days() -> None:
    Settings(
        database_url=URL,
        secret_key=SECRET_KEY,
        detection_volume_min_days=14,
        detection_volume_lookback_days=14,
        api_key_usage_retention_days=14,
    )
    invalid: list[dict[str, Any]] = [
        {"detection_volume_min_days": 15},
        {"api_key_usage_retention_days": 13},
        {"detection_volume_factor": 1},
        {"detection_volume_min_events": 0},
    ]
    for changes in invalid:
        with pytest.raises(ValidationError):
            Settings(
                database_url=URL,
                secret_key=SECRET_KEY,
                detection_volume_lookback_days=14,
                **changes,
            )


def test_by_default_three_times_the_usual_and_100_events_after_a_week() -> None:
    fields = Settings.model_fields
    assert fields["detection_volume_factor"].default == 3.0
    assert fields["detection_volume_min_events"].default == 100
    assert fields["detection_volume_lookback_days"].default == 14
    assert fields["detection_volume_min_days"].default == 7
    assert fields["api_key_usage_retention_days"].default == 30
