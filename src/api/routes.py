"""API endpoints for crawl jobs."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from src.api.models import JobRequest, JobStatus, OllamaModel
from src.llm.client import get_available_models, PROVIDERS, PROVIDER_MODELS
from src.jobs.manager import JobManager

logger = logging.getLogger(__name__)
router = APIRouter()

job_manager = JobManager()


@router.get("/models")
async def list_models(provider: Optional[str] = Query(None, description="Provider: ollama, openrouter, or opencode")) -> list[OllamaModel]:
    """List available models. If provider specified, returns models for that provider."""
    if provider:
        models = await get_available_models(provider)
    else:
        # Return all models from all providers
        all_models = []
        for p in PROVIDERS.keys():
            all_models.extend(await get_available_models(p))
        models = all_models
    return [OllamaModel(name=m["name"], size=m.get("size"), provider=m.get("provider", "ollama")) for m in models]


@router.get("/providers")
async def list_providers():
    """List available providers and their status."""
    return {
        "providers": [
            {
                "id": p_id,
                "name": p_id.capitalize(),
                "configured": (
                    True if p_id == "ollama" 
                    else p_id == "openrouter" and bool(__import__('os').environ.get('OPENROUTER_API_KEY'))
                    else p_id == "opencode" and bool(__import__('os').environ.get('OPENCODE_API_KEY'))
                ),
                "requires_api_key": config["requires_api_key"],
            }
            for p_id, config in PROVIDERS.items()
        ]
    }


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
        ping=15,
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
