#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import settings
from src.db import Base

# Import models so SQLAlchemy metadata contains every application table.
from src.models import error_pattern as _error_pattern  # noqa: F401
from src.models import explore as _explore  # noqa: F401
from src.models import learner as _learner  # noqa: F401
from src.models import runtime as _runtime  # noqa: F401
from src.models import session as _session  # noqa: F401
from src.models import vocabulary as _vocabulary  # noqa: F401


CONFIRM_TOKEN = "RESET_ALL_DATA"
LOCAL_DATABASE_HOSTS = {"localhost", "127.0.0.1", "::1", "db", "postgres"}
PROTECTED_TABLES = {"alembic_version"}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely clear local BinnAgent application data."
    )
    parser.add_argument(
        "--database-url",
        default=settings.database_url,
        help="Database URL to reset. Defaults to BINN_DATABASE_URL.",
    )
    parser.add_argument(
        "--confirm",
        help=f"Required token for destructive reset: {CONFIRM_TOKEN}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Always inspect row counts without deleting data.",
    )
    parser.add_argument(
        "--allow-non-local",
        action="store_true",
        help="Allow resetting a database whose host is not localhost/db/postgres.",
    )
    return parser.parse_args(argv)


def app_tables() -> list[str]:
    return sorted(
        table_name
        for table_name in Base.metadata.tables
        if table_name not in PROTECTED_TABLES
    )


def is_local_database(database_url: str) -> bool:
    parsed = urlparse(database_url)
    host = parsed.hostname
    if not host:
        return False
    return host in LOCAL_DATABASE_HOSTS


def quote_identifier(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) + chr(34))}"'


def qualified_table_name(table_name: str) -> str:
    table = Base.metadata.tables[table_name]
    if table.schema:
        return f"{quote_identifier(table.schema)}.{quote_identifier(table.name)}"
    return quote_identifier(table.name)


async def collect_counts(conn) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name in app_tables():
        result = await conn.execute(
            text(f"SELECT count(*) FROM {qualified_table_name(table_name)}")
        )
        counts[table_name] = int(result.scalar_one())
    return counts


def print_counts(counts: dict[str, int]) -> None:
    width = max((len(table_name) for table_name in counts), default=5)
    print("Application tables:")
    for table_name, count in counts.items():
        print(f"  {table_name:<{width}}  rows={count}")


async def reset_database(
    *,
    database_url: str,
    dry_run: bool,
    confirm: str | None,
    allow_non_local: bool,
) -> int:
    if not is_local_database(database_url) and not allow_non_local:
        print(
            "Refusing to reset a non-local database. "
            "Pass --allow-non-local only if you fully understand the risk.",
            file=sys.stderr,
        )
        return 2

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            print(f"Database: {database_url}")
            before_counts = await collect_counts(conn)
            print_counts(before_counts)

            should_delete = confirm == CONFIRM_TOKEN and not dry_run
            if not should_delete:
                print(
                    "\nDry run only. Re-run with "
                    f"--confirm {CONFIRM_TOKEN} to clear these tables."
                )
                return 0

            qualified_names = ", ".join(
                qualified_table_name(table_name) for table_name in app_tables()
            )
            if qualified_names:
                await conn.execute(
                    text(f"TRUNCATE TABLE {qualified_names} RESTART IDENTITY CASCADE")
                )

            print("\nData cleared. Verifying row counts:")
            after_counts = await collect_counts(conn)
            print_counts(after_counts)
            print(
                "\nBrowser note: any stale learner cached in localStorage will be "
                "removed automatically when the app refreshes learner state."
            )
            return 0
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    dry_run = args.dry_run or args.confirm != CONFIRM_TOKEN
    return asyncio.run(
        reset_database(
            database_url=args.database_url,
            dry_run=dry_run,
            confirm=args.confirm,
            allow_non_local=args.allow_non_local,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
