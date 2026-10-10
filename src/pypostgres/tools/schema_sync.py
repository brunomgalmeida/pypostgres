#!/usr/bin/env -S uv run --active python3

"""
Compares the columns order and definitions across 2 databases/schemas.

Uses the pypostgres library to introspect and sync schema from a source
database/schema into a destination database/schema.

Example Usage:
export VIRTUAL_ENV="$HOME/dba/.venv/"
export UV_VENV="${VIRTUAL_ENV}"
x="postgresql://hostname:5432/postgres"
LOGLEVEL=WARNING pypg-schema-sync \
      --source      '{"uri": "'$x'", "schema": "public", "id":"source"}' \
      --destination '{"uri": "'$x'", "schema": "historical", "id":"destination"}' --ignore-missing-tables
"""

import argparse
import json
import logging
import os
import sys
from typing import Any

import pypostgres as psycopg2

logger = logging.getLogger(__name__)


def parse_args(cliargs: list[str]) -> argparse.Namespace:
    cliargs = cliargs[1:]  # remove the application name
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Dry run", default=False)
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")
    parser.add_argument("--source", help="Source", dest="source")
    parser.add_argument("--destination", help="Destination", dest="destination")
    parser.add_argument(
        "--ignore-missing-tables",
        action="store_true",
        help="Ignore missing tables in destination",
        default=False,
        dest="ignore_missing_tables",
    )

    found, not_found = parser.parse_known_args(cliargs)
    if not_found:
        raise Exception(f"Unknown args {not_found}")
    return found


class DBDiff:
    def __init__(self, uri: str, schema: str, **kwargs: Any):
        self.uri = uri
        self.schema = schema
        db_identifier = kwargs.get("id")
        self.id = db_identifier


def main(config: dict[str, str] = {}) -> None:
    args = config.get("args") or parse_args(sys.argv)

    db0 = DBDiff(**json.loads(args.source))
    db1 = DBDiff(**json.loads(args.destination))

    logging.info("Connecting to SRC")
    conn0 = psycopg2.connect(dsn=db0.uri)
    # conn0.set_isolation_level(0)
    conn0.readonly = True

    logging.info("Connecting to DST")
    conn1 = psycopg2.connect(dsn=db1.uri)

    cur0 = conn0.cursor()
    cur1 = conn1.cursor()

    cur0.execute("SELECT CURRENT_USER user, inet_server_port() port, inet_server_addr( ), inet_server_port( );")
    r = cur0.fetchone()
    logging.info(f"Connected to {db0.id} on {r}")

    cur0_utils = psycopg2.utils(cur0)
    cur1_utils = psycopg2.utils(cur1)

    # Get a list of all tables in schema
    tables0: list[Any] = cur0_utils.get_table_list(schema_name=db0.schema)
    logging.info(f"Found {len(tables0)} tables in '{db0.schema}' of '{db0.id}'")
    tables_ignore = []

    for table in tables0:
        table_name: str = table["table_name"]

        if table_name in tables_ignore:
            logging.info(f"Ignoring table: {table_name}")
            continue

        logging.info(f"Checking table: {table_name}")

        T0: psycopg2.PGTable = cur0_utils.get_table_schema(schema_name=db0.schema, table_name=table_name)
        T1: psycopg2.PGTable = cur1_utils.get_table_schema(schema_name=db1.schema, table_name=table_name)

        if T0.column != T1.column:
            if not T1.column:
                if not args.ignore_missing_tables:
                    logging.error(f"Table '{db1.schema}.{table_name}' does not exist in '{db1.id}'")
                else:
                    logging.debug(f"Table '{db1.schema}.{table_name}' does not exist in '{db1.id}', skipping")
                continue

            logging.info(f"Table '{T0.name}' has differences between {db0.id} and {db1.id}")
            for i in range(0, max(len(T0.column), len(T1.column))):
                col1: psycopg2.PGColumn | None = None
                col0: psycopg2.PGColumn | None = None

                try:
                    col0 = T0.column[i]
                except IndexError:
                    pass
                try:
                    col1 = T1.column[i]
                except IndexError:
                    pass

                # This is only from 0-->1, we SHOULD NEVER ALTER db0
                if col0 != col1:
                    logging.debug(f"[{table_name}] column {i}: {col0} vs {col1}")

                if not col1:
                    sql = f"ALTER TABLE {db1.schema}.{table_name} ADD COLUMN IF NOT EXISTS {col0.name} {col0.data_type}"
                    logging.warning(f"{db1.schema}.{table_name} is missing '{col0.name}' '{col0.data_type}' at position {col0.ordinal_position},\n\t{sql}")
                    cur1.execute(sql)

                elif not col0:
                    raise Exception(f"{db1.schema}.{table_name} has extra column '{col1.name}' '{col1.data_type}' at position {col1.ordinal_position}")

                elif col0.name != col1.name:
                    raise Exception(f"{db1.schema}.{table_name} column name mismatch at position {i}: '{col0.name}' != '{col1.name}'")

                elif col0.data_type != col1.data_type:
                    sql = f"ALTER TABLE {db1.schema}.{table_name} ALTER COLUMN {col1.name} SET DATA TYPE {col0.data_type}"
                    logging.warning(f"{db1.schema}.{table_name} data type mismatch:\n\t{sql}")
                    cur1.execute(sql)

        if not args.dry_run:
            # !! This is only from 0-->1, we SHOULD NEVER ALTER db0
            conn0.cancel()
            conn1.commit()


def _setup_logging(verbose: bool) -> None:
    console_logging = logging.StreamHandler(stream=sys.stdout)
    console_logging.setLevel(os.environ.get("LOGLEVEL", "WARNING"))
    if verbose:
        console_logging.setLevel(logging.DEBUG)
    logging.basicConfig(
        format=os.getenv("LOGFORMAT", "%(asctime)s.%(msecs)03d %(name)s@%(filename)s.%(funcName)s:%(lineno)03d %(levelname)s: %(message)s"),
        level=logging.DEBUG,
        handlers=[console_logging],
        datefmt="%Y-%m-%d %H:%M:%S",
    )


if __name__ == "__main__":
    args = parse_args(sys.argv)
    _setup_logging(args.verbose)
    main(config={"args": args})
