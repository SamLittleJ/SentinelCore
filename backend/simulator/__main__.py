"""Command line: python -m simulator --owner-email owner@example.com

The owner's password is read from SENTINELCORE_OWNER_PASSWORD, or asked for,
so it never appears in the shell history or the process list.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from simulator.client import SentinelCore, SimulatorError
from simulator.evaluation import evaluate
from simulator.report import to_json, to_markdown
from simulator.runner import simulate

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "docs" / "evaluation"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m simulator",
        description="Play routine traffic and attacks against SentinelCore and "
        "report how many were detected.",
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--owner-email", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow a host other than localhost. The simulator attacks the "
        "target for real: point it only at an instance you own.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    host = urlsplit(args.base_url).hostname
    if host not in LOCAL_HOSTS and not args.allow_remote:
        print(
            f"Refusing to attack {host}: pass --allow-remote if you own it.",
            file=sys.stderr,
        )
        return 2

    password = os.environ.get("SENTINELCORE_OWNER_PASSWORD") or getpass.getpass(
        f"Password for {args.owner_email}: "
    )
    with httpx.Client(base_url=args.base_url, timeout=30) as http:
        api = SentinelCore(http)
        try:
            api.log_in_owner(args.owner_email, password)
            observations = simulate(api, args.seed)
        except (SimulatorError, httpx.HTTPError) as error:
            print(error, file=sys.stderr)
            return 1

    evaluation = evaluate(observations)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.md").write_text(to_markdown(evaluation))
    (args.out / "report.json").write_text(to_json(evaluation))
    if evaluation.earlier_alerts:
        print(
            "Warning: the database already held alerts; see the report.",
            file=sys.stderr,
        )
    print(
        f"Detected {evaluation.detected} of {evaluation.attacks} attacks, "
        f"{len(evaluation.false_positives)} false positives. "
        f"Report: {args.out / 'report.md'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
