"""The API calls the simulator makes, over any httpx client.

The tests pass FastAPI's TestClient, which is an httpx client, so the same
code drives the application in-process and over the network.
"""

import time

import httpx

# The alerts the simulator expects: type, MITRE ATT&CK technique, rule name.
ALERTS = (
    ("brute_force_detected", "T1110.001", "Brute force"),
    ("password_spray_detected", "T1110.003", "Password spray"),
    ("dormant_account_login", "T1078", "Dormant account"),
    ("unfamiliar_sign_in", "T1078", "Unfamiliar network and device"),
    ("privileged_role_granted", "T1098", "Privileged role granted"),
)
ALERT_TYPES = tuple(alert_type for alert_type, _, _ in ALERTS)
INGEST_BATCH = 500
# The attacker's guess, wrong on purpose.
WRONG_PASSWORD = "not-the-password-0"  # nosec B105
ALERTS_PAGE = 200


class SimulatorError(Exception):
    pass


def check(response: httpx.Response, action: str) -> httpx.Response:
    if response.is_error:
        # The body explains validation errors; it never holds a secret.
        raise SimulatorError(f"{action} failed: {response.status_code} {response.text}")
    return response


class SentinelCore:
    def __init__(self, http: httpx.Client) -> None:
        self.http = http
        self.owner_token: str | None = None
        self.api_key: str | None = None

    @property
    def as_owner(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.owner_token}"}

    def log_in_owner(self, email: str, password: str) -> None:
        response = self.http.post(
            "/auth/login", json={"email": email, "password": password}
        )
        self.owner_token = check(response, "Signing in as the owner").json()[
            "access_token"
        ]

    def create_api_key(self) -> int:
        response = self.http.post(
            "/admin/api-keys",
            json={
                "name": "Attack simulator",
                "source": "simulator",
                "expires_in_days": 30,
            },
            headers=self.as_owner,
        )
        created = check(response, "Creating the API key").json()
        self.api_key = created["key"]
        return created["api_key"]["id"]

    def revoke_api_key(self, key_id: int) -> None:
        response = self.http.post(
            f"/admin/api-keys/{key_id}/revoke", headers=self.as_owner
        )
        check(response, "Revoking the API key")
        self.api_key = None

    def register(self, username: str, email: str, password: str) -> int:
        response = self.http.post(
            "/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        return check(response, f"Registering {email}").json()["id"]

    def ingest(self, events: list[dict]) -> float:
        """Report `events`, in batches; returns the time taken, in ms."""
        started = time.perf_counter()
        for first in range(0, len(events), INGEST_BATCH):
            response = self.http.post(
                "/ingest/events",
                json={"events": events[first : first + INGEST_BATCH]},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            check(response, "Ingesting events")
        return (time.perf_counter() - started) * 1000

    def sign_in_with_wrong_password(self, email: str) -> float:
        started = time.perf_counter()
        # 401 while the guesses count, then 429 once the email is locked.
        self.http.post(
            "/auth/login",
            json={"email": email, "password": WRONG_PASSWORD},
        )
        return (time.perf_counter() - started) * 1000

    def grant_admin(self, user_id: int) -> float:
        started = time.perf_counter()
        response = self.http.patch(
            f"/admin/users/{user_id}/role",
            json={"role": "admin"},
            headers=self.as_owner,
        )
        check(response, f"Granting admin to user_id={user_id}")
        return (time.perf_counter() - started) * 1000

    def alerts_after(self, last_id: int) -> list[dict]:
        """Alerts with an id above `last_id`, oldest first.

        Each call is a read of individual events, so the server audits it.
        Listings are newest first by time; alerts are stamped with the server's
        clock as they are raised, so that is also the order of their ids.
        """
        alerts: list[dict] = []
        before_id = None
        while True:
            params: dict = {"event_type": list(ALERT_TYPES), "limit": ALERTS_PAGE}
            if before_id is not None:
                params["before_id"] = before_id
            response = self.http.get(
                "/security/events", params=params, headers=self.as_owner
            )
            page = check(response, "Reading alerts").json()
            newer = [alert for alert in page["items"] if alert["id"] > last_id]
            alerts += newer
            if len(newer) < len(page["items"]) or page["next_cursor"] is None:
                break
            before_id = page["next_cursor"]
        return sorted(alerts, key=lambda alert: alert["id"])

    def latest_alert_id(self) -> int:
        response = self.http.get(
            "/security/events",
            params={"event_type": list(ALERT_TYPES), "limit": 1},
            headers=self.as_owner,
        )
        items = check(response, "Reading alerts").json()["items"]
        return items[0]["id"] if items else 0
