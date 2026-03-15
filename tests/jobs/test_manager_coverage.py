"""
Targeted tests to increase coverage of src/jobs/manager.py.

Covers areas NOT already tested in test_manager.py and test_manager_ttl_pause.py:
- event_stream(): TimeoutError + dead task with exception → job_done/failed
- event_stream(): TimeoutError + dead task that was cancelled → job_done/failed
- event_stream(): TimeoutError + alive task → keepalive ping
- event_stream(): GeneratorExit handler
- event_stream(): generic Exception handler
- event_stream(): job_error terminal event stops stream
- create_job() _on_done callback: exception path (job.status == "running")
- create_job() _on_done callback: t.cancelled() path
- JobManager.shutdown(): with running tasks
- JobManager.shutdown(): with no running tasks (early return)
- JobManager.create_resume_job(): stores job, skips discovery
- JobManager.create_resume_job(): _on_done with exception
- JobManager.start_cleanup_loop(): runs cleanup and handles CancelledError
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.models import JobRequest
from src.jobs.manager import Job, JobManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(**overrides) -> JobRequest:
    base = {
        "url": "https://example.com",
        "crawl_model": "mistral:7b",
        "pipeline_model": "qwen3:14b",
        "reasoning_model": "deepseek-r1:32b",
    }
    base.update(overrides)
    return JobRequest(**base)


def _make_mock_task(done: bool = True, cancelled: bool = False, exception=None):
    """Build a synchronous MagicMock that mimics an asyncio.Task."""
    t = MagicMock()
    t.done.return_value = done
    t.cancelled.return_value = cancelled
    if cancelled:
        t.exception.side_effect = asyncio.CancelledError()
    else:
        t.exception.return_value = exception
    return t


# ---------------------------------------------------------------------------
# TestEventStreamTimeoutDeadTask
# ---------------------------------------------------------------------------


class TestEventStreamTimeoutDeadTask:
    """event_stream() TimeoutError paths when the runner task has died."""

    async def test_timeout_dead_task_with_exception_yields_job_done(self):
        """When the task is done and has an exception, yield job_done with error."""
        job = Job(id="j1", request=_make_request())
        job._task = _make_mock_task(
            done=True, cancelled=False, exception=RuntimeError("boom")
        )

        call_count = 0
        original_wait_for = asyncio.wait_for

        async def patched_wait_for(coro, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Close the coroutine to prevent ResourceWarning
                coro.close()
                raise asyncio.TimeoutError()
            return await original_wait_for(coro, timeout)

        received = []
        with patch("src.jobs.manager.asyncio.wait_for", side_effect=patched_wait_for):
            async for event in job.event_stream():
                received.append(event)

        assert len(received) == 1
        assert received[0]["event"] == "job_done"
        data = json.loads(received[0]["data"])
        assert data["status"] == "failed"
        assert "boom" in data["error"]

    async def test_timeout_dead_task_cancelled_yields_job_done_unexpected(self):
        """When the task is done and was cancelled, yield job_done with generic message."""
        job = Job(id="j2", request=_make_request())
        job._task = _make_mock_task(done=True, cancelled=True)

        call_count = 0
        original_wait_for = asyncio.wait_for

        async def patched_wait_for(coro, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                coro.close()
                raise asyncio.TimeoutError()
            return await original_wait_for(coro, timeout)

        received = []
        with patch("src.jobs.manager.asyncio.wait_for", side_effect=patched_wait_for):
            async for event in job.event_stream():
                received.append(event)

        assert len(received) == 1
        assert received[0]["event"] == "job_done"
        data = json.loads(received[0]["data"])
        assert data["status"] == "failed"
        assert "unexpectedly" in data["error"]


# ---------------------------------------------------------------------------
# TestEventStreamKeepalive
# ---------------------------------------------------------------------------


class TestEventStreamKeepalive:
    """event_stream() keepalive path when timeout occurs but task is still alive."""

    async def test_timeout_alive_task_yields_keepalive(self):
        """When task is still running after timeout, a keepalive event is yielded."""
        job = Job(id="j3", request=_make_request())
        job._task = _make_mock_task(done=False)

        timeout_count = 0
        original_wait_for = asyncio.wait_for

        async def patched_wait_for(coro, timeout):
            nonlocal timeout_count
            timeout_count += 1
            if timeout_count == 1:
                # First call: timeout (task alive → keepalive)
                coro.close()
                raise asyncio.TimeoutError()
            # Second call: return a terminal event so the loop ends
            coro.close()
            return {"event": "job_done", "data": json.dumps({"status": "completed"})}

        received = []
        with patch("src.jobs.manager.asyncio.wait_for", side_effect=patched_wait_for):
            async for event in job.event_stream():
                received.append(event)

        events = [e["event"] for e in received]
        assert "keepalive" in events
        assert received[0]["event"] == "keepalive"
        assert received[1]["event"] == "job_done"

    async def test_keepalive_has_expected_data(self):
        """Keepalive event should have empty JSON data."""
        job = Job(id="j4", request=_make_request())
        job._task = _make_mock_task(done=False)

        call_count = 0
        original_wait_for = asyncio.wait_for

        async def patched_wait_for(coro, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                coro.close()
                raise asyncio.TimeoutError()
            coro.close()
            return {"event": "job_cancelled", "data": "{}"}

        with patch("src.jobs.manager.asyncio.wait_for", side_effect=patched_wait_for):
            async for event in job.event_stream():
                if event["event"] == "keepalive":
                    assert event["data"] == "{}"
                    break


# ---------------------------------------------------------------------------
# TestEventStreamTerminalEvents
# ---------------------------------------------------------------------------


class TestEventStreamTerminalEvents:
    """event_stream() stops on all three terminal event types."""

    async def test_job_error_stops_stream(self):
        """job_error terminal event should stop the event stream."""
        job = Job(id="j5", request=_make_request())
        await job.emit_event("job_error", {"error": "something broke"})

        received = []
        async for event in job.event_stream():
            received.append(event)

        assert len(received) == 1
        assert received[0]["event"] == "job_error"

    async def test_job_done_stops_stream_immediately(self):
        """After job_done, no further events should be consumed."""
        job = Job(id="j6", request=_make_request())
        await job.emit_event("job_done", {"status": "completed"})
        # Extra event that should NOT be yielded
        await job.emit_event("log", {"message": "after done"})

        received = []
        async for event in job.event_stream():
            received.append(event)

        assert len(received) == 1
        assert received[0]["event"] == "job_done"


# ---------------------------------------------------------------------------
# TestEventStreamExceptionHandlers
# ---------------------------------------------------------------------------


class TestEventStreamExceptionHandlers:
    """event_stream() GeneratorExit and generic Exception handlers."""

    async def test_generator_exit_is_handled_gracefully(self):
        """GeneratorExit from client disconnect should not propagate."""
        job = Job(id="j7", request=_make_request())

        # Put a non-terminal event so the loop stays alive, then break early
        await job.emit_event("log", {"message": "hello"})

        # Collect only the first event then break — simulates client disconnect
        received = []
        gen = job.event_stream()
        try:
            async for event in gen:
                received.append(event)
                # Force close the generator (mimics sse_starlette disconnecting)
                await gen.aclose()
                break
        except StopAsyncIteration:
            pass

        # Should have received the log event without error
        assert received[0]["event"] == "log"

    async def test_generic_exception_in_event_stream_is_caught(self):
        """A generic exception inside event_stream should be caught and logged."""
        job = Job(id="j8", request=_make_request())

        async def exploding_wait_for(coro, timeout):
            coro.close()
            raise ValueError("unexpected failure")

        received = []
        with patch(
            "src.jobs.manager.asyncio.wait_for", side_effect=exploding_wait_for
        ):
            # Should not raise — exception is caught internally
            async for event in job.event_stream():
                received.append(event)  # pragma: no cover

        # No events yielded; exception was swallowed
        assert received == []


# ---------------------------------------------------------------------------
# TestOnDoneCallback
# ---------------------------------------------------------------------------


class TestOnDoneCallback:
    """_on_done callback inside create_job() and create_resume_job()."""

    async def test_on_done_with_exception_sets_status_failed_when_running(self):
        """If runner task throws and job.status is 'running', set to 'failed'."""
        manager = JobManager()

        # We'll capture the done callback and invoke it manually
        captured_callback = None

        def fake_add_done_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_task = MagicMock()
        mock_task.add_done_callback = fake_add_done_callback
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = RuntimeError("runner crashed")

        def make_create_task(t):
            """Return a create_task side_effect that closes the coro and returns t."""
            return lambda coro: coro.close() or t

        with patch(
            "src.jobs.manager.asyncio.create_task",
            side_effect=make_create_task(mock_task),
        ):
            job = await manager.create_job(_make_request())

        # Simulate job entering running state, then callback fires
        job.status = "running"
        assert captured_callback is not None
        captured_callback(mock_task)

        assert job.status == "failed"

    async def test_on_done_with_exception_does_not_change_non_running_status(self):
        """If job.status is not 'running' when callback fires, status is unchanged."""
        manager = JobManager()
        captured_callback = None

        def fake_add_done_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_task = MagicMock()
        mock_task.add_done_callback = fake_add_done_callback
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = RuntimeError("oops")

        with patch(
            "src.jobs.manager.asyncio.create_task",
            side_effect=lambda coro: coro.close() or mock_task,
        ):
            job = await manager.create_job(_make_request())

        job.status = "completed"
        captured_callback(mock_task)

        # Status should remain 'completed', not overwritten
        assert job.status == "completed"

    async def test_on_done_cancelled_task_returns_early(self):
        """If task was cancelled, _on_done should return without changing status."""
        manager = JobManager()
        captured_callback = None

        def fake_add_done_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_task = MagicMock()
        mock_task.add_done_callback = fake_add_done_callback
        mock_task.cancelled.return_value = True

        with patch(
            "src.jobs.manager.asyncio.create_task",
            side_effect=lambda coro: coro.close() or mock_task,
        ):
            job = await manager.create_job(_make_request())

        job.status = "running"
        captured_callback(mock_task)

        # cancelled path just logs and returns; status unchanged by callback
        assert job.status == "running"

    async def test_on_done_no_exception_does_nothing(self):
        """If task succeeded (no exception, not cancelled), callback is a no-op."""
        manager = JobManager()
        captured_callback = None

        def fake_add_done_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_task = MagicMock()
        mock_task.add_done_callback = fake_add_done_callback
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = None

        with patch(
            "src.jobs.manager.asyncio.create_task",
            side_effect=lambda coro: coro.close() or mock_task,
        ):
            job = await manager.create_job(_make_request())

        job.status = "completed"
        captured_callback(mock_task)
        assert job.status == "completed"


# ---------------------------------------------------------------------------
# TestShutdown
# ---------------------------------------------------------------------------


class TestShutdown:
    """JobManager.shutdown() cancels running tasks."""

    async def test_shutdown_with_no_jobs_returns_early(self):
        """shutdown() with empty job dict should return without error."""
        manager = JobManager()
        # Should complete without raising
        await manager.shutdown()

    async def test_shutdown_with_all_done_tasks_returns_early(self):
        """shutdown() skips tasks that are already done."""
        manager = JobManager()

        # Use a real completed task to avoid AsyncMock coroutine warnings
        async def instant():
            pass

        real_task = asyncio.create_task(instant())
        await real_task  # let it complete so done() == True

        job = Job(id="j-done", request=_make_request())
        job._task = real_task
        manager._jobs["j-done"] = job

        # Since all tasks are done, shutdown returns early without cancelling
        await manager.shutdown()
        assert real_task.done() is True
        assert real_task.cancelled() is False

    async def test_shutdown_cancels_running_tasks(self):
        """shutdown() calls cancel() on tasks that are not done."""
        manager = JobManager()

        # Build a real asyncio.Task that we can control
        cancel_called = []

        async def long_running():
            try:
                await asyncio.sleep(9999)
            except asyncio.CancelledError:
                cancel_called.append(True)
                raise

        task = asyncio.create_task(long_running())
        # Give it a moment to start
        await asyncio.sleep(0)

        job = Job(id="j-running", request=_make_request())
        job._task = task
        manager._jobs["j-running"] = job

        await manager.shutdown()

        assert task.cancelled() or task.done()
        assert len(cancel_called) == 1

    async def test_shutdown_with_no_task_attribute(self):
        """shutdown() gracefully handles jobs where _task is None."""
        manager = JobManager()
        job = Job(id="j-none", request=_make_request())
        # _task defaults to None
        manager._jobs["j-none"] = job

        await manager.shutdown()  # should not raise


# ---------------------------------------------------------------------------
# TestCreateResumeJob
# ---------------------------------------------------------------------------


class TestCreateResumeJob:
    """JobManager.create_resume_job() stores job and wires _on_done callback."""

    async def test_create_resume_job_stores_job(self):
        """create_resume_job should store the job in _jobs under its ID."""
        manager = JobManager()
        pending_urls = ["https://example.com/page1", "https://example.com/page2"]

        with patch(
            "src.jobs.manager.asyncio.create_task",
            side_effect=lambda coro: coro.close() or MagicMock(),
        ):
            job = await manager.create_resume_job(_make_request(), pending_urls)

        assert job.id in manager._jobs
        assert manager._jobs[job.id] is job

    async def test_create_resume_job_returns_job_with_pending_status(self):
        """Resumed job starts in 'pending' status."""
        manager = JobManager()

        with patch(
            "src.jobs.manager.asyncio.create_task",
            side_effect=lambda coro: coro.close() or MagicMock(),
        ):
            job = await manager.create_resume_job(_make_request(), ["https://x.com/a"])

        assert job.status == "pending"

    async def test_create_resume_job_on_done_exception_sets_failed(self):
        """_on_done for resume job sets status to 'failed' on unhandled exception."""
        manager = JobManager()
        captured_callback = None

        def fake_add_done_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_task = MagicMock()
        mock_task.add_done_callback = fake_add_done_callback
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = RuntimeError("resume failed")

        with patch(
            "src.jobs.manager.asyncio.create_task",
            side_effect=lambda coro: coro.close() or mock_task,
        ):
            job = await manager.create_resume_job(
                _make_request(), ["https://example.com/p1"]
            )

        job.status = "running"
        assert captured_callback is not None
        captured_callback(mock_task)

        assert job.status == "failed"

    async def test_create_resume_job_on_done_cancelled_is_noop(self):
        """_on_done for resume job returns early when task was cancelled."""
        manager = JobManager()
        captured_callback = None

        def fake_add_done_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_task = MagicMock()
        mock_task.add_done_callback = fake_add_done_callback
        mock_task.cancelled.return_value = True

        with patch(
            "src.jobs.manager.asyncio.create_task",
            side_effect=lambda coro: coro.close() or mock_task,
        ):
            job = await manager.create_resume_job(
                _make_request(), ["https://example.com/p1"]
            )

        job.status = "running"
        captured_callback(mock_task)
        # Cancelled path is a no-op; status unchanged
        assert job.status == "running"

    async def test_create_resume_job_unique_id(self):
        """Each create_resume_job call produces a unique UUID job ID."""
        import uuid

        manager = JobManager()

        with patch(
            "src.jobs.manager.asyncio.create_task",
            side_effect=lambda coro: coro.close() or MagicMock(),
        ):
            job1 = await manager.create_resume_job(_make_request(), [])
            job2 = await manager.create_resume_job(_make_request(), [])

        assert job1.id != job2.id
        uuid.UUID(job1.id)  # validate format
        uuid.UUID(job2.id)


# ---------------------------------------------------------------------------
# TestStartCleanupLoop
# ---------------------------------------------------------------------------


class TestStartCleanupLoop:
    """start_cleanup_loop() runs cleanup on interval and handles CancelledError."""

    async def test_cleanup_loop_calls_cleanup_and_stops_on_cancelled(self):
        """start_cleanup_loop should call cleanup_old_jobs and exit on CancelledError."""
        manager = JobManager()
        cleanup_call_count = 0

        original_cleanup = manager.cleanup_old_jobs

        async def fake_cleanup():
            nonlocal cleanup_call_count
            cleanup_call_count += 1
            return 0

        manager.cleanup_old_jobs = fake_cleanup

        # Run the loop with a very short interval and cancel after first iteration
        async def run_and_cancel():
            task = asyncio.create_task(manager.start_cleanup_loop(interval=0))
            # Let one iteration run
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_and_cancel()
        # At least one cleanup should have been called
        assert cleanup_call_count >= 1

    async def test_cleanup_loop_cancelled_error_does_not_propagate(self):
        """CancelledError in the loop should be caught and not re-raised."""
        manager = JobManager()

        async def instant_sleep(secs):
            # Raise immediately to simulate cancellation during sleep
            raise asyncio.CancelledError()

        with patch("src.jobs.manager.asyncio.sleep", side_effect=instant_sleep):
            # Should not raise
            await manager.start_cleanup_loop(interval=300)


# ---------------------------------------------------------------------------
# TestPauseResumeJob
# ---------------------------------------------------------------------------


class TestPauseResumeJob:
    """JobManager.pause_job() and resume_job() delegate to Job methods."""

    def test_pause_job_returns_none_for_unknown_id(self):
        """pause_job returns None when job_id is not found."""
        manager = JobManager()
        result = manager.pause_job("nonexistent")
        assert result is None

    def test_pause_job_returns_job_and_pauses_it(self):
        """pause_job returns the job and sets its status to 'paused'."""
        manager = JobManager()
        job = Job(id="j-pause", request=_make_request(), status="running")
        manager._jobs["j-pause"] = job

        result = manager.pause_job("j-pause")
        assert result is job
        assert job.status == "paused"

    def test_resume_job_returns_none_for_unknown_id(self):
        """resume_job returns None when job_id is not found."""
        manager = JobManager()
        result = manager.resume_job("nonexistent")
        assert result is None

    def test_resume_job_returns_job_and_resumes_it(self):
        """resume_job returns the job and sets its status back to 'running'."""
        manager = JobManager()
        job = Job(id="j-resume", request=_make_request(), status="paused")
        job._paused = True
        job._pause_event.clear()
        manager._jobs["j-resume"] = job

        result = manager.resume_job("j-resume")
        assert result is job
        assert job.status == "running"


# ---------------------------------------------------------------------------
# TestCreateResumeJobNoExceptionBranch
# ---------------------------------------------------------------------------


class TestCreateResumeJobNoExceptionBranch:
    """Cover the no-exception branch in create_resume_job._on_done."""

    async def test_on_done_no_exception_is_noop_for_resume_job(self):
        """If resume job task completes with no exception, _on_done is silent."""
        manager = JobManager()
        captured_callback = None

        def fake_add_done_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_task = MagicMock()
        mock_task.add_done_callback = fake_add_done_callback
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = None  # success, no exception

        with patch(
            "src.jobs.manager.asyncio.create_task",
            side_effect=lambda coro: coro.close() or mock_task,
        ):
            job = await manager.create_resume_job(_make_request(), [])

        job.status = "completed"
        captured_callback(mock_task)
        # No-exception path does nothing
        assert job.status == "completed"

    async def test_on_done_exception_but_non_running_status_skips_failed(self):
        """_on_done with exception does not set 'failed' if job is not 'running'."""
        manager = JobManager()
        captured_callback = None

        def fake_add_done_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_task = MagicMock()
        mock_task.add_done_callback = fake_add_done_callback
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = RuntimeError("too late")

        with patch(
            "src.jobs.manager.asyncio.create_task",
            side_effect=lambda coro: coro.close() or mock_task,
        ):
            job = await manager.create_resume_job(_make_request(), [])

        # Job already completed before the exception surfaced
        job.status = "completed"
        captured_callback(mock_task)
        # Branch 247->exit: exc is truthy but status != "running", so no change
        assert job.status == "completed"
