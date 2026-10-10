#!/usr/bin/env -S uv run --active python3
"""Thin runner for the pypostgres schema-sync tool."""
import sys

from pypostgres.tools.schema_sync import main, parse_args, _setup_logging

if __name__ == "__main__":
    args = parse_args(sys.argv)
    _setup_logging(args.verbose)
    main(config={"args": args})
