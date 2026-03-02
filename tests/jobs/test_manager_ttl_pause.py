"""Unit tests for Job TTL cleanup (PR 1.5) and pause/resume (PR 3.1).

Source: src/jobs/manager.py
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.jobs.manager import Job, JobManager


def _make_mock_request() -> MagicMock:
    """Return a MagicMock that stands in for a JobRequest.

    We avoid constructing a real JobRequest because the output_path validator
    calls Path.resolve() which returns a Windows-style path in the CI
    environment, failing the '/data' prefix check.
    """
    req = MagicMock()
    req.output_path = "/data/output/test"
    return req


def _make_job(job_id: str = "test-job-1", completed_at: float | None = None) -> Job:
    """Return a Job instance with optional completed_at timestamp."""
    job = Job(id=job_id, request=_make_mock_request())
    job.completed_at = completed_at
    if completed_at is not None:
        job.status = "completed"
    return job


class TestJobManagerCleanupOldJobs:
    """Tests for JobManager.cleanup_old_jobs() TTL behaviour (PR 1.5)."""

    async def test_removes_jobs_older_than_ttl(self):
        """Jobs whose completed_at is older than JOB_TTL_SECONDS are removed."""
        manager = JobManager()
        old_ts = time.time() - 7200  # 2 hours ago
        old_job = _make_job("old-job", completed_at=old_ts)
        manager._jobs["old-job"] = old_job

        with patch.dict("os.environ", {"JOB_TTL_SECONDS": "3600"}):
            removed = await manager.cleanup_old_jobs()

        assert removed == 1
        assert "old-job" not in manager._jobs

    async def test_keeps_jobs_with_recent_completed_at(self):
        """Jobs completed recently (within TTL) are not removed."""
        manager = JobManager()
        recent_ts = time.time() - 60  # 1 minute ago
        recent_job = _make_job("recent-job", completed_at=recent_ts)
        manager._jobs["recent-job"] = recent_job

        with patch.dict("os.environ", {"JOB_TTL_SECONDS": "3600"}):
            removed = await manager.cleanup_old_jobs()

        assert removed == 0
        assert "recent-job" in manager._jobs

    async def test_keeps_jobs_with_none_completed_at(self):
        """Jobs still running (completed_at=None) are never removed by TTL cleanup."""
        manager = JobManager()
        running_job = _make_job("running-job", completed_at=None)
        running_job.status = "running"
        manager._jobs["running-job"] = running_job

        with patch.dict("os.environ", {"JOB_TTL_SECONDS": "3600"}):
            removed = await manager.cleanup_old_jobs()

        assert removed == 0
        assert "running-job" in manager._jobs

    async def test_returns_count_of_removed_jobs(self):
        """cleanup_old_jobs() returns the exact number of jobs removed."""
        manager = JobManager()
        old_ts = time.time() - 7200

        for i in range(3):
            job = _make_job(f"expired-job-{i}", completed_at=old_ts)
            manager._jobs[f"expired-job-{i}"] = job

        # Add one recent job that must survive
        recent_job = _make_job("recent-job", completed_at=time.time() - 10)
        manager._jobs["recent-job"] = recent_job

        with patch.dict("os.environ", {"JOB_TTL_SECONDS": "3600"}):
            removed = await manager.cleanup_old_jobs()

        assert removed == 3
        assert "recent-job" in manager._jobs

    async def test_cleanup_disabled_when_ttl_is_zero(self):
        """When JOB_TTL_SECONDS=0, cleanup is disabled and no jobs are removed."""
        manager = JobManager()
        old_job = _make_job("old-job", completed_at=time.time() - 9999)
        manager._jobs["old-job"] = old_job

        with patch.dict("os.environ", {"JOB_TTL_SECONDS": "0"}):
            removed = await manager.cleanup_old_jobs()

        assert removed == 0
        assert "old-job" in manager._jobs


class TestJobPause:
    """Tests for Job.pause() — PR 3.1."""

    def test_pause_sets_paused_to_true(self):
        """pause() sets _paused to True on a running job."""
        job = _make_job()
        job.status = "running"

        result = job.pause()

        assert result is True
        assert job._paused is True

    def test_pause_clears_the_pause_event(self):
        """pause() calls clear() on the internal asyncio.Event (set=running → clear=paused)."""
        job = _make_job()
        job.status = "running"

        job.pause()

        assert not job._pause_event.is_set()

    def test_pause_sets_status_to_paused(self):
        """pause() updates the job status to 'paused'."""
        job = _make_job()
        job.status = "running"

        job.pause()

        assert job.status == "paused"

    def test_pause_returns_false_for_completed_job(self):
        """pause() returns False when the job is not in a pauseable state."""
        job = _make_job()
        job.status = "completed"

        result = job.pause()

        assert result is False
        assert job._paused is False


class TestJobResume:
    """Tests for Job.resume() — PR 3.1."""

    def test_resume_sets_paused_to_false(self):
        """resume() clears the _paused flag on a paused job."""
        job = _make_job()
        job.status = "running"
        job.pause()

        result = job.resume()

        assert result is True
        assert job._paused is False

    def test_resume_sets_pause_event(self):
        """resume() sets the asyncio.Event, unblocking wait_if_paused()."""
        job = _make_job()
        job.status = "running"
        job.pause()

        job.resume()

        assert job._pause_event.is_set()

    def test_resume_sets_status_to_running(self):
        """resume() changes the job status back to 'running'."""
        job = _make_job()
        job.status = "running"
        job.pause()

        job.resume()

        assert job.status == "running"

    def test_resume_returns_false_when_job_is_not_paused(self):
        """resume() returns False when the job is not in the 'paused' state."""
        job = _make_job()
        job.status = "running"

        result = job.resume()

        assert result is False


class TestJobWaitIfPaused:
    """Tests for Job.wait_if_paused() — PR 3.1."""

    async def test_returns_immediately_when_not_paused(self):
        """wait_if_paused() completes without blocking when the job is running."""
        job = _make_job()
        # _pause_event is set (running state) by default

        # Should complete without hanging
        await asyncio.wait_for(job.wait_if_paused(), timeout=1.0)

    async def test_unblocks_after_resume(self):
        """wait_if_paused() blocks while paused and unblocks when resume() is called."""
        job = _make_job()
        job.status = "running"
        job.pause()  # clears the event → will block

        async def _resume_after_delay() -> None:
            await asyncio.sleep(0.05)
            job.resume()

        asyncio.create_task(_resume_after_delay())
        # If resume() works correctly this will complete within the timeout
        await asyncio.wait_for(job.wait_if_paused(), timeout=1.0)

        assert job._paused is False
