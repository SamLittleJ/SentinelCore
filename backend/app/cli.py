"""Command-line maintenance tasks.

Usage, from the backend directory:

    python -m app.cli grant-api-login
    python -m app.cli cleanup-sessions
    python -m app.cli create-owner --email owner@example.com --username owner

`grant-api-login` lets the API's database role sign in with the password in
DATABASE_URL; it runs as the owner of the tables (MIGRATIONS_DATABASE_URL),
after the migrations have created the role.

`create-owner` reads the password from SENTINELCORE_OWNER_PASSWORD, or asks
for it without echoing it, so it stays out of the shell history.
"""

import argparse
import getpass
import os
from typing import cast

import psycopg
from psycopg import sql
from pydantic import ValidationError
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging
from app.core.row_security import APP_ROLE, restrict_rows
from app.schemas.user import UserCreate
from app.services.session_cleanup import run_session_cleanup
from app.services.tenancy import SYSTEM
from app.services.user_service import OwnerExistsError, create_owner

# The name of an environment variable, not a password.
OWNER_PASSWORD_ENV = "SENTINELCORE_OWNER_PASSWORD"  # nosec B105


def _owner_password() -> str:
    password = os.environ.get(OWNER_PASSWORD_ENV)
    if password:
        return password
    password = getpass.getpass("Owner password: ")
    if getpass.getpass("Repeat the password: ") != password:
        raise SystemExit("The passwords differ.")
    return password


def _create_owner(email: str, username: str) -> None:
    try:
        owner_in = UserCreate(
            email=email, username=username, password=_owner_password()
        )
    except ValidationError as exc:
        # Only where and what: the error's input could be the password.
        problems = "; ".join(
            f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
            for error in exc.errors()
        )
        raise SystemExit(f"Invalid owner details: {problems}") from None

    with SessionLocal() as db:
        restrict_rows(db, SYSTEM)
        try:
            owner = create_owner(db, owner_in)
        except OwnerExistsError as exc:
            raise SystemExit(f"{exc}; invite other accounts from it.") from None
        except IntegrityError:
            raise SystemExit(
                "An account with this email or username already exists."
            ) from None
    print(f"Created the owner {owner.email} (user_id={owner.id}).")


def _grant_api_login() -> None:
    if settings.migrations_database_url is None:
        raise SystemExit("Set MIGRATIONS_DATABASE_URL to the owner of the tables.")
    api = make_url(settings.database_url)
    if not api.username or not api.password:
        raise SystemExit("DATABASE_URL must name the API's role and its password.")

    engine = create_engine(settings.migrations_database_url)
    try:
        with engine.connect() as connection:
            bypasses = connection.scalar(
                text(
                    "SELECT rolsuper OR rolbypassrls FROM pg_roles "
                    "WHERE rolname = :name"
                ),
                {"name": api.username},
            )
            if bypasses is None:
                raise SystemExit(
                    f"No database role {api.username}: run the migrations first."
                )
            if bypasses:
                raise SystemExit(
                    f"The role {api.username} bypasses row-level security; "
                    f"DATABASE_URL must name the API's role, {APP_ROLE}."
                )
            # A role's password cannot be a query parameter, so it is quoted
            # as a literal by the driver.
            statement = sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(api.username), sql.Literal(api.password)
            )
            driver = cast(psycopg.Connection, connection.connection.driver_connection)
            driver.execute(statement)
            connection.commit()
    finally:
        engine.dispose()
    print(f"The role {api.username} may now sign in with the password in DATABASE_URL.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "grant-api-login",
        help="Let the API's database role sign in with the password in "
        "DATABASE_URL, as the owner in MIGRATIONS_DATABASE_URL.",
    )
    commands.add_parser(
        "cleanup-sessions",
        help="Delete sessions that expired or were revoked before the retention "
        "period (SESSION_RETENTION_DAYS).",
    )
    create_owner_parser = commands.add_parser(
        "create-owner",
        help="Create the organization's first owner, who invites everyone else. "
        f"The password comes from {OWNER_PASSWORD_ENV} or a prompt.",
    )
    create_owner_parser.add_argument("--email", required=True)
    create_owner_parser.add_argument("--username", required=True)

    args = parser.parse_args(argv)
    configure_logging(settings.log_level, settings.log_format)

    if args.command == "grant-api-login":
        _grant_api_login()
    elif args.command == "cleanup-sessions":
        deleted = run_session_cleanup()
        print(f"Deleted {deleted} stale session(s).")
    elif args.command == "create-owner":
        _create_owner(args.email, args.username)


if __name__ == "__main__":
    main()
