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
    is_distributed: bool | None
    replication_factor: int | None
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
