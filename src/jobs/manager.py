"""Job management."""

import json
import os
import time
import uuid
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, TYPE_CHECKING

if TYPE_CHECKING:
    from src.scraper.page import PagePool

from src.api.models import JobRequest

logger = logging.getLogger(__name__)


def _make_running_event() -> asyncio.Event:
    """Return a pre-set asyncio.Event (set = running, clear = paused)."""
    e = asyncio.Event()
    e.set()
    return e


@dataclass
class Job:
    """Represents a crawl job."""

    id: str
    request: JobRequest
    status: str = "pending"
    pages_total: int = 0
    pages_completed: int = 0
    current_url: str | None = None
    completed_at: float | None = None  # PR 1.5: wall-clock time at completion
    pages_skipped: int = 0  # PR 2.3: dedup skips
    pages_blocked: int = 0  # PR 2.3: bot-check pages
    # PR 3.1: pause/resume via asyncio.Event (set=running, clear=paused)
    _paused: bool = False
    _pause_event: asyncio.Event = field(default_factory=lambda: _make_running_event())
    _cancelled: bool = False
    _events: asyncio.Queue = field(default_factory=asyncio.Queue)
    _task: Any = field(default=None, repr=False)  # asyncio.Task

    def cancel(self) -> None:
        """Mark job as cancelled."""
        self._cancelled = True
        self.status = "cancelled"
        # Unblock wait_if_paused so runner can observe is_cancelled
        self._pause_event.set()

    def pause(self) -> bool:
        """Signal the runner to pause after the current page (PR 3.1).

        Returns False if job is not in a pauseable state.
        """
        if self.status not in ("running", "pending"):
            return False
        self._paused = True
        self._pause_event.clear()  # clear = paused
        self.status = "paused"
        logger.info(f"Job {self.id}: paused")
        return True

    def resume(self) -> bool:
        """Resume a paused job (PR 3.1).

        Returns False if job is not paused.
        """
        if self.status != "paused":
            return False
        self._paused = False
        self._pause_event.set()  # set = running
        self.status = "running"
        logger.info(f"Job {self.id}: resumed")
        return True

    async def wait_if_paused(self) -> None:
        """Suspend the runner coroutine until the job is resumed (PR 3.1)."""
        await self._pause_event.wait()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    async def emit_event(self, event_type: str, data: dict) -> None:
        """Emit an SSE event."""
        await self._events.put({"event": event_type, "data": json.dumps(data)})

    async def event_stream(self) -> AsyncGenerator[dict, None]:
        """Yield events for SSE consumption. Handles client disconnect gracefully."""
        try:
            while True:
                try:
                    event = await asyncio.wait_for(self._events.get(), timeout=20)
                    yield event
                    if event["event"] in ("job_done", "job_cancelled", "job_error"):
                        break
                except asyncio.TimeoutError:
                    # Check if runner task died without terminal event
                    if self._task and self._task.done():
                        exc = (
                            self._task.exception()
                            if not self._task.cancelled()
                            else None
                        )
                        error_msg = (
                            str(exc) if exc else "Runner task ended unexpectedly"
                        )
                        logger.error(f"Job {self.id}: runner died: {error_msg}")
                        yield {
                            "event": "job_done",
                            "data": json.dumps(
                                {"status": "failed", "error": error_msg}
                            ),
                        }
                        break
                    # Send keepalive comment
                    yield {"event": "keepalive", "data": "{}"}
        except GeneratorExit:
            # Client disconnected — sse_starlette closed the generator
            logger.info(f"Job {self.id}: SSE client disconnected")
        except Exception as e:
            logger.error(f"Job {self.id}: event_stream error: {e}")


class JobManager:
    """Manages crawl jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._jobs_lock: asyncio.Lock = asyncio.Lock()  # PR 1.5: guards _jobs dict
        self.page_pool: "PagePool | None" = None  # PR 1.2: set in main.py lifespan

    async def create_job(self, request: JobRequest) -> Job:
        """Create and start a new job."""
        job_id = str(uuid.uuid4())
        job = Job(id=job_id, request=request)
        async with self._jobs_lock:
            self._jobs[job_id] = job

        from src.jobs.runner import run_job

        task = asyncio.create_task(run_job(job, page_pool=self.page_pool))
        job._task = task

        # done_callback logs unhandled exceptions and prevents silent failures
        # — closes CONS-014 / issue #60
        def _on_done(t: asyncio.Task) -> None:
            if t.cancelled():
                logger.info(f"Job {job_id}: task was cancelled")
                return
            exc = t.exception()
            if exc:
                logger.error(
                    f"Job {job_id}: unhandled exception in runner: {exc}", exc_info=exc
                )
                if job.status == "running":
                    job.status = "failed"

        task.add_done_callback(_on_done)

        logger.info(f"Created job {job_id} for {request.url}")
        return job

    def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def active_job_count(self) -> int:
        """Return the number of jobs currently running or pending."""
        return sum(
            1 for job in self._jobs.values() if job.status in ("pending", "running")
        )

    async def shutdown(self) -> None:
        """Cancel all running tasks on server shutdown — closes CONS-014 / issue #60."""
        running = [
            job for job in self._jobs.values() if job._task and not job._task.done()
        ]
        if not running:
            return
        logger.info(f"Shutdown: cancelling {len(running)} active job(s)")
        for job in running:
            job._task.cancel()
        await asyncio.gather(*[job._task for job in running], return_exceptions=True)
        logger.info("Shutdown: all job tasks cancelled")

    async def cancel_job(self, job_id: str) -> Job | None:
        """Cancel a running job."""
        job = self._jobs.get(job_id)
        if job:
            job.cancel()
            await job.emit_event(
                "job_cancelled",
                {
                    "pages_completed": job.pages_completed,
                    "pages_total": job.pages_total,
                    "output_path": str(job.request.output_path),
                },
            )
            logger.info(f"Cancelled job {job_id}")
        return job

    def pause_job(self, job_id: str) -> "Job | None":
        """Pause a running job (PR 3.1)."""
        job = self._jobs.get(job_id)
        if job:
            job.pause()
        return job

    def resume_job(self, job_id: str) -> "Job | None":
        """Resume a paused job (PR 3.1)."""
        job = self._jobs.get(job_id)
        if job:
            job.resume()
        return job

    async def create_resume_job(
        self, request: JobRequest, pending_urls: list[str]
    ) -> "Job":
        """Create a new job that resumes from a saved state (PR 3.1).

        Skips discovery/filtering and processes only the given pending_urls.
        """
        job_id = str(uuid.uuid4())
        job = Job(id=job_id, request=request)
        async with self._jobs_lock:
            self._jobs[job_id] = job

        from src.jobs.runner import run_job

        task = asyncio.create_task(
            run_job(job, page_pool=self.page_pool, resume_urls=pending_urls)
        )
        job._task = task

        def _on_done(t: asyncio.Task) -> None:
            if t.cancelled():
                return
            exc = t.exception()
            if exc:
                logger.error(f"Job {job_id}: resume job failed: {exc}", exc_info=exc)
                if job.status == "running":
                    job.status = "failed"

        task.add_done_callback(_on_done)
        logger.info(f"Created resume job {job_id} with {len(pending_urls)} pending URLs")
        return job

    async def cleanup_old_jobs(self) -> int:
        """Remove completed/failed jobs older than JOB_TTL_SECONDS (PR 1.5).

        Returns number of jobs removed.
        """
        ttl = int(os.environ.get("JOB_TTL_SECONDS", "3600"))
        if ttl <= 0:
            return 0
        now = time.time()
        to_remove = []
        async with self._jobs_lock:
            for job_id, job in self._jobs.items():
                if job.completed_at is not None and (now - job.completed_at) > ttl:
                    to_remove.append(job_id)
            for job_id in to_remove:
                del self._jobs[job_id]
        if to_remove:
            logger.info(f"TTL cleanup: removed {len(to_remove)} expired job(s)")
        return len(to_remove)

    async def start_cleanup_loop(self, interval: int = 300) -> None:
        """Background task: periodically clean up expired jobs (PR 1.5).

        JOB_TTL_SECONDS=0 disables cleanup.
        """
        logger.info(f"Job cleanup loop started (interval={interval}s)")
        try:
            while True:
                await asyncio.sleep(interval)
                await self.cleanup_old_jobs()
        except asyncio.CancelledError:
            logger.info("Job cleanup loop stopped")
