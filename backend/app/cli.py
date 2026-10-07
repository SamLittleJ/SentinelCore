"""Command-line maintenance tasks.

Usage, from the backend directory:

    python -m app.cli cleanup-sessions
"""

import argparse

from app.core.config import settings
from app.core.logging import configure_logging
from app.services.session_cleanup import run_session_cleanup


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "cleanup-sessions",
        help="Delete sessions that expired or were revoked before the retention "
        "period (SESSION_RETENTION_DAYS).",
    )

    args = parser.parse_args(argv)
    configure_logging(settings.log_level, settings.log_format)

    if args.command == "cleanup-sessions":
        deleted = run_session_cleanup()
        print(f"Deleted {deleted} stale session(s).")


if __name__ == "__main__":
    main()
