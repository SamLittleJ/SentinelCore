"""Synthetic traffic for a canary's analysis (docs/07-gitops.md).

Usage, from the backend image:

    python -m app.canary_traffic --url http://sentinelcore-backend-canary:8000 \
        --seconds 120 --rate 5

It sends requests that read the database and write nothing: an ingestion
batch with a well-formed key that does not exist. The API looks the key up
in `api_keys` and answers 401, before any token is taken or any event,
usage row or audit record is written. A version that cannot read its tables
answers 500 instead, which the analysis's Prometheus query counts. Failed
sign-ins were not used: each would write a security event, spend the
address's sign-in budget and could raise an alert.

It needs no setting of the application (no database URL, no secret), so the
Job that runs it holds none; it uses the standard library only. It prints
how many answers fell in each class and exits with 1 only when no request
got an answer at all, as the canary was then not reachable.
"""

import argparse
import json
import secrets
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable

PATH = "/ingest/events"
TIMEOUT_SECONDS = 5


def unknown_key() -> str:
    """A key of the ingestion scheme (`sck_<prefix>_<secret>`) that no
    organization holds: its prefix is random, so the lookup finds nothing."""
    return f"sck_{secrets.token_hex(6)}_{secrets.token_urlsafe(24)}"


def request_for(base_url: str) -> urllib.request.Request:
    return urllib.request.Request(
        base_url.rstrip("/") + PATH,
        data=json.dumps({"events": []}).encode(),
        headers={
            "Authorization": f"Bearer {unknown_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def send(request: urllib.request.Request) -> int | None:
    """The status code of the answer, or None when there was none."""
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
            return int(response.status)
    except urllib.error.HTTPError as error:
        return int(error.code)
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None


def status_class(status: int | None) -> str:
    return "no answer" if status is None else f"{status // 100}xx"


def run(
    base_url: str,
    seconds: float,
    rate: float,
    sender: Callable[[urllib.request.Request], int | None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] | None = None,
) -> Counter[str]:
    """Sends `rate` requests a second for `seconds`, on a fixed schedule so a
    slow answer does not lower the rate after it."""
    sender = sender or send
    sleep = sleep or time.sleep
    counts: Counter[str] = Counter()
    start = clock()
    for index in range(round(seconds * rate)):
        wait = start + index / rate - clock()
        if wait > 0:
            sleep(wait)
        counts[status_class(sender(request_for(base_url)))] += 1
    return counts


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.canary_traffic")
    parser.add_argument("--url", required=True, help="The canary Service's URL.")
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--rate", type=float, default=5, help="Requests a second.")
    args = parser.parse_args(argv)
    if args.seconds <= 0 or args.rate <= 0:
        parser.error("--seconds and --rate must be positive")

    counts = run(args.url, args.seconds, args.rate)
    print(", ".join(f"{name}: {counts[name]}" for name in sorted(counts)))
    if counts["no answer"] == sum(counts.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
