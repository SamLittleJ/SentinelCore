"""The first half of the incident drill (`make incident`, docs/postmortems/):
an organization of its own, then a password spray against it from one
address, at real time, so the API's detection sees it as it would a real one.

    python -m simulator.incident --base-url http://localhost:8080/api \\
        --owner-email owner@example.com

The owner's password comes from SENTINELCORE_OWNER_PASSWORD or a prompt. Each
step prints its UTC time, for the postmortem's timeline. The second half, a
shell in the API's container that Falco must catch, is scripts/incident.sh's.
"""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from simulator.__main__ import LOCAL_HOSTS
from simulator.client import SentinelCore, SimulatorError

# Above the spray rule's ten accounts and under the twenty failures an
# address may make before it is refused (app/core/config.py).
SPRAYED_ACCOUNTS = 12
MEMBERS = 14
NAME = "Northwind (incident drill)"


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def play(
    owner: SentinelCore, slug: str, say: Callable[[str], None] = print
) -> list[str]:
    """Create the drill's organization and its members, then spray them;
    returns the emails sprayed."""
    say(f"{now()} owner creates the organization {slug}")
    organization_id = owner.create_organization(NAME, slug)
    emails = [f"member{n:02d}@{slug}.example.com" for n in range(1, MEMBERS + 1)]
    for number, email in enumerate(emails, start=1):
        owner.add_person(
            f"{slug}-member{number:02d}",
            email,
            secrets.token_urlsafe(18),
            organization_id=organization_id,
        )
    say(f"{now()} {MEMBERS} members joined by invitation")
    sprayed = emails[:SPRAYED_ACCOUNTS]
    say(f"{now()} spray starts: one wrong password for each of {len(sprayed)} accounts")
    for email in sprayed:
        owner.sign_in_with_wrong_password(email)
    say(f"{now()} spray ends")
    return sprayed


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m simulator.incident",
        description="The incident drill's spray: an organization of its own, "
        "then a password spray against it from one address.",
    )
    parser.add_argument("--base-url", default="http://localhost:8080/api")
    parser.add_argument("--owner-email", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    host = urlsplit(args.base_url).hostname
    if host not in LOCAL_HOSTS:
        print(f"Refusing to attack {host}: the drill runs locally.", file=sys.stderr)
        return 2
    password = os.environ.get("SENTINELCORE_OWNER_PASSWORD") or getpass.getpass(
        f"Password for {args.owner_email}: "
    )
    slug = "northwind-" + datetime.now(UTC).strftime("%m%d%H%M")
    with httpx.Client(base_url=args.base_url, timeout=60) as http:
        owner = SentinelCore(http)
        try:
            owner.log_in(args.owner_email, password)
            play(owner, slug)
        except (SimulatorError, httpx.HTTPError) as error:
            print(error, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
