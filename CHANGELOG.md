# CHANGELOG

## v0.0.2 (2026-10-10)

- `Inspector` now introspects installed extensions into `PGDatabase.extensions` (`PGExtension` name + version).
- New optional extra `pypostgres[timescale]`: `TimescaleDB` cursor facade returning typed models (`TSJob`, `TSJobError`, `TSHypertable`, `TSChunk`) from `timescaledb_information` — jobs (all/failed/long-running/errors), hypertables and chunks. Verified against TimescaleDB 2.30.
- Package version is now derived from git tags (hatch-vcs) instead of a hardcoded `pyproject.toml` value.

## v0.0.1

- Initial release: dict-style cursor, `CustomCursor.to_csv()`, `Inspector`, `PGUtils`, monthly partition helpers.
