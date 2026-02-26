"""Job management."""

import json
import uuid
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from src.api.models import JobRequest

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """Represents a crawl job."""

    id: str
    request: JobRequest
    status: str = "pending"
    pages_total: int = 0
    pages_completed: int = 0
    current_url: str | None = None
    _cancelled: bool = False
    _events: asyncio.Queue = field(default_factory=asyncio.Queue)
    _task: Any = field(default=None, repr=False)  # asyncio.Task

    def cancel(self) -> None:
        """Mark job as cancelled."""
        self._cancelled = True
        self.status = "cancelled"

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

    async def create_job(self, request: JobRequest) -> Job:
        """Create and start a new job."""
        job_id = str(uuid.uuid4())
        job = Job(id=job_id, request=request)
        self._jobs[job_id] = job

        # Start job in background, keep task reference
        from src.jobs.runner import run_job

        job._task = asyncio.create_task(run_job(job))

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
