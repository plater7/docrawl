"""
Unit tests for src/jobs/manager.py

Tests cover:
- Job.cancel() sets status and is_cancelled flag
- Job.emit_event() / Job.event_stream() — emit and receive events
- JobManager.get_job() returns None for unknown id
- JobManager.cancel_job() returns None for unknown id
- JobManager.create_job() creates job with unique UUID id and status="pending"
- JobManager.active_job_count() counts only pending/running jobs
"""

from unittest.mock import patch

from src.api.models import JobRequest
from src.jobs.manager import Job, JobManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(**overrides) -> JobRequest:
    """Build a minimal valid JobRequest."""
    base = {
        "url": "https://example.com",
        "crawl_model": "mistral:7b",
        "pipeline_model": "qwen3:14b",
        "reasoning_model": "deepseek-r1:32b",
    }
    base.update(overrides)
    return JobRequest(**base)


def _make_job(status: str) -> Job:
    """Create a Job with the given status without starting a task."""
    job = Job(id="test-id", request=_make_request(), status=status)
    return job


# ---------------------------------------------------------------------------
# TestJobCancel
# ---------------------------------------------------------------------------


class TestJobCancel:
    """Test Job.cancel() behaviour."""

    def test_cancel_sets_status_cancelled(self):
        """cancel() should set status to 'cancelled'."""
        job = Job(id="test-id", request=_make_request())
        assert job.status == "pending"
        job.cancel()
        assert job.status == "cancelled"

    def test_cancel_sets_is_cancelled_flag(self):
        """cancel() should set is_cancelled to True."""
        job = Job(id="test-id", request=_make_request())
        assert job.is_cancelled is False
        job.cancel()
        assert job.is_cancelled is True

    def test_cancel_idempotent(self):
        """Calling cancel() twice should not raise."""
        job = Job(id="test-id", request=_make_request())
        job.cancel()
        job.cancel()
        assert job.status == "cancelled"
        assert job.is_cancelled is True


# ---------------------------------------------------------------------------
# TestJobEmitEvent
# ---------------------------------------------------------------------------


class TestJobEmitEvent:
    """Test Job.emit_event() and Job.event_stream()."""

    async def test_emit_event_puts_to_queue(self):
        """emit_event should place an event dict on the internal queue."""
        job = Job(id="test-id", request=_make_request())
        await job.emit_event("phase_change", {"phase": "discovery"})
        assert not job._events.empty()

    async def test_emit_event_structure(self):
        """Emitted event should have 'event' and 'data' keys."""
        job = Job(id="test-id", request=_make_request())
        await job.emit_event("log", {"message": "hello"})
        event = await job._events.get()
        assert event["event"] == "log"
        assert "hello" in event["data"]

    async def test_event_stream_yields_events(self):
        """event_stream should yield all queued events until terminal event."""
        job = Job(id="test-id", request=_make_request())

        # Pre-populate the queue with events
        await job.emit_event("phase_change", {"phase": "discovery"})
        await job.emit_event("log", {"message": "crawling"})
        await job.emit_event("job_done", {"status": "completed"})

        received = []
        async for event in job.event_stream():
            received.append(event)
            # job_done is the terminal event — stream will break after this

        assert len(received) == 3
        assert received[0]["event"] == "phase_change"
        assert received[1]["event"] == "log"
        assert received[2]["event"] == "job_done"

    async def test_event_stream_stops_on_job_cancelled(self):
        """event_stream should stop after 'job_cancelled' terminal event."""
        job = Job(id="test-id", request=_make_request())
        await job.emit_event("job_cancelled", {"pages_completed": 5})

        received = []
        async for event in job.event_stream():
            received.append(event)

        assert len(received) == 1
        assert received[0]["event"] == "job_cancelled"

    async def test_emit_multiple_events(self):
        """Multiple events should all be emitted correctly."""
        job = Job(id="test-id", request=_make_request())
        for i in range(5):
            await job.emit_event("log", {"index": i})
        await job.emit_event("job_done", {"status": "completed"})

        received = []
        async for event in job.event_stream():
            received.append(event)

        assert len(received) == 6
        assert received[-1]["event"] == "job_done"


# ---------------------------------------------------------------------------
# TestActiveJobCount
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


# ---------------------------------------------------------------------------
# TestJobManagerGetJob
# ---------------------------------------------------------------------------


class TestJobManagerGetJob:
    """Test JobManager.get_job() behaviour."""

    def test_get_job_returns_none_for_unknown_id(self):
        """get_job should return None for a non-existent job ID."""
        manager = JobManager()
        result = manager.get_job("non-existent-id")
        assert result is None

    def test_get_job_returns_none_for_empty_string(self):
        """get_job should return None for empty string ID."""
        manager = JobManager()
        result = manager.get_job("")
        assert result is None

    async def test_get_job_returns_existing_job(self):
        """get_job should return the job after it has been created."""
        manager = JobManager()
        with patch("src.jobs.manager.asyncio.create_task"):
            job = await manager.create_job(_make_request())

        retrieved = manager.get_job(job.id)
        assert retrieved is job


# ---------------------------------------------------------------------------
# TestJobManagerCancelJob
# ---------------------------------------------------------------------------


class TestJobManagerCancelJob:
    """Test JobManager.cancel_job() behaviour."""

    async def test_cancel_job_returns_none_for_unknown_id(self):
        """cancel_job should return None for a non-existent job ID."""
        manager = JobManager()
        result = await manager.cancel_job("non-existent-id")
        assert result is None

    async def test_cancel_job_returns_job_when_found(self):
        """cancel_job should return the job when it exists."""
        manager = JobManager()
        with patch("src.jobs.manager.asyncio.create_task"):
            job = await manager.create_job(_make_request())

        result = await manager.cancel_job(job.id)
        assert result is job

    async def test_cancel_job_sets_cancelled_status(self):
        """cancel_job should mark the job as cancelled."""
        manager = JobManager()
        with patch("src.jobs.manager.asyncio.create_task"):
            job = await manager.create_job(_make_request())

        await manager.cancel_job(job.id)
        assert job.status == "cancelled"
        assert job.is_cancelled is True


# ---------------------------------------------------------------------------
# TestJobManagerCreateJob
# ---------------------------------------------------------------------------


class TestJobManagerCreateJob:
    """Test JobManager.create_job() behaviour."""

    async def test_create_job_returns_job_with_pending_status(self):
        """create_job should return a Job with status='pending'."""
        manager = JobManager()
        with patch("src.jobs.manager.asyncio.create_task"):
            job = await manager.create_job(_make_request())
        assert job.status == "pending"

    async def test_create_job_returns_job_with_uuid_id(self):
        """create_job should return a Job with a UUID string as id."""
        import uuid

        manager = JobManager()
        with patch("src.jobs.manager.asyncio.create_task"):
            job = await manager.create_job(_make_request())
        # Validate it's a valid UUID string
        parsed = uuid.UUID(job.id)
        assert str(parsed) == job.id

    async def test_create_job_produces_unique_ids(self):
        """Each create_job call should produce a different job ID."""
        manager = JobManager()
        with patch("src.jobs.manager.asyncio.create_task"):
            job1 = await manager.create_job(_make_request())
            job2 = await manager.create_job(_make_request())
        assert job1.id != job2.id

    async def test_create_job_stores_job_in_manager(self):
        """Created job should be retrievable via get_job."""
        manager = JobManager()
        with patch("src.jobs.manager.asyncio.create_task"):
            job = await manager.create_job(_make_request())

        assert manager.get_job(job.id) is job

    async def test_create_job_stores_request(self):
        """Created job should carry the original request."""
        manager = JobManager()
        request = _make_request(delay_ms=999)
        with patch("src.jobs.manager.asyncio.create_task"):
            job = await manager.create_job(request)
        assert job.request.delay_ms == 999

    async def test_create_job_does_not_run_actual_runner(self):
        """create_job with mocked create_task should not run the runner."""
        manager = JobManager()
        runner_called = []

        async def fake_run_job(job):
            runner_called.append(job.id)

        with patch("src.jobs.manager.asyncio.create_task") as mock_task:
            await manager.create_job(_make_request())
            # create_task was called once (to schedule the runner)
            mock_task.assert_called_once()
            # But the runner itself was not awaited/run
            assert len(runner_called) == 0

    async def test_create_multiple_jobs(self):
        """Multiple jobs should all be stored and retrievable."""
        manager = JobManager()
        jobs = []
        with patch("src.jobs.manager.asyncio.create_task"):
            for _ in range(3):
                job = await manager.create_job(_make_request())
                jobs.append(job)

        for job in jobs:
            assert manager.get_job(job.id) is job
