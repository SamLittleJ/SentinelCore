"""The incident drill's spray (simulator/incident.py): one organization of
its own, then a spray from one address that the rule catches, at the
server's default limits."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.security_event import SecurityEvent, SecurityEventType
from app.schemas.user import UserCreate
from app.services.user_service import create_owner
from simulator import incident
from simulator.client import SentinelCore
from tests.test_simulator import from_address

OWNER_EMAIL = "owner@example.com"
OWNER_PASSWORD = "owner-password-1"


@pytest.fixture()
def owner(client: TestClient, db_session: Session) -> SentinelCore:
    create_owner(
        db_session,
        UserCreate(username="owner", email=OWNER_EMAIL, password=OWNER_PASSWORD),
    )
    # One address of its own: the rule skips events without one.
    api = SentinelCore(from_address("198.51.100.20"))
    api.log_in(OWNER_EMAIL, OWNER_PASSWORD)
    return api


def test_the_spray_is_detected_in_the_drills_own_organization(
    owner: SentinelCore, db_session: Session
) -> None:
    lines: list[str] = []

    sprayed = incident.play(owner, "northwind-test", lines.append)

    organization = db_session.scalars(
        select(Organization).where(Organization.slug == "northwind-test")
    ).one()
    assert "incident drill" in organization.name
    alerts = db_session.scalars(
        select(SecurityEvent).where(
            SecurityEvent.event_type == SecurityEventType.PASSWORD_SPRAY_DETECTED
        )
    ).all()
    assert len(alerts) == 1
    assert alerts[0].organization_id == organization.id
    assert len(sprayed) == incident.SPRAYED_ACCOUNTS
    assert any("spray starts" in line for line in lines)


def test_the_spray_stays_under_the_limit_per_address() -> None:
    from app.core.config import settings

    assert settings.detection_spray_min_accounts <= incident.SPRAYED_ACCOUNTS
    assert incident.SPRAYED_ACCOUNTS < settings.login_address_burst
    assert incident.SPRAYED_ACCOUNTS <= incident.MEMBERS


def test_the_drill_refuses_a_remote_host(capsys: pytest.CaptureFixture[str]) -> None:
    code = incident.main(
        ["--base-url", "https://example.com/api", "--owner-email", OWNER_EMAIL]
    )

    assert code == 2
    assert "Refusing to attack example.com" in capsys.readouterr().err
