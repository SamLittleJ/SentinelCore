"""The API calls the simulator makes, over any httpx client.

The tests pass FastAPI's TestClient, which is an httpx client, so the same
code drives the application in-process and over the network.
"""

import time
from collections.abc import Callable

import httpx

# The alerts the simulator expects: type, MITRE ATT&CK technique, rule name.
ALERTS = (
    ("brute_force_detected", "T1110.001", "Brute force"),
    ("password_spray_detected", "T1110.003", "Password spray"),
    (
        "cross_organization_spray_detected",
        "T1110.003",
        "Password spray across organizations",
    ),
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
    """The API as one signed-in operator: the owner, or for the demo an
    admin or an analyst too.

    `from_address`, when given, makes a client whose requests come from
    another address, for attackers that are not the simulator itself.
    """

    def __init__(
        self,
        http: httpx.Client,
        from_address: Callable[[str], httpx.Client] | None = None,
    ) -> None:
        self.http = http
        self.from_address = from_address
        self.senders: dict[str, httpx.Client] = {}
        self.operator_token: str | None = None
        self.api_key: str | None = None

    def sender(self, address: str | None) -> httpx.Client:
        """The client whose requests come from `address`, or ours for None."""
        if address is None:
            return self.http
        if self.from_address is None:
            raise SimulatorError(f"Cannot send from {address}")
        if address not in self.senders:
            self.senders[address] = self.from_address(address)
        return self.senders[address]

    def close_senders(self) -> None:
        for sender in self.senders.values():
            sender.close()
        self.senders.clear()

    @property
    def as_operator(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.operator_token}"}

    def log_in(self, email: str, password: str) -> None:
        response = self.http.post(
            "/auth/login", json={"email": email, "password": password}
        )
        self.operator_token = check(response, f"Signing in as {email}").json()[
            "access_token"
        ]

    def create_organization(self, name: str, slug: str) -> int:
        response = self.http.post(
            "/admin/organizations",
            json={"name": name, "slug": slug},
            headers=self.as_operator,
        )
        return check(response, f"Creating organization {slug}").json()["id"]

    def suspend_organization(self, organization_id: int) -> None:
        response = self.http.post(
            f"/admin/organizations/{organization_id}/suspend",
            headers=self.as_operator,
        )
        check(response, "Suspending an organization")

    def create_api_key(
        self,
        organization_id: int,
        name: str = "Attack simulator",
        source: str = "simulator",
        expires_in_days: int = 30,
    ) -> int:
        response = self.http.post(
            "/admin/api-keys",
            json={
                "name": name,
                "source": source,
                "expires_in_days": expires_in_days,
                "organization_id": organization_id,
            },
            headers=self.as_operator,
        )
        created = check(response, "Creating the API key").json()
        self.api_key = created["key"]
        return created["api_key"]["id"]

    def revoke_api_key(self, key_id: int) -> None:
        response = self.http.post(
            f"/admin/api-keys/{key_id}/revoke", headers=self.as_operator
        )
        check(response, "Revoking the API key")
        self.api_key = None

    def invite(
        self, email: str, role: str = "user", organization_id: int | None = None
    ) -> tuple[int, str]:
        """The new invitation's id and its token, shown only now. The owner
        names the organization; an admin invites into their own."""
        body: dict = {"email": email, "role": role}
        if organization_id is not None:
            body["organization_id"] = organization_id
        response = self.http.post(
            "/admin/invitations",
            json=body,
            headers=self.as_operator,
        )
        created = check(response, f"Inviting {email}").json()
        return created["invitation"]["id"], created["token"]

    def revoke_invitation(self, invitation_id: int) -> None:
        response = self.http.post(
            f"/admin/invitations/{invitation_id}/revoke", headers=self.as_operator
        )
        check(response, "Revoking an invitation")

    def add_person(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "user",
        organization_id: int | None = None,
    ) -> int:
        """Invite `email`, then accept as the person invited, the only way an
        account joins an organization."""
        _, token = self.invite(email, role, organization_id)
        response = self.http.post(
            "/auth/invitations/accept",
            json={"token": token, "username": username, "password": password},
        )
        return check(response, f"Accepting the invitation of {email}").json()["id"]

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

    def sign_in_with_wrong_password(
        self, email: str, address: str | None = None
    ) -> float:
        started = time.perf_counter()
        response = self.sender(address).post(
            "/auth/login",
            json={"email": email, "password": WRONG_PASSWORD},
        )
        # 401 while the guesses count, then 429 once the email or the address
        # is limited. Anything else is a failure, not a guess.
        if response.status_code not in (401, 429):
            raise SimulatorError(
                f"Guessing the password of {email} got {response.status_code}"
            )
        return (time.perf_counter() - started) * 1000

    def grant_admin(self, user_id: int) -> float:
        started = time.perf_counter()
        response = self.http.patch(
            f"/admin/users/{user_id}/role",
            json={"role": "admin"},
            headers=self.as_operator,
        )
        check(response, f"Granting admin to user_id={user_id}")
        return (time.perf_counter() - started) * 1000

    def change_role(self, user_id: int, role: str) -> None:
        response = self.http.patch(
            f"/admin/users/{user_id}/role",
            json={"role": role},
            headers=self.as_operator,
        )
        check(response, f"Changing the role of user_id={user_id}")

    def deactivate(self, user_id: int) -> None:
        response = self.http.patch(
            f"/admin/users/{user_id}/status",
            json={"is_active": False},
            headers=self.as_operator,
        )
        check(response, f"Deactivating user_id={user_id}")

    def lock(self, user_id: int, hours: int, reason: str) -> None:
        response = self.http.post(
            f"/admin/users/{user_id}/lock",
            json={"duration_hours": hours, "reason": reason},
            headers=self.as_operator,
        )
        check(response, f"Locking user_id={user_id}")

    def revoke_sessions(self, user_id: int, reason: str) -> None:
        response = self.http.post(
            f"/admin/users/{user_id}/revoke-sessions",
            json={"reason": reason},
            headers=self.as_operator,
        )
        check(response, f"Revoking the sessions of user_id={user_id}")

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
                "/security/events", params=params, headers=self.as_operator
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
            headers=self.as_operator,
        )
        items = check(response, "Reading alerts").json()["items"]
        return items[0]["id"] if items else 0
