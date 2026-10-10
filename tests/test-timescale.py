from datetime import datetime, timedelta

import pytest

from pypostgres.timescale import TSJob, TSJobError


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
