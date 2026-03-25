"""API endpoints for crawl jobs.

🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from src.api.models import JobRequest, JobStatus, OllamaModel, ResumeFromStateRequest
from src.llm.client import (
    get_available_models,
    PROVIDERS,
    OLLAMA_URL,
    LMSTUDIO_URL,
    LMSTUDIO_API_KEY,
    LLAMACPP_URL,
    LLAMACPP_API_KEY,
)
from src.jobs.manager import JobManager

logger = logging.getLogger(__name__)
router = APIRouter()

job_manager = JobManager()

# Rate limiting — closes CONS-005 / issue #53
limiter = Limiter(key_func=get_remote_address)

MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "5"))


@router.get("/models")
async def list_models(
    provider: Optional[str] = Query(
        None, description="Provider: ollama, openrouter, or opencode"
    ),
) -> list[OllamaModel]:
    """List available models. If provider specified, returns models for that provider."""
    if provider:
        models = await get_available_models(provider)
    else:
        # Return all models from all providers
        all_models = []
        for p in PROVIDERS.keys():
            all_models.extend(await get_available_models(p))
        models = all_models
    return [
        OllamaModel(
            name=m["name"],
            size=m.get("size"),
            provider=m.get("provider", "ollama"),
            is_free=m.get("is_free", True),
        )
        for m in models
    ]


@router.get("/providers")
async def list_providers():
    """List available providers and their status."""
    return {
        "providers": [
            {
                "id": p_id,
                "name": p_id.capitalize(),
                "configured": (
                    p_id == "ollama"
                    or (
                        p_id == "openrouter"
                        and bool(os.environ.get("OPENROUTER_API_KEY"))
                    )
                    or (p_id == "opencode" and bool(os.environ.get("OPENCODE_API_KEY")))
                    or False
                ),
                "requires_api_key": config["requires_api_key"],
            }
            for p_id, config in PROVIDERS.items()
        ]
    }


@router.post("/jobs")
@limiter.limit("10/minute")
async def create_job(request: Request, job_request: JobRequest) -> JobStatus:
    """Create and start a new crawl job."""
    active_count = job_manager.active_job_count()
    if active_count >= MAX_CONCURRENT_JOBS:
        raise HTTPException(
            status_code=429,
            detail=f"Too many active jobs ({active_count}/{MAX_CONCURRENT_JOBS}). Try again later.",
        )
    job = await job_manager.create_job(job_request)
    return JobStatus(
        id=job.id,
        status=job.status,
        pages_total=0,
        pages_completed=0,
        converter=job_request.converter,
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
        converter=job.request.converter if job.request else None,
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
        converter=job.request.converter if job.request else None,
        pages_retried=job.pages_retried,
    )


@router.get("/health/ready")
async def health_ready() -> dict:
    """Check if the system is ready to accept jobs.

    Returns readiness status with detailed checks for:
    - Ollama connectivity
    - Disk space availability
    - Write permissions to /data

    🤖 Generated with AI assistance by DocCrawler 🕷️
    """
    import httpx

    issues = []
    checks = {}

    # Check Ollama connectivity
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                checks["ollama"] = {
                    "status": "ok",
                    "models_count": len(models),
                    "url": OLLAMA_URL,
                }
            else:
                checks["ollama"] = {"status": "error", "code": response.status_code}
                issues.append(f"Ollama returned status {response.status_code}")
    except httpx.ConnectError:
        checks["ollama"] = {"status": "unreachable", "url": OLLAMA_URL}
        issues.append(
            f"Cannot connect to Ollama at {OLLAMA_URL}. Is Ollama running? Try: ollama serve"
        )
    except httpx.TimeoutException:
        checks["ollama"] = {"status": "timeout", "url": OLLAMA_URL}
        issues.append(f"Ollama at {OLLAMA_URL} timed out after 5s")
    except Exception as e:
        checks["ollama"] = {"status": "error", "message": str(e)}
        issues.append(f"Ollama check failed: {e}")

    # Check LM Studio connectivity
    try:
        lms_headers = {}
        if LMSTUDIO_API_KEY:
            lms_headers["Authorization"] = f"Bearer {LMSTUDIO_API_KEY}"
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{LMSTUDIO_URL}/models", headers=lms_headers, timeout=5
            )
            if r.status_code == 200:
                data = r.json()
                checks["lmstudio"] = {
                    "status": "ok",
                    "models_count": len(data.get("data", [])),
                    "url": LMSTUDIO_URL,
                }
            else:
                checks["lmstudio"] = {"status": "error", "url": LMSTUDIO_URL}
    except httpx.ConnectError:
        checks["lmstudio"] = {"status": "unreachable", "url": LMSTUDIO_URL}
    except httpx.TimeoutException:
        checks["lmstudio"] = {"status": "timeout", "url": LMSTUDIO_URL}
    except Exception as e:
        checks["lmstudio"] = {"status": "error", "message": str(e)}

    # Check llama.cpp connectivity
    try:
        llama_headers = {}
        if LLAMACPP_API_KEY:
            llama_headers["Authorization"] = f"Bearer {LLAMACPP_API_KEY}"
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{LLAMACPP_URL}/models", headers=llama_headers, timeout=5
            )
            if r.status_code == 200:
                data = r.json()
                checks["llamacpp"] = {
                    "status": "ok",
                    "models_count": len(data.get("data", [])),
                    "url": LLAMACPP_URL,
                }
            else:
                checks["llamacpp"] = {"status": "error", "url": LLAMACPP_URL}
    except httpx.ConnectError:
        checks["llamacpp"] = {"status": "unreachable", "url": LLAMACPP_URL}
    except httpx.TimeoutException:
        checks["llamacpp"] = {"status": "timeout", "url": LLAMACPP_URL}
    except Exception as e:
        checks["llamacpp"] = {"status": "error", "message": str(e)}

    # Check disk space
    data_path = Path("/data")
    try:
        if data_path.exists():
            usage = shutil.disk_usage(data_path)
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            used_percent = (usage.used / usage.total) * 100

            checks["disk_space"] = {
                "status": "ok" if free_gb > 1 else "warning",
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "used_percent": round(used_percent, 1),
            }
            if free_gb < 1:
                issues.append(f"Low disk space: {free_gb:.1f}GB free")
            if free_gb < 0.1:
                checks["disk_space"]["status"] = "critical"
                issues.append(f"Critical disk space: {free_gb:.2f}GB free")
        else:
            checks["disk_space"] = {"status": "not_found", "path": str(data_path)}
            issues.append("/data directory does not exist")
    except Exception as e:
        checks["disk_space"] = {"status": "error", "message": str(e)}
        issues.append("Disk space check failed")  # avoid leaking exception details

    # Check write permissions
    try:
        test_file = data_path / ".write_test"
        if data_path.exists():
            test_file.write_text("test")
            test_file.unlink()
            checks["write_permissions"] = {"status": "ok", "path": str(data_path)}
        else:
            parent = data_path.parent
            if parent.exists() and parent.is_dir():
                checks["write_permissions"] = {
                    "status": "ok",
                    "note": "/data will be created on demand",
                }
            else:
                checks["write_permissions"] = {
                    "status": "error",
                    "message": "Parent directory not writable",
                }
                issues.append("Cannot create /data directory")
    except PermissionError:
        checks["write_permissions"] = {"status": "denied", "path": str(data_path)}
        issues.append(
            f"Permission denied writing to {data_path}. Try: sudo chown -R $USER:$USER ./data"
        )
    except Exception as e:
        checks["write_permissions"] = {"status": "error", "message": str(e)}
        issues.append(f"Write permission check failed: {e}")

    ready = len(issues) == 0 and checks.get("ollama", {}).get("status") == "ok"

    if not ready:
        raise HTTPException(
            status_code=503,
            detail={"ready": False, "issues": issues, "checks": checks},
        )

    return {"ready": True, "checks": checks}


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str) -> JobStatus:
    """Pause a running job after the current page finishes (PR 3.1).

    The job state is checkpointed to {output_path}/.job_state.json.
    Use POST /jobs/resume-from-state to restart from the checkpoint.
    """
    job = job_manager.pause_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("paused", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Job {job_id} cannot be paused (status: {job.status})",
        )
    return JobStatus(
        id=job.id,
        status=job.status,
        pages_completed=job.pages_completed,
        pages_total=job.pages_total,
    )


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str) -> JobStatus:
    """Resume a paused job (PR 3.1)."""
    job = job_manager.resume_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("paused", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Job {job_id} cannot be resumed (status: {job.status})",
        )
    return JobStatus(
        id=job.id,
        status=job.status,
        pages_completed=job.pages_completed,
        pages_total=job.pages_total,
    )


@router.post("/jobs/resume-from-state")
@limiter.limit("10/minute")
async def resume_from_state(
    request: Request, body: ResumeFromStateRequest
) -> JobStatus:
    """Create a new job resuming only the pending URLs from a saved state file (PR 3.1).

    Loads {state_file_path}, reconstructs the original JobRequest, and starts
    a new job processing only the URLs that were pending at the time of the checkpoint.
    Completed and failed URLs from the original run are skipped.
    """
    from src.jobs.state import load_job_state

    state_path = Path(body.state_file_path)
    if not state_path.exists():
        raise HTTPException(
            status_code=404, detail=f"State file not found: {state_path}"
        )

    try:
        state = load_job_state(state_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not state.pending_urls:
        raise HTTPException(
            status_code=409, detail="No pending URLs in state file — job was complete."
        )

    try:
        job_request = JobRequest.model_validate(state.request)
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"Invalid request in state file: {e}"
        )

    active_count = job_manager.active_job_count()
    if active_count >= MAX_CONCURRENT_JOBS:
        raise HTTPException(
            status_code=429,
            detail=f"Too many active jobs ({active_count}/{MAX_CONCURRENT_JOBS}). Try again later.",
        )

    job = await job_manager.create_resume_job(job_request, state.pending_urls)
    return JobStatus(
        id=job.id,
        status=job.status,
        pages_total=len(state.pending_urls),
        converter=job_request.converter,
    )


@router.get("/stats")
async def get_stats() -> dict:
    """In-memory job counters for operator observability."""
    jobs = list(job_manager._jobs.values())
    return {
        "total_jobs": len(jobs),
        "active_jobs": sum(1 for j in jobs if j.status in ("pending", "running")),
        "paused_jobs": sum(1 for j in jobs if j.status == "paused"),
        "completed_jobs": sum(1 for j in jobs if j.status == "completed"),
        "failed_jobs": sum(1 for j in jobs if j.status == "failed"),
        "cancelled_jobs": sum(1 for j in jobs if j.status == "cancelled"),
    }


@router.get("/converters")
@limiter.limit("60/minute")
async def list_converters(request: Request) -> dict:
    """List available HTML→Markdown converter plugins (PR 3.4)."""
    from src.scraper.converters import available_converters, get_converter

    converters = []
    for name in available_converters():
        c = get_converter(name)
        converters.append(
            {
                "name": name,
                "supports_tables": c.supports_tables(),
                "supports_code_blocks": c.supports_code_blocks(),
            }
        )
    return {"converters": converters, "default": "markdownify"}


@router.get("/info")
async def app_info() -> dict:
    """App identity metadata: version, repo, author, models used during development."""
    from src.main import API_VERSION

    return {
        "name": "Docrawl",
        "version": API_VERSION,
        "repo": "https://github.com/plater7/docrawl",
        "author": "plater7",
        "models_used": ["qwen3-coder:free", "glm-4.7-free", "claude-sonnet-4-6"],
    }
