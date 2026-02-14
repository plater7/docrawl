"""API endpoints for crawl jobs."""

import logging
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.api.models import JobRequest, JobStatus, OllamaModel
from src.llm.client import get_available_models
from src.jobs.manager import JobManager

logger = logging.getLogger(__name__)
router = APIRouter()

job_manager = JobManager()


@router.get("/models")
async def list_models() -> list[OllamaModel]:
    """List available Ollama models."""
    models = await get_available_models()
    return [OllamaModel(name=m["name"], size=m.get("size")) for m in models]


@router.post("/jobs")
async def create_job(request: JobRequest) -> JobStatus:
    """Create and start a new crawl job."""
    job = await job_manager.create_job(request)
    return JobStatus(
        id=job.id,
        status=job.status,
        pages_total=0,
        pages_completed=0,
    )


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str) -> EventSourceResponse:
    """SSE stream of job progress events."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return EventSourceResponse(
        job.event_stream(),
        ping=15,            # send SSE comment every 15s to keep connection alive
        ping_message_factory=lambda: "keepalive",
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> JobStatus:
    """Cancel a running job."""
    job = await job_manager.cancel_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(
        id=job.id,
        status=job.status,
        pages_completed=job.pages_completed,
        pages_total=job.pages_total,
    )


@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str) -> JobStatus:
    """Get current status of a job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(
        id=job.id,
        status=job.status,
        pages_completed=job.pages_completed,
        pages_total=job.pages_total,
        current_url=job.current_url,
    )
