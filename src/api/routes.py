"""API endpoints for crawl jobs.

🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.
"""

import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from src.api.models import JobRequest, JobStatus, OllamaModel
from src.llm.client import get_available_models, PROVIDERS, OLLAMA_URL
from src.jobs.manager import JobManager

logger = logging.getLogger(__name__)
router = APIRouter()

job_manager = JobManager()


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
                        and bool(__import__("os").environ.get("OPENROUTER_API_KEY"))
                    )
                    or (
                        p_id == "opencode"
                        and bool(__import__("os").environ.get("OPENCODE_API_KEY"))
                    )
                    or False
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
        issues.append(f"Disk space check failed: {e}")

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

    return {"ready": ready, "issues": issues, "checks": checks}
