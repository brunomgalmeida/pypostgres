"""TimescaleDB handling for pypostgres, installed via the ``pypostgres[timescale]`` extra.

The core package never imports this module; import it explicitly with
``from pypostgres.timescale import TimescaleDB``. Requires a database with the
timescaledb extension installed.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class TSJob:
    """A TimescaleDB background job with its last-run statistics."""

    job_id: int
    application_name: str | None
    proc_schema: str | None
    proc_name: str
    hypertable_schema: str | None
    hypertable_name: str | None
    schedule_interval: timedelta
    fixed_schedule: bool
    scheduled: bool
    last_run_status: str | None
    last_start: datetime | None
    last_successful_finish: datetime | None
    next_start: datetime | None
    last_run_duration: timedelta | None
    total_runs: int | None
    total_successes: int | None
    total_failures: int | None

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("Job id cannot be empty")
        if not self.proc_name:
            raise ValueError("Job proc name cannot be empty")


@dataclass
class TSJobError:
    """One row of timescaledb_information.job_errors (needs a recent TimescaleDB)."""

    job_id: int
    proc_schema: str | None
    proc_name: str | None
    pid: int | None
    start_time: datetime | None
    finish_time: datetime | None
    sqlerrcode: str | None
    err_message: str | None

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("Job id cannot be empty")


@dataclass
class TSHypertable:
    """A hypertable with its dimensions, chunks and size (timescaledb_information.hypertables)."""

    hypertable_schema: str
    hypertable_name: str
    owner: str | None
    num_dimensions: int | None
    num_chunks: int | None
    compression_enabled: bool | None
    total_size: str | None
    total_bytes: int | None

    def __post_init__(self) -> None:
        if not self.hypertable_schema:
            raise ValueError("Hypertable schema cannot be empty")
        if not self.hypertable_name:
            raise ValueError("Hypertable name cannot be empty")


@dataclass
class TSChunk:
    """One chunk of a hypertable (timescaledb_information.chunks)."""

    hypertable_schema: str
    hypertable_name: str
    chunk_schema: str
    chunk_name: str
    range_start: datetime
    range_end: datetime
    is_compressed: bool | None

    def __post_init__(self) -> None:
        if not self.chunk_schema:
            raise ValueError("Chunk schema cannot be empty")
        if not self.chunk_name:
            raise ValueError("Chunk name cannot be empty")


class TimescaleDB:
    """Read-only facade over TimescaleDB informational views (mirrors PGUtils)."""

    def __init__(self, cur):
        if not cur:
            raise ValueError("Database cursor cannot be None")
        self.cur = cur

    def _map(self, model: type) -> list:
        return [model(**dict(row)) for row in self.cur.fetchall()]

    def get_hypertables(self) -> list[TSHypertable]:
        """All hypertables with size and chunk counts (timescaledb_information.hypertables)."""
        self.cur.execute(
            """
            SELECT h.hypertable_schema,
                   h.hypertable_name,
                   h.owner,
                   h.num_dimensions,
                   h.num_chunks,
                   h.compression_enabled,
                   pg_size_pretty(
                     hypertable_size(format('%I.%I', h.hypertable_schema, h.hypertable_name)::regclass)
                   ) AS total_size,
                   hypertable_size(format('%I.%I', h.hypertable_schema, h.hypertable_name)::regclass) AS total_bytes
            FROM timescaledb_information.hypertables h
            ORDER BY total_bytes DESC
            """
        )
        return self._map(TSHypertable)

    def get_chunks(self) -> list[TSChunk]:
        """Individual chunks, most recent first (timescaledb_information.chunks)."""
        self.cur.execute(
            """
            SELECT c.hypertable_schema, c.hypertable_name,
                   c.chunk_schema, c.chunk_name,
                   c.range_start, c.range_end,
                   c.is_compressed
            FROM timescaledb_information.chunks c
            ORDER BY c.hypertable_schema, c.hypertable_name, c.range_start DESC
            LIMIT 50
            """
        )
        return self._map(TSChunk)

    def get_jobs(self) -> list[TSJob]:
        """All jobs with last-run statistics (timescaledb_information.jobs)."""
        self.cur.execute(
            """
            SELECT j.job_id,
                   j.application_name,
                   j.proc_schema,
                   j.proc_name,
                   j.hypertable_schema,
                   j.hypertable_name,
                   j.schedule_interval,
                   j.scheduled,
                   j.fixed_schedule,
                   s.last_run_status,
                   s.last_run_started_at AS last_start,
                   s.last_successful_finish,
                   s.next_start,
                   s.last_run_duration,
                   s.total_runs,
                   s.total_successes,
                   s.total_failures
            FROM timescaledb_information.jobs j
            LEFT JOIN timescaledb_information.job_stats s USING (job_id)
            ORDER BY j.job_id
            """
        )
        return self._map(TSJob)

    def get_failed_jobs(self) -> list[TSJob]:
        """Jobs whose last run failed or accumulated failures (timescaledb_information.jobs)."""
        self.cur.execute(
            """
            SELECT j.job_id,
                   j.application_name,
                   j.proc_schema,
                   j.proc_name,
                   j.hypertable_schema,
                   j.hypertable_name,
                   j.schedule_interval,
                   j.scheduled,
                   j.fixed_schedule,
                   s.last_run_status,
                   s.last_run_started_at AS last_start,
                   s.last_successful_finish,
                   s.next_start,
                   s.last_run_duration,
                   s.total_runs,
                   s.total_successes,
                   s.total_failures
            FROM timescaledb_information.jobs j
            JOIN timescaledb_information.job_stats s USING (job_id)
            WHERE s.last_run_status = 'failed'
               OR s.total_failures > 0
            ORDER BY s.total_failures DESC, s.last_run_started_at DESC
            """
        )
        return self._map(TSJob)

    def get_long_running_jobs(self) -> list[TSJob]:
        """Jobs whose last run took longer than their schedule interval."""
        self.cur.execute(
            """
            SELECT j.job_id,
                   j.application_name,
                   j.proc_schema,
                   j.proc_name,
                   j.hypertable_schema,
                   j.hypertable_name,
                   j.schedule_interval,
                   j.scheduled,
                   j.fixed_schedule,
                   s.last_run_status,
                   s.last_run_started_at AS last_start,
                   s.last_successful_finish,
                   s.next_start,
                   s.last_run_duration,
                   s.total_runs,
                   s.total_successes,
                   s.total_failures
            FROM timescaledb_information.jobs j
            JOIN timescaledb_information.job_stats s USING (job_id)
            WHERE s.last_run_duration > j.schedule_interval
            ORDER BY s.last_run_duration DESC
            """
        )
        return self._map(TSJob)

    def get_job_errors(self, limit: int = 50) -> list[TSJobError]:
        """Recent job errors (timescaledb_information.job_errors; needs a recent TimescaleDB —
        on servers without the view the raw psycopg2 error is raised, nothing is guarded)."""
        self.cur.execute(
            """
            SELECT job_id,
                   proc_schema,
                   proc_name,
                   pid,
                   start_time,
                   finish_time,
                   sqlerrcode,
                   err_message
            FROM timescaledb_information.job_errors
            ORDER BY finish_time DESC
            LIMIT %s
            """,
            (limit,),
        )
        return self._map(TSJobError)
