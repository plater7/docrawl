"""Job management."""

import uuid
import asyncio
import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator

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

    def cancel(self) -> None:
        """Mark job as cancelled."""
        self._cancelled = True
        self.status = "cancelled"

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    async def emit_event(self, event_type: str, data: dict) -> None:
        """Emit an SSE event."""
        await self._events.put({"event": event_type, "data": data})

    async def event_stream(self) -> AsyncGenerator[dict, None]:
        """Yield events as they occur."""
        while True:
            try:
                event = await asyncio.wait_for(self._events.get(), timeout=30)
                yield event
                if event["event"] in ("job_done", "job_cancelled"):
                    break
            except asyncio.TimeoutError:
                # Send keepalive
                yield {"event": "keepalive", "data": {}}


class JobManager:
    """Manages crawl jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    async def create_job(self, request: JobRequest) -> Job:
        """Create and start a new job."""
        job_id = str(uuid.uuid4())
        job = Job(id=job_id, request=request)
        self._jobs[job_id] = job

        # Start job in background
        from src.jobs.runner import run_job
        asyncio.create_task(run_job(job))

        logger.info(f"Created job {job_id} for {request.url}")
        return job

    def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    async def cancel_job(self, job_id: str) -> Job | None:
        """Cancel a running job."""
        job = self._jobs.get(job_id)
        if job:
            job.cancel()
            logger.info(f"Cancelled job {job_id}")
        return job
