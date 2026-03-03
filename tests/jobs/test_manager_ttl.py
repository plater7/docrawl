"""Unit tests for Job TTL cleanup (src/jobs/manager.py) — PR 1.5."""

import time
from unittest.mock import MagicMock, patch

from src.jobs.manager import Job, JobManager


def _make_mock_request() -> MagicMock:
    """Return a MagicMock that stands in for a JobRequest.

    Avoids constructing a real JobRequest because the output_path validator
    calls Path.resolve() which returns a Windows-style path in CI,
    failing the '/data' prefix check.
    """
    req = MagicMock()
    req.output_path = "/data/output/test"
    return req


def _make_job(job_id: str = "test-job-1", completed_at: float | None = None) -> Job:
    """Return a Job with optional completed_at timestamp."""
    job = Job(id=job_id, request=_make_mock_request())
    job.completed_at = completed_at
    if completed_at is not None:
        job.status = "completed"
    return job


class TestJobManagerCleanupOldJobs:
    """Tests for JobManager.cleanup_old_jobs() TTL behaviour — PR 1.5."""

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

    async def test_keeps_running_jobs_with_no_completed_at(self):
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
        """cleanup_old_jobs() returns the exact count of removed jobs."""
        manager = JobManager()
        old_ts = time.time() - 7200

        for i in range(3):
            job = _make_job(f"expired-{i}", completed_at=old_ts)
            manager._jobs[f"expired-{i}"] = job

        recent_job = _make_job("recent", completed_at=time.time() - 10)
        manager._jobs["recent"] = recent_job

        with patch.dict("os.environ", {"JOB_TTL_SECONDS": "3600"}):
            removed = await manager.cleanup_old_jobs()

        assert removed == 3
        assert "recent" in manager._jobs

    async def test_cleanup_disabled_when_ttl_is_zero(self):
        """When JOB_TTL_SECONDS=0, no jobs are removed regardless of age."""
        manager = JobManager()
        old_job = _make_job("old-job", completed_at=time.time() - 99999)
        manager._jobs["old-job"] = old_job

        with patch.dict("os.environ", {"JOB_TTL_SECONDS": "0"}):
            removed = await manager.cleanup_old_jobs()

        assert removed == 0
        assert "old-job" in manager._jobs
