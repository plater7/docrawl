"""Tests for JobManager.active_job_count in src/jobs/manager.py."""

import pytest

from src.api.models import JobRequest
from src.jobs.manager import Job, JobManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request() -> JobRequest:
    """Return a minimal valid JobRequest."""
    return JobRequest(
        url="https://example.com",
        crawl_model="model",
        pipeline_model="model",
        reasoning_model="model",
    )


def _make_job(status: str) -> Job:
    """Create a Job with the given status without starting a task."""
    job = Job(id="test-id", request=_make_request(), status=status)
    return job


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestActiveJobCount:
    """Unit tests for JobManager.active_job_count."""

    def test_empty_manager_returns_zero(self):
        """With no jobs registered, active count is 0."""
        manager = JobManager()
        assert manager.active_job_count() == 0

    def test_single_pending_job_counts_as_active(self):
        """A job in 'pending' status is counted."""
        manager = JobManager()
        job = _make_job("pending")
        manager._jobs[job.id] = job
        assert manager.active_job_count() == 1

    def test_single_running_job_counts_as_active(self):
        """A job in 'running' status is counted."""
        manager = JobManager()
        job = _make_job("running")
        manager._jobs[job.id] = job
        assert manager.active_job_count() == 1

    def test_completed_job_not_counted(self):
        """A job in 'completed' status does not count as active."""
        manager = JobManager()
        job = _make_job("completed")
        manager._jobs[job.id] = job
        assert manager.active_job_count() == 0

    def test_cancelled_job_not_counted(self):
        """A job in 'cancelled' status does not count as active."""
        manager = JobManager()
        job = _make_job("cancelled")
        manager._jobs[job.id] = job
        assert manager.active_job_count() == 0

    def test_failed_job_not_counted(self):
        """A job in 'failed' status does not count as active."""
        manager = JobManager()
        job = _make_job("failed")
        manager._jobs[job.id] = job
        assert manager.active_job_count() == 0

    def test_mixed_statuses_counts_only_active(self):
        """Only pending and running jobs are counted in a mixed set."""
        manager = JobManager()
        statuses = ["pending", "pending", "running", "completed", "cancelled"]
        for i, status in enumerate(statuses):
            job = Job(id=f"job-{i}", request=_make_request(), status=status)
            manager._jobs[job.id] = job
        # 2 pending + 1 running = 3
        assert manager.active_job_count() == 3

    def test_all_completed_returns_zero(self):
        """When all jobs are completed, active count is 0."""
        manager = JobManager()
        for i in range(4):
            job = Job(id=f"job-{i}", request=_make_request(), status="completed")
            manager._jobs[job.id] = job
        assert manager.active_job_count() == 0

    def test_multiple_pending_jobs(self):
        """Multiple pending jobs are all counted."""
        manager = JobManager()
        for i in range(5):
            job = Job(id=f"job-{i}", request=_make_request(), status="pending")
            manager._jobs[job.id] = job
        assert manager.active_job_count() == 5
