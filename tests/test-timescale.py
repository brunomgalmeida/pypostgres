from datetime import datetime, timedelta

import pytest

from pypostgres.timescale import TSJob, TSJobError, TSHypertable, TSChunk, TimescaleDB


def _tsjob(**over):
    base = dict(job_id=1, application_name="Retention Policy JS Proc",
                proc_schema="public", proc_name="policy_retention",
                hypertable_schema="public", hypertable_name="metrics",
                schedule_interval=timedelta(days=1), fixed_schedule=False,
                scheduled=True, last_run_status="Success",
                last_start=None, last_successful_finish=None,
                next_start=None, last_run_duration=None,
                total_runs=0, total_successes=0, total_failures=0)
    return TSJob(**{**base, **over})


def test_tsjob_creation():
    job = _tsjob()
    assert job.job_id == 1
    assert job.scheduled is True


def test_tsjob_empty_job_id_raises():
    with pytest.raises(ValueError, match="Job id cannot be empty"):
        _tsjob(job_id=0)


def test_tsjob_empty_proc_name_raises():
    with pytest.raises(ValueError, match="Job proc name cannot be empty"):
        _tsjob(proc_name="")


def test_tsjoberror_creation_and_validation():
    err = TSJobError(job_id=1, proc_schema="public", proc_name="p",
                     pid=123, start_time=None, finish_time=None,
                     sqlerrcode=None, err_message="boom")
    assert err.err_message == "boom"
    with pytest.raises(ValueError, match="Job id cannot be empty"):
        TSJobError(job_id=0, proc_schema=None, proc_name=None, pid=None,
                   start_time=None, finish_time=None, sqlerrcode=None,
                   err_message="boom")


def _tshypertable(**over):
    base = dict(hypertable_schema="public", hypertable_name="metrics",
                owner="postgres", num_dimensions=2, num_chunks=4,
                compression_enabled=True, total_size="4096 bytes",
                total_bytes=4096)
    return TSHypertable(**{**base, **over})


def test_tshypertable_creation_and_validation():
    ht = _tshypertable()
    assert ht.total_bytes == 4096
    with pytest.raises(ValueError, match="Hypertable name cannot be empty"):
        _tshypertable(hypertable_name="")
    with pytest.raises(ValueError, match="Hypertable schema cannot be empty"):
        _tshypertable(hypertable_schema="")


def test_tschunk_creation_and_validation():
    ch = TSChunk(hypertable_schema="public", hypertable_name="metrics",
                 chunk_schema="_timescaledb_internal",
                 chunk_name="_hyper_1_1_chunk",
                 range_start=datetime(2026, 1, 1),
                 range_end=datetime(2026, 2, 1), is_compressed=False)
    assert ch.chunk_name.endswith("chunk")
    with pytest.raises(ValueError, match="Chunk name cannot be empty"):
        TSChunk(hypertable_schema="public", hypertable_name="m",
                chunk_schema="s", chunk_name="",
                range_start=datetime(2026, 1, 1),
                range_end=datetime(2026, 2, 1), is_compressed=False)
    with pytest.raises(ValueError, match="Chunk schema cannot be empty"):
        TSChunk(hypertable_schema="public", hypertable_name="m",
                chunk_schema="", chunk_name="c",
                range_start=datetime(2026, 1, 1),
                range_end=datetime(2026, 2, 1), is_compressed=False)


def test_timescaledb_requires_cursor():
    with pytest.raises(ValueError, match="Database cursor cannot be None"):
        TimescaleDB(None)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *a, **k):
        pass

    def fetchall(self):
        return self._rows


def test_get_hypertables_maps_rows():
    rows = [dict(hypertable_schema="public", hypertable_name="metrics",
                 owner="postgres", num_dimensions=2, num_chunks=4,
                 compression_enabled=True, total_size="4096 bytes",
                 total_bytes=4096)]
    result = TimescaleDB(_FakeCursor(rows)).get_hypertables()
    assert result == [TSHypertable(**rows[0])]
