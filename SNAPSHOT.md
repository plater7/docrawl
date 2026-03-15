# DocRawl Code Snapshot — v0.9.10

> Auto-generated on 2026-03-15 02:41 UTC by `scripts/generate_snapshot.py`.
> Use as reference for AI-assisted development sessions.

## Project Structure

```
src/
├── api
│   ├── __init__.py
│   ├── models.py
│   └── routes.py
├── crawler
│   ├── __init__.py
│   ├── discovery.py
│   ├── filter.py
│   └── robots.py
├── jobs
│   ├── __init__.py
│   ├── manager.py
│   ├── runner.py
│   └── state.py
├── llm
│   ├── __init__.py
│   ├── cleanup.py
│   ├── client.py
│   └── filter.py
├── scraper
│   ├── converters/
│   ├── __init__.py
│   ├── cache.py
│   ├── detection.py
│   ├── markdown.py
│   ├── page.py
│   └── structured.py
├── ui
│   ├── __init__.py
│   └── index.html
├── utils
│   ├── __init__.py
│   └── security.py
├── __init__.py
├── exceptions.py
└── main.py
```

---

## `src/__init__.py`

```python

```

---

## `src/api/__init__.py`

```python

```

---

## `src/api/models.py`

```python
"""Pydantic models for API request/response."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, HttpUrl, Field, field_validator, model_validator

from src.utils.security import validate_url_not_ssrf


class JobRequest(BaseModel):
    """Request to create a new crawl job."""

    url: HttpUrl
    crawl_model: str | None = Field(default=None, pattern=r"^[\w./:@-]{1,100}$")
    pipeline_model: str | None = Field(default=None, pattern=r"^[\w./:@-]{1,100}$")
    reasoning_model: str | None = Field(default=None, pattern=r"^[\w./:@-]{1,100}$")
    output_path: str = Field(default="/data/output")
    delay_ms: int = Field(default=500, ge=100, le=60000)
    max_concurrent: int = Field(default=3, ge=1, le=10)
    max_depth: int = Field(default=5, ge=1, le=20)
    respect_robots_txt: bool = True
    use_native_markdown: bool = True
    use_markdown_proxy: bool = False
    markdown_proxy_url: str | None = Field(default=None)
    use_http_fast_path: bool = Field(
        default=True,
        description=(
            "Enable HTTP fast-path before Playwright. "
            "Fallback chain: native_markdown → http_fast → playwright."
        ),
    )
    use_cache: bool = False  # PR 2.4: opt-in disk cache (24h TTL)
    output_format: Literal["markdown", "json"] = (
        "markdown"  # PR 3.2: structured JSON output opt-in
    )
    use_pipeline_mode: bool = False  # PR 3.3: opt-in producer/consumer pipeline
    converter: str | None = Field(
        default=None, pattern=r"^[\w-]{1,50}$"
    )  # PR 3.4: converter plugin name (None = default)
    skip_llm_cleanup: bool = Field(
        default=False,
        description=(
            "Skip the LLM cleanup step after HTML->Markdown conversion. "
            "Set to True when using a converter that already produces clean "
            "Markdown (e.g. converter='readerlm'). Has no effect when "
            "converter is markdownify and content has no noise."
        ),
    )
    language: str = Field(default="en", max_length=10)
    filter_sitemap_by_path: bool = True
    content_selectors: list[str] | None = Field(
        default=None,
        description=(
            "CSS selectors to try for main content extraction (prepended before DocRawl defaults). "
            "Each selector max 200 chars, list max 20 items."
        ),
    )
    noise_selectors: list[str] | None = Field(
        default=None,
        description=(
            "CSS selectors for noise elements to remove before extraction (prepended before DocRawl defaults). "
            "Each selector max 200 chars, list max 20 items."
        ),
    )

    @field_validator("content_selectors", "noise_selectors")
    @classmethod
    def validate_selectors(cls, v: list[str] | None) -> list[str] | None:
        """Validate per-job CSS selector lists."""
        if v is None:
            return v
        if len(v) > 20:
            raise ValueError("Selector list max 20 items")
        for sel in v:
            if len(sel) > 200:
                raise ValueError(f"Selector too long (max 200 chars): {sel[:50]}...")
        return v

    @field_validator("output_path")
    @classmethod
    def validate_output_path(cls, v: str) -> str:
        """Prevent path traversal — closes CONS-001 / issue #47."""
        resolved = Path("/data").joinpath(v.lstrip("/")).resolve()
        if not str(resolved).startswith("/data"):
            raise ValueError("output_path must be under /data")
        return str(resolved)

    @field_validator("markdown_proxy_url", mode="before")
    @classmethod
    def validate_proxy_url(cls, v: object) -> object:
        """Prevent SSRF via markdown proxy URL — closes CONS-019 / issue #65."""
        if v is None or v == "":
            return None
        parsed = urlparse(str(v))
        if parsed.scheme != "https":
            raise ValueError("markdown_proxy_url must use HTTPS")
        validate_url_not_ssrf(str(v))
        return v

    @model_validator(mode="after")
    def validate_converter(self) -> "JobRequest":
        """Validate converter name exists in registry (PR 3.4 fix)."""
        if self.converter is None:
            return self
        from src.scraper.converters import available_converters

        available = available_converters()
        if self.converter not in available:
            raise ValueError(
                f"Converter '{self.converter}' not found. Available: {available}"
            )
        return self

    @model_validator(mode="after")
    def validate_models_required(self) -> "JobRequest":
        """Require LLM model fields only when they will actually be used.

        When skip_llm_cleanup=True or a ReaderLM converter is selected, the
        pipeline_model is not needed.  crawl_model is only needed for LLM URL
        filtering; if absent, the runner skips that step.
        """
        _READERLM_CONVERTERS = {"readerlm", "readerlm-v1"}
        llm_cleanup_needed = not self.skip_llm_cleanup and (
            self.converter not in _READERLM_CONVERTERS
        )
        if llm_cleanup_needed and self.pipeline_model is None:
            raise ValueError(
                "pipeline_model is required unless skip_llm_cleanup=True or "
                "a ReaderLM converter is used (converter='readerlm' / 'readerlm-v1')."
            )
        return self


class ResumeFromStateRequest(BaseModel):
    """Request to resume a job from a saved .job_state.json file (PR 3.1)."""

    state_file_path: str = Field(
        description="Absolute path to the .job_state.json file produced by a paused/completed job."
    )

    @field_validator("state_file_path")
    @classmethod
    def validate_state_path(cls, v: str) -> str:
        """Prevent path traversal on state file path."""
        resolved = Path("/data").joinpath(v.lstrip("/")).resolve()
        if not str(resolved).startswith("/data"):
            raise ValueError("state_file_path must be under /data")
        return str(resolved)


class JobStatus(BaseModel):
    """Current status of a job."""

    id: str
    status: str
    pages_completed: int = 0
    pages_total: int = 0
    current_url: str | None = None
    converter: str | None = None  # PR 3.5: show converter in job status
    pages_retried: int = 0  # PR 4: scrape-level retry count


class OllamaModel(BaseModel):
    """LLM model info."""

    name: str
    size: int | None = None
    provider: str = "ollama"
    is_free: bool = True
```

---

## `src/api/routes.py`

```python
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
```

---

## `src/crawler/__init__.py`

```python

```

---

## `src/crawler/discovery.py`

*File truncated: showing first 500 of 617 lines.*

```python
"""URL discovery: sitemap, nav parsing, recursive crawl."""

import asyncio
import gzip
import logging
import os
import random
import defusedxml.ElementTree as ET  # XXE-safe replacement — closes CONS-010 / issue #64
from xml.etree.ElementTree import ParseError as XMLParseError
from typing import TYPE_CHECKING, cast
from urllib.parse import urljoin, urlparse, urlunparse

if TYPE_CHECKING:
    from src.scraper.cache import PageCache

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from src.utils.security import validate_url_not_ssrf

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalize URL for deduplication with safety checks.

    Normalization rules:
    - Remove fragment (#section)
    - Remove trailing slash (except for root path)
    - Lowercase scheme and domain
    - Preserve query params
    - Handle unicode and special characters
    - Enforce max URL length (2000 chars)

    Examples:
        https://example.com/path/ -> https://example.com/path
        https://example.com/path#section -> https://example.com/path
        https://EXAMPLE.com/Path -> https://example.com/Path (domain lowercase, path preserved)

    Raises:
        ValueError: If URL is invalid or exceeds max length
    """
    MAX_URL_LENGTH = 2000  # Reasonable limit to prevent DoS

    # Safety check: URL length
    if len(url) > MAX_URL_LENGTH:
        logger.warning(f"URL exceeds max length ({MAX_URL_LENGTH}): {url[:100]}...")
        url = url[:MAX_URL_LENGTH]

    try:
        parsed = urlparse(url)

        # Validate scheme
        if parsed.scheme not in ["http", "https", ""]:
            logger.debug(f"Skipping non-HTTP URL: {url}")
            return url  # Return as-is for caller to filter

        # Normalize path: remove trailing slash except for root
        path = parsed.path.rstrip("/") if parsed.path != "/" else "/"

        # Lowercase scheme and domain, preserve path case
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                path,
                parsed.params,
                parsed.query,
                "",  # Remove fragment
            )
        )
    except Exception as e:
        logger.warning(f"Failed to normalize URL: {url} - {e}")
        return url  # Return as-is, let caller handle


async def _extract_links(
    url: str,
    base_domain: str,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    jitter: bool = True,
) -> list[str]:
    """Fetch a URL and return same-domain links found in it.

    Used by parallel recursive_crawl per-depth-level gather.
    Jitter 0.1–0.3s between requests mitigates rate limiting.
    """
    async with sem:
        if jitter:
            await asyncio.sleep(random.uniform(0.1, 0.3))
        try:
            response = await client.get(url)
            if response.status_code == 404:
                logger.debug(f"Skipping 404: {url}")
                return []
            if response.status_code != 200:
                logger.debug(f"Non-200 {response.status_code} for {url}")
                return []
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            links: list[str] = []
            for link in soup.find_all("a", href=True):
                href = cast(str, link["href"])
                if any(
                    skip in href.lower()
                    for skip in ["#", "javascript:", "mailto:", "tel:"]
                ):
                    continue
                absolute_url = urljoin(url, href)
                parsed = urlparse(absolute_url)
                if parsed.netloc == base_domain and parsed.scheme in ["http", "https"]:
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if parsed.query:
                        clean_url += f"?{parsed.query}"
                    links.append(clean_url)
            return links
        except httpx.TimeoutException:
            logger.debug(f"Timeout crawling {url}")
            return []
        except Exception as e:
            logger.debug(f"Failed to crawl {url}: {e}")
            return []


async def recursive_crawl(
    base_url: str, max_depth: int, concurrency: int | None = None
) -> list[str]:
    """
    Recursively crawl internal links up to max_depth using parallel BFS per depth level.

    Args:
        base_url: Starting URL
        max_depth: Maximum depth to crawl (1 = only direct links from base_url)
        concurrency: Max concurrent requests per level. Defaults to DISCOVERY_CONCURRENCY env var (10).
                     Set to 1 for sequential behaviour identical to the previous implementation.

    Returns:
        List of discovered URLs (deduplicated, normalized)

    Edge cases handled:
    - Deduplication via normalized URLs
    - Same-domain filtering
    - Fragment removal
    - Trailing slash normalization
    - Jitter 0.1–0.3s between requests (rate limiting mitigation)
    - Total URL cap (1000 URLs max to prevent explosion)
    - Timeout handling (10s per request)
    - Heartbeat logging every 10 URLs
    - Per-URL error handling (failures don't stop crawl)
    """
    if concurrency is None:
        concurrency = int(os.environ.get("DISCOVERY_CONCURRENCY", "10"))

    if max_depth < 1:
        return [base_url]

    visited: set[str] = set()
    discovered_urls: list[str] = []
    base_domain = urlparse(base_url).netloc

    MAX_URLS = 1000  # Safety cap
    HEARTBEAT_INTERVAL = 10  # Log every N URLs

    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "DocRawl/1.0 (Documentation Crawler)"},
    ) as client:
        # BFS level by level
        current_level: list[str] = [base_url]

        for depth in range(max_depth + 1):
            if not current_level or len(discovered_urls) >= MAX_URLS:
                break

            # Deduplicate and cap at current level
            to_fetch: list[str] = []
            for url in current_level:
                normalized = normalize_url(url)
                if normalized not in visited and len(discovered_urls) < MAX_URLS:
                    visited.add(normalized)
                    discovered_urls.append(normalized)
                    to_fetch.append(url)

                    if len(discovered_urls) % HEARTBEAT_INTERVAL == 0:
                        logger.info(
                            f"Crawl progress: {len(discovered_urls)} URLs discovered"
                        )

            if depth >= max_depth:
                break

            logger.debug(
                f"Crawling depth {depth}/{max_depth}: {len(to_fetch)} URLs in parallel"
            )

            # Gather links from all URLs at this depth in parallel
            results = await asyncio.gather(
                *[
                    _extract_links(
                        url, base_domain, client, sem, jitter=(concurrency > 1)
                    )
                    for url in to_fetch
                ],
                return_exceptions=False,
            )

            # Flatten and deduplicate next level
            next_level_set: set[str] = set()
            for link_list in results:
                for link in link_list:
                    norm = normalize_url(link)
                    if norm not in visited and norm not in next_level_set:
                        next_level_set.add(norm)

            current_level = list(next_level_set)

    if len(discovered_urls) >= MAX_URLS:
        logger.warning(f"Hit URL cap ({MAX_URLS}). Crawl may be incomplete.")

    logger.info(f"Recursive crawl complete: {len(discovered_urls)} URLs found")
    return discovered_urls


async def try_nav_parse(base_url: str) -> list[str]:
    """
    Parse navigation/sidebar links from the page using Playwright.

    Useful for JS-rendered navigation that httpx can't see.

    Args:
        base_url: URL to parse navigation from

    Returns:
        List of URLs found in navigation elements

    Edge cases handled:
    - Multiple nav selectors (nav, aside, sidebar, etc.)
    - External link filtering
    - Deduplication
    - Timeout (10s page load, reduced from 15s)
    - Max 100 URLs cap
    """
    discovered_urls: set[str] = set()
    base_domain = urlparse(base_url).netloc
    MAX_NAV_URLS = 100

    # Common navigation selectors
    NAV_SELECTORS = [
        "nav a",
        "aside a",
        ".sidebar a",
        ".navigation a",
        '[role="navigation"] a',
        ".toc a",  # Table of contents
        ".menu a",
    ]

    msg = f"Trying nav parsing on {base_url}"
    logger.info(msg)

    try:
        validate_url_not_ssrf(base_url)  # SSRF check — closes CONS-002 / issue #51
    except ValueError as e:
        logger.warning(f"Nav parsing blocked: {e}")
        return []

    try:
        async with async_playwright() as p:
            async with await p.chromium.launch(headless=True) as browser:
                async with await browser.new_page() as page:
                    logger.debug("Loading page for nav parsing...")
                    await page.goto(
                        base_url, wait_until="domcontentloaded", timeout=10000
                    )

                    # Try each selector with limit
                    for selector in NAV_SELECTORS:
                        if len(discovered_urls) >= MAX_NAV_URLS:
                            logger.info(f"Hit nav URL cap ({MAX_NAV_URLS}), stopping")
                            break

                        try:
                            links = await page.query_selector_all(selector)
                            logger.debug(
                                f"Selector '{selector}' found {len(links)} links"
                            )

                            for link in links:
                                if len(discovered_urls) >= MAX_NAV_URLS:
                                    break

                                href = await link.get_attribute("href")
                                if not href:
                                    continue

                                # Skip anchors and non-http links
                                if href.startswith("#") or href.startswith(
                                    "javascript:"
                                ):
                                    continue

                                absolute_url = urljoin(base_url, href)
                                parsed = urlparse(absolute_url)

                                # Same domain only
                                if parsed.netloc == base_domain and parsed.scheme in [
                                    "http",
                                    "https",
                                ]:
                                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                                    if parsed.query:
                                        clean_url += f"?{parsed.query}"
                                    discovered_urls.add(normalize_url(clean_url))

                        except Exception as e:
                            logger.debug(f"Selector '{selector}' failed: {e}")
                            continue

    except PlaywrightTimeout:
        msg = f"Nav parsing timeout after 10s on {base_url}"
        logger.warning(msg)
        return []
    except Exception as e:
        msg = f"Nav parsing failed for {base_url}: {e}"
        logger.error(msg)
        return []

    result = list(discovered_urls)[:MAX_NAV_URLS]
    msg = f"Nav parsing found {len(result)} URLs"
    logger.info(msg)
    return result


async def try_sitemap(
    base_url: str,
    filter_by_path: bool = True,
    sitemap_cache: "PageCache | None" = None,
) -> list[str]:
    """
    Try to parse sitemap.xml and robots.txt.

    Discovery order:
    1. /sitemap.xml
    2. /sitemap_index.xml
    3. Parse robots.txt for Sitemap: directive

    Args:
        base_url: Base URL of the site
        filter_by_path: If True, filter URLs to only include those under the base URL's path
        sitemap_cache: Optional PageCache for sitemap HTTP responses. When provided,
                       sitemap XML is cached on first fetch and reused on repeat crawls,
                       avoiding redundant HTTP requests. Gzipped sitemaps (.gz) are not cached.

    Returns:
        List of URLs found in sitemaps

    Edge cases handled:
    - Gzipped sitemaps (.xml.gz)
    - Sitemap index files (nested sitemaps)
    - Multiple sitemaps in robots.txt
    - Invalid XML handling
    - 404s and network errors
    """
    discovered_urls = set()
    base_domain = urlparse(base_url).netloc
    base_path = urlparse(base_url).path.rstrip("/") if urlparse(base_url).path else ""
    if base_path == "":
        base_path = "/"

    msg = f"Trying sitemap on {base_url}"
    logger.info(msg)

    async def parse_sitemap_xml(url: str, client: httpx.AsyncClient) -> set[str]:
        """Parse a sitemap XML file with robust error handling."""
        urls: set[str] = set()
        is_gz = url.endswith(".gz")

        try:
            content: bytes | None = None

            # Check cache first (non-gzipped only — binary .gz can't round-trip through str)
            if sitemap_cache and not is_gz:
                cached = sitemap_cache.get(url)
                if cached is not None:
                    logger.debug(f"Sitemap cache HIT: {url}")
                    content = cached.encode("utf-8")

            if content is None:
                response = await client.get(url, timeout=10.0)

                # Skip 404s gracefully
                if response.status_code == 404:
                    logger.debug(f"Sitemap not found (404): {url}")
                    return urls
                elif response.status_code != 200:
                    logger.debug(
                        f"Non-200 status {response.status_code} for sitemap: {url}"
                    )
                    return urls

                content = response.content

                # Cache successful non-gzipped responses
                if sitemap_cache and not is_gz:
                    logger.debug(f"Sitemap cache MISS, storing: {url}")
                    sitemap_cache.put(url, response.text)

            # Handle gzipped sitemaps
            if url.endswith(".gz"):
                try:
                    content = gzip.decompress(content)
                except Exception as e:
                    logger.warning(
                        f"✗ Failed to decompress gzipped sitemap: {url} - {e}"
                    )
                    return urls

            # Parse XML with defensive error handling
            try:
                root = ET.fromstring(content)
            except XMLParseError as e:
                logger.warning(f"✗ Invalid XML in sitemap: {url} - {e}")
                return urls

            # Handle sitemap index (nested sitemaps)
            namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            # Check if this is a sitemap index
            for sitemap_elem in root.findall(".//ns:sitemap/ns:loc", namespace):
                nested_url = sitemap_elem.text
                if nested_url:
                    # Recursively parse nested sitemaps (failures don't stop entire discovery)
                    try:
                        nested_urls = await parse_sitemap_xml(nested_url, client)
                        urls.update(nested_urls)
                    except Exception as e:
                        logger.debug(
                            f"Failed to parse nested sitemap {nested_url}: {e}"
                        )
                        continue

            # Extract URLs from regular sitemap
            for url_elem in root.findall(".//ns:url/ns:loc", namespace):
                url_text = url_elem.text
                if url_text:
                    parsed = urlparse(url_text)
                    # Filter same domain
                    if parsed.netloc == base_domain:
                        # Filter by base path if enabled
                        url_path = parsed.path.rstrip("/") if parsed.path else "/"
                        if filter_by_path and base_path != "/":
                            if not url_path.startswith(base_path):
                                logger.debug(
                                    f"Skipping URL not under base path {base_path}: {url_text}"
                                )
                                continue
                        urls.add(normalize_url(url_text))

        except httpx.TimeoutException:
            logger.debug(f"Timeout fetching sitemap: {url}")
        except Exception as e:
            logger.warning(f"✗ Failed to parse sitemap {url}: {e}")

        return urls

    async with httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "DocRawl/1.0 (Documentation Crawler)"},
    ) as client:
        # Try standard sitemap locations
        sitemap_urls = [
            urljoin(base_url, "/sitemap.xml"),
            urljoin(base_url, "/sitemap_index.xml"),
        ]

        # Try to get sitemap URLs from robots.txt
        try:
            robots_url = urljoin(base_url, "/robots.txt")
            response = await client.get(robots_url, timeout=5.0)
            if response.status_code == 200:
                for line in response.text.split("\n"):
                    if line.lower().startswith("sitemap:"):
                        sitemap_url = line.split(":", 1)[1].strip()
                        sitemap_urls.append(sitemap_url)
        except Exception:
            pass  # robots.txt is optional

        # Parse all discovered sitemaps
        for sitemap_url in sitemap_urls:
            logger.debug(f"Parsing sitemap: {sitemap_url}")
# ... truncated ...
```

---

## `src/crawler/filter.py`

```python
"""Deterministic URL filtering."""

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

EXCLUDED_EXTENSIONS = {
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".mp4",
    ".mp3",
    ".wav",
    ".avi",
    ".mov",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".exe",
    ".dmg",
    ".deb",
    ".rpm",
}

EXCLUDED_PATTERNS = {
    "/blog/",
    "/changelog/",
    "/api-reference/",
    "/releases/",
    "/download/",
    "/assets/",
}

LANGUAGE_PATTERNS = {
    "en": ["/en/", "/en-us/", "/en-gb/", "/en-au/", "/en-ca/", "/en-in/", "/english/"],
    "es": ["/es/", "/es-es/", "/es-mx/", "/es-ar/", "/es-cl/", "/es-co/", "/spanish/"],
    "fr": ["/fr/", "/fr-fr/", "/fr-ca/", "/french/"],
    "de": ["/de/", "/de-de/", "/de-at/", "/de-ch/", "/german/"],
    "ja": ["/ja/", "/jp/", "/japanese/"],
    "zh": ["/zh/", "/zh-cn/", "/zh-tw/", "/zh-hk/", "/chinese/"],
    "pt": ["/pt/", "/pt-br/", "/pt-pt/", "/portuguese/"],
    "ru": ["/ru/", "/russian/"],
    "ko": ["/ko/", "/kr/", "/korean/"],
}


def filter_urls(urls: list[str], base_url: str, language: str = "en") -> list[str]:
    """
    Apply deterministic filtering to URL list.

    - Only same domain/subpath
    - Exclude non-doc extensions
    - Exclude common non-doc patterns
    - Filter by language (default: English only)
    - Deduplicate
    """
    base_parsed = urlparse(base_url)
    base_domain = base_parsed.netloc
    base_path = base_parsed.path.rstrip("/")

    filtered: set[str] = set()

    for url in urls:
        parsed = urlparse(url)

        if parsed.netloc != base_domain:
            continue

        path = parsed.path.rstrip("/")
        if not path.startswith(base_path):
            continue

        if any(path.lower().endswith(ext) for ext in EXCLUDED_EXTENSIONS):
            continue

        if any(pattern in path.lower() for pattern in EXCLUDED_PATTERNS):
            continue

        if not _matches_language(path, language, base_url):
            continue

        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        filtered.add(normalized)

    logger.info(
        f"Filtered {len(urls)} URLs down to {len(filtered)} (language: {language})"
    )
    return sorted(filtered)


def _matches_language(path: str, language: str, base_url: str = "") -> bool:
    """
    Check if URL path matches the target language.

    Strategy:
    1. If path contains target language → include
    2. If path contains OTHER language → exclude
    3. If path has NO language prefix → use base_url to determine fallback
    """
    if language == "all":
        return True

    path_lower = path.lower()

    # Check for target language
    lang_patterns = LANGUAGE_PATTERNS.get(language, [f"/{language}/"])
    for pattern in lang_patterns:
        if pattern in path_lower:
            return True

    # Check for other languages
    other_langs = set(LANGUAGE_PATTERNS.keys()) - {language}
    for other_lang in other_langs:
        for pattern in LANGUAGE_PATTERNS[other_lang]:
            if pattern in path_lower:
                return False

    # No language pattern found in URL
    # If base_url has a language, assume URLs without prefix are same as base → include
    # If base_url has no language and URL has no language → include (be permissive)
    # If base_url has language but this URL doesn't → exclude (different language)
    if base_url:
        base_parsed = urlparse(base_url)
        base_path = base_parsed.path.lower()

        base_has_language = any(
            pattern in base_path
            for patterns in LANGUAGE_PATTERNS.values()
            for pattern in patterns
        )

        # If base has language but this URL doesn't → exclude
        if base_has_language:
            return False

    return True
```

---

## `src/crawler/robots.py`

```python
"""robots.txt parser."""

import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class RobotsParser:
    """Simple robots.txt parser supporting Disallow and Allow directives."""

    def __init__(self) -> None:
        self.disallowed: list[str] = []
        self.allowed: list[str] = []
        self.crawl_delay: float | None = None

    async def load(self, base_url: str) -> bool:
        """Load and parse robots.txt from base URL."""
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(robots_url, timeout=10)
                if response.status_code != 200:
                    return False

                self._parse(response.text)
                return True
        except Exception as e:
            logger.warning(f"Failed to load robots.txt: {e}")
            return False

    def _parse(self, content: str) -> None:
        """Parse robots.txt content."""
        in_user_agent_all = False

        for line in content.splitlines():
            line = line.strip().lower()

            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                in_user_agent_all = agent == "*"
            elif in_user_agent_all:
                if line.startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        self.disallowed.append(path)
                elif line.startswith("allow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        self.allowed.append(path)
                elif line.startswith("crawl-delay:"):
                    try:
                        self.crawl_delay = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass

    def is_allowed(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt.

        Uses specificity-based precedence: the longest matching rule wins.
        If Allow and Disallow tie on length, Allow wins (RFC 9309 §2.2.2).
        """
        parsed = urlparse(url)
        path = parsed.path

        best_disallow_len: int | None = None
        for rule in self.disallowed:
            if path.startswith(rule):
                if best_disallow_len is None or len(rule) > best_disallow_len:
                    best_disallow_len = len(rule)

        best_allow_len: int | None = None
        for rule in self.allowed:
            if path.startswith(rule):
                if best_allow_len is None or len(rule) > best_allow_len:
                    best_allow_len = len(rule)

        # No rule matched at all -> allowed
        if best_disallow_len is None and best_allow_len is None:
            return True

        # Only allow matched -> allowed
        if best_disallow_len is None:
            return True

        # Only disallow matched -> blocked
        if best_allow_len is None:
            return False

        # Both matched: Allow wins on tie or when more specific
        return best_allow_len >= best_disallow_len
```

---

## `src/exceptions.py`

```python
"""Custom exceptions for Docrawl with user-friendly messages.

🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.
"""


class DocrawlError(Exception):
    """Base exception for Docrawl errors."""

    def __init__(self, message: str, user_hint: str | None = None):
        self.message = message
        self.user_hint = user_hint
        super().__init__(message)

    def __str__(self) -> str:
        if self.user_hint:
            return f"{self.message}\n  Hint: {self.user_hint}"
        return self.message


class OllamaNotRunningError(DocrawlError):
    """Ollama service is not reachable."""

    def __init__(self, url: str = "http://localhost:11434"):
        super().__init__(
            message=f"Cannot connect to Ollama at {url}",
            user_hint="Start Ollama with: ollama serve",
        )


class ModelNotFoundError(DocrawlError):
    """Requested model is not available."""

    def __init__(self, model: str, provider: str = "ollama"):
        hint = f"Pull the model with: ollama pull {model}"
        if provider != "ollama":
            hint = f"Check that your API key is configured for {provider}"
        super().__init__(
            message=f"Model '{model}' not found on {provider}", user_hint=hint
        )


class DiskSpaceError(DocrawlError):
    """Insufficient disk space."""

    def __init__(self, free_gb: float, required_gb: float = 1.0):
        super().__init__(
            message=f"Low disk space: {free_gb:.2f}GB free (need {required_gb}GB)",
            user_hint="Free up disk space or change output directory",
        )


class PermissionDeniedError(DocrawlError):
    """Cannot write to output directory."""

    def __init__(self, path: str):
        super().__init__(
            message=f"Permission denied writing to {path}",
            user_hint="Run: sudo chown -R $USER:$USER ./data",
        )


class ProviderNotConfiguredError(DocrawlError):
    """API provider is missing required configuration."""

    def __init__(self, provider: str, missing_key: str):
        super().__init__(
            message=f"{provider} requires {missing_key} to be set",
            user_hint=f"Add {missing_key} to your .env file",
        )


class CrawlError(DocrawlError):
    """Generic error during crawl operation."""

    def __init__(self, message: str, url: str | None = None):
        full_msg = f"{message}" + (f" (URL: {url})" if url else "")
        super().__init__(message=full_msg)


class ValidationError(DocrawlError):
    """Input validation error."""

    def __init__(self, field: str, reason: str):
        super().__init__(
            message=f"Invalid {field}: {reason}",
            user_hint=f"Check the {field} field in the form",
        )


class LLMProviderError(DocrawlError):
    """Base class for all LLM provider errors."""

    def __init__(self, message: str, provider: str, user_hint: str | None = None):
        self.provider = provider
        super().__init__(message=message, user_hint=user_hint)


class LLMConnectionError(LLMProviderError):
    """Cannot connect to LLM provider."""

    def __init__(self, provider: str, detail: str = ""):
        super().__init__(
            message=f"Cannot connect to {provider}" + (f": {detail}" if detail else ""),
            provider=provider,
            user_hint=f"Check that {provider} is running and reachable",
        )


class LLMTimeoutError(LLMProviderError):
    """LLM provider request timed out."""

    def __init__(self, provider: str, timeout_s: int | float = 0):
        super().__init__(
            message=f"{provider} request timed out after {timeout_s}s",
            provider=provider,
            user_hint="Try increasing the timeout or use a smaller model",
        )


class LLMRateLimitError(LLMProviderError):
    """LLM provider returned HTTP 429 rate limit."""

    def __init__(self, provider: str, retry_after: int | None = None):
        self.retry_after = retry_after
        hint = f"Retry after {retry_after}s" if retry_after else "Wait and retry"
        super().__init__(
            message=f"{provider} rate limit exceeded",
            provider=provider,
            user_hint=hint,
        )
```

---

## `src/jobs/__init__.py`

```python

```

---

## `src/jobs/manager.py`

```python
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
    pages_retried: int = 0  # PR 4: scrape-level retry count
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
        logger.info(
            f"Created resume job {job_id} with {len(pending_urls)} pending URLs"
        )
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
```

---

## `src/jobs/runner.py`

*File truncated: showing first 500 of 1190 lines.*

```python
"""Job execution orchestration."""

import asyncio
import logging
import os as _os
import time
from dataclasses import dataclass as _dataclass
from pathlib import Path
from urllib.parse import urlparse

from src.jobs.manager import Job
from src.api.models import JobRequest
from src.crawler.discovery import discover_urls
from src.crawler.filter import filter_urls
from src.crawler.robots import RobotsParser
from src.llm.filter import filter_urls_with_llm
from src.llm.cleanup import cleanup_markdown, needs_llm_cleanup
from src.llm.client import get_available_models, get_provider_for_model
from src.scraper.page import (
    PageScraper,
    PagePool,
    fetch_markdown_native,
    fetch_markdown_proxy,
    fetch_html_fast,
)
from src.scraper.markdown import chunk_markdown
from src.scraper.detection import is_blocked_response, content_hash
from src.scraper.cache import PageCache
from src.jobs.state import save_job_state
from src.scraper.structured import (
    html_to_structured,
    save_structured,
    StructuredPage,
    ContentBlock,
)
from src.scraper.converters import get_converter
from src.scraper.converters.base import MarkdownConverter

logger = logging.getLogger(__name__)

MAX_SCRAPE_RETRIES = int(_os.environ.get("SCRAPE_MAX_RETRIES", "2"))


async def validate_models(
    crawl_model: str | None, pipeline_model: str | None, reasoning_model: str | None
) -> list[str]:
    """Validate that all required models are available.

    Returns list of errors, empty if all valid.  None values are skipped.
    """
    errors = []
    models_to_check = [
        ("crawl_model", crawl_model),
        ("pipeline_model", pipeline_model),
        ("reasoning_model", reasoning_model),
    ]

    for field, model in models_to_check:
        if model is None:
            continue
        provider = get_provider_for_model(model)

        try:
            available = await get_available_models(provider)
            model_names = [m["name"] for m in available]

            # For Ollama, check exact match or base model name
            if provider == "ollama":
                # Handle model names with tags (e.g., mistral:7b vs mistral:latest)
                base_model = model.split(":")[0]
                found = any(
                    m == model
                    or m == f"{base_model}:latest"
                    or m.startswith(f"{base_model}:")
                    for m in model_names
                )
                if not found and model_names:
                    errors.append(
                        f"Model '{model}' not found. Available: {', '.join(model_names[:5])}{'...' if len(model_names) > 5 else ''}"
                    )
            # For API providers, we trust the model list (they have many models)
            # Just check that we got a response
            elif not available and provider in ["openrouter", "opencode"]:
                errors.append(
                    f"Cannot verify model '{model}' - check {provider} API key"
                )

        except Exception as e:
            errors.append(f"Failed to validate {field} '{model}': {e}")

    return errors


async def _log(job: Job, event_type: str, data: dict) -> None:
    """Emit SSE event and log the message to stdout."""
    await job.emit_event(event_type, data)
    msg = data.get("message", "")
    if msg:
        phase = data.get("phase", "")
        model = data.get("active_model", "")
        level = data.get("level", "")
        prefix = f"[{job.id[:8]}] [{phase}]" if phase else f"[{job.id[:8]}]"
        suffix = f" [{model}]" if model else ""
        full_msg = f"{prefix} {msg}{suffix}"
        if level == "error":
            logger.error(full_msg)
        elif level == "warning":
            logger.warning(full_msg)
        else:
            logger.info(full_msg)


async def run_job(
    job: Job,
    page_pool: PagePool | None = None,
    resume_urls: list[str] | None = None,
) -> None:
    """Execute a crawl job with enriched phase/model SSE events.

    page_pool: optional pre-initialized PagePool from main.py lifespan (PR 1.2).
               If None, falls back to the legacy per-page create/close path.
    resume_urls: if provided, skip discovery/filtering and process only these URLs (PR 3.1).
    """
    # TODO: reasoning_model will be used for:
    # - Site structure analysis before crawling
    # - Complex content filtering (language selection, cross-page dedup)
    # - Documentation quality assessment
    # Currently unused, passed through for future pipeline stages
    job.status = "running"
    request = job.request
    base_url = str(request.url)

    scraper = PageScraper()
    robots = RobotsParser()
    # PR 3.4: resolve converter plugin (None → default "markdownify")
    _converter = get_converter(request.converter)

    try:
        # INIT phase
        await _log(
            job,
            "phase_change",
            {
                "phase": "init",
                "message": "Validating models...",
            },
        )

        # Validate models before starting (skip when all models are None — e.g. readerlm + skip_llm_cleanup)
        _any_model = any(
            m is not None
            for m in (
                request.crawl_model,
                request.pipeline_model,
                request.reasoning_model,
            )
        )
        validation_errors = (
            await validate_models(
                request.crawl_model, request.pipeline_model, request.reasoning_model
            )
            if _any_model
            else []
        )
        if validation_errors:
            error_msg = "; ".join(validation_errors)
            await _log(
                job,
                "log",
                {
                    "phase": "init",
                    "message": f"Model validation failed: {error_msg}",
                    "level": "error",
                },
            )
            job.status = "failed"
            await job.emit_event(
                "job_done",
                {
                    "status": "failed",
                    "error": f"Model validation failed: {error_msg}",
                },
            )
            return

        await _log(
            job,
            "phase_change",
            {
                "phase": "init",
                "message": "Initializing browser...",
            },
        )
        await scraper.start()
        await _log(
            job,
            "phase_change",
            {
                "phase": "init",
                "message": "Browser ready",
            },
        )

        # Robots.txt
        if request.respect_robots_txt:
            await robots.load(base_url)
            if robots.crawl_delay:
                delay_s = max(request.delay_ms / 1000, robots.crawl_delay)
                await _log(
                    job,
                    "log",
                    {
                        "phase": "init",
                        "message": f"robots.txt loaded (crawl-delay: {robots.crawl_delay}s, using {delay_s}s)",
                    },
                )
            else:
                delay_s = request.delay_ms / 1000
                await _log(
                    job,
                    "log",
                    {
                        "phase": "init",
                        "message": "robots.txt loaded (no crawl-delay)",
                    },
                )
        else:
            delay_s = request.delay_ms / 1000

        # PR 3.1: skip discovery/filtering when resuming from saved state
        before_llm: float = 0.0
        llm_duration: float = 0.0
        if resume_urls is not None:
            urls = resume_urls
            await _log(
                job,
                "phase_change",
                {
                    "phase": "discovery",
                    "message": f"Resuming from state: {len(urls)} pending URLs (skipping discovery/filtering)",
                },
            )
        else:
            # DISCOVERY phase
            phase_start = time.monotonic()
            await _log(
                job,
                "phase_change",
                {
                    "phase": "discovery",
                    "message": "Crawling site structure...",
                },
            )

            urls = await discover_urls(
                base_url, request.max_depth, request.filter_sitemap_by_path
            )

            discovery_time = time.monotonic() - phase_start
            await _log(
                job,
                "log",
                {
                    "phase": "discovery",
                    "message": f"Found {len(urls)} URLs ({discovery_time:.1f}s)",
                },
            )

            if job.is_cancelled:
                return

            # FILTERING phase — basic
            phase_start = time.monotonic()
            total_before = len(urls)
            await _log(
                job,
                "phase_change",
                {
                    "phase": "filtering",
                    "message": "Applying basic filters...",
                },
            )

            urls = filter_urls(urls, base_url, request.language)
            after_basic = len(urls)
            removed_basic = total_before - after_basic
            await _log(
                job,
                "log",
                {
                    "phase": "filtering",
                    "message": f"Basic filtering: {total_before} → {after_basic} URLs (removed {removed_basic} non-doc)",
                },
            )

            # Robots.txt filtering
            if request.respect_robots_txt:
                before_robots = len(urls)
                urls = [u for u in urls if robots.is_allowed(u)]
                removed_robots = before_robots - len(urls)
                if removed_robots > 0:
                    await _log(
                        job,
                        "log",
                        {
                            "phase": "filtering",
                            "message": f"robots.txt: {before_robots} → {len(urls)} URLs (blocked {removed_robots})",
                        },
                    )

            # FILTERING phase — LLM (skipped when crawl_model is None)
            before_llm = len(urls)
            if request.crawl_model is not None:
                await _log(
                    job,
                    "phase_change",
                    {
                        "phase": "filtering",
                        "active_model": request.crawl_model,
                        "message": f"LLM filtering with {request.crawl_model}...",
                    },
                )

                llm_start = time.monotonic()
                urls = await filter_urls_with_llm(urls, request.crawl_model)
                llm_duration = time.monotonic() - llm_start
            else:
                llm_duration = 0.0

        if request.crawl_model is not None:
            await _log(
                job,
                "log",
                {
                    "phase": "filtering",
                    "active_model": request.crawl_model,
                    "message": f"LLM result: {before_llm} → {len(urls)} URLs ({llm_duration:.1f}s)",
                },
            )
        # end else (full discovery/filtering)

        job.pages_total = len(urls)

        if job.is_cancelled:
            return

        # SCRAPING + CLEANUP phase
        output_path = Path(request.output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        pages_ok = 0
        pages_partial = 0
        pages_failed = 0
        pages_skipped = 0  # PR 2.3: dedup skips
        pages_blocked = 0  # PR 2.3: bot-check pages
        pages_native_md = 0
        pages_proxy_md = 0
        pages_playwright = 0
        pages_http_fast = 0  # PR 1.3

        # PR 2.3: per-job content dedup state
        seen_hashes: set[str] = set()
        _hash_lock = asyncio.Lock()

        # PR 3.1: track completed/failed URLs for pause/resume checkpoint
        completed_urls: list[str] = []
        failed_urls: list[str] = []
        _url_track_lock = asyncio.Lock()

        # PR 2.4: optional page HTML cache
        page_cache: PageCache | None = None
        if request.use_cache:
            cache_dir = output_path / ".cache"
            page_cache = PageCache(cache_dir)

        # Semaphore enforces max_concurrent — closes CONS-010 / issue #56
        sem = asyncio.Semaphore(request.max_concurrent)
        # Lock to protect shared counters and job.pages_completed
        _counter_lock = asyncio.Lock()

        async def _process_page(i: int, url: str) -> None:
            nonlocal pages_ok, pages_partial, pages_failed, pages_skipped, pages_blocked
            nonlocal pages_native_md, pages_proxy_md, pages_playwright, pages_http_fast

            async with sem:
                # PR 3.1: suspend until job is resumed (no-op if running)
                await job.wait_if_paused()

                if job.is_cancelled:
                    return

                job.current_url = url
                page_start = time.monotonic()

                # Scraping sub-phase
                await _log(
                    job,
                    "phase_change",
                    {
                        "phase": "scraping",
                        "message": "Loading page...",
                        "progress": f"{i + 1}/{len(urls)}",
                        "url": url,
                    },
                )

                try:
                    markdown = None
                    native_token_count = None
                    raw_html: str | None = None  # PR 3.2: kept for structured output
                    fetch_method = "playwright"
                    load_time = 0.0

                    # PR 2.4: check cache before any network call
                    if page_cache is not None:
                        cached_html = page_cache.get(url)
                        if cached_html is not None:
                            markdown = _converter.convert(cached_html)  # PR 3.4
                            fetch_method = "cache"
                            load_time = time.monotonic() - page_start
                            await _log(
                                job,
                                "log",
                                {
                                    "phase": "scraping",
                                    "message": f"[{i + 1}/{len(urls)}] [cache] Served from cache {url} ({load_time:.2f}s)",
                                },
                            )

                    # Try native markdown via content negotiation
                    if request.use_native_markdown:
                        md_content, token_count = await fetch_markdown_native(url)
                        if md_content:
                            markdown = md_content
                            native_token_count = token_count
                            fetch_method = "native"
                            async with _counter_lock:
                                pages_native_md += 1
                            load_time = time.monotonic() - page_start
                            token_info = (
                                f", {token_count} tokens" if token_count else ""
                            )
                            await _log(
                                job,
                                "log",
                                {
                                    "phase": "scraping",
                                    "message": f"[{i + 1}/{len(urls)}] [native-md] Skipped Playwright for {url} ({load_time:.1f}s{token_info})",
                                },
                            )

                    # Try markdown proxy as fallback
                    if markdown is None and request.use_markdown_proxy:
                        proxy_url = request.markdown_proxy_url or "https://markdown.new"
                        md_content, _ = await fetch_markdown_proxy(url, proxy_url)
                        if md_content:
                            markdown = md_content
                            fetch_method = "proxy"
                            async with _counter_lock:
                                pages_proxy_md += 1
                            load_time = time.monotonic() - page_start
                            await _log(
                                job,
                                "log",
                                {
                                    "phase": "scraping",
                                    "message": f"[{i + 1}/{len(urls)}] [proxy-md] Fetched via proxy for {url} ({load_time:.1f}s)",
                                },
                            )

                    # HTTP fast-path: try plain HTTP before Playwright (PR 1.3)
                    if markdown is None and request.use_http_fast_path:
                        fast_md = await fetch_html_fast(url)
                        if fast_md:
                            markdown = fast_md
                            fetch_method = "http_fast"
                            async with _counter_lock:
                                pages_http_fast += 1
                            load_time = time.monotonic() - page_start
                            await _log(
                                job,
                                "log",
                                {
                                    "phase": "scraping",
                                    "message": f"[{i + 1}/{len(urls)}] [http-fast] Skipped Playwright for {url} ({load_time:.1f}s)",
                                },
                            )

                    # Fall back to Playwright with retries (pass pool if available — PR 1.2)
                    if markdown is None:
                        for _attempt in range(MAX_SCRAPE_RETRIES + 1):
                            try:
                                html = await scraper.get_html(
                                    url,
                                    pool=page_pool,
                                    content_selectors=request.content_selectors,
                                    noise_selectors=request.noise_selectors,
                                )
                                break
                            except asyncio.CancelledError:
# ... truncated ...
```

---

## `src/jobs/state.py`

```python
"""Job state persistence for pause/resume (PR 3.1).

State file: {output_path}/.job_state.json
Contains: serialized JobRequest + URL lists (completed, failed, pending)

Design decisions:
- Atomic write (.tmp → os.replace) for crash safety
- resume-from-state creates a new job with only pending URLs
- Sites may change between pause and resume (404s go to failed)
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STATE_FILENAME = ".job_state.json"


@dataclass
class JobState:
    """Serializable snapshot of a paused job's progress."""

    job_id: str
    request: dict  # serialized JobRequest
    completed_urls: list[str]
    failed_urls: list[str]
    pending_urls: list[str]


def save_job_state(
    output_path: Path,
    job_id: str,
    request_dict: dict[str, Any],
    completed_urls: list[str],
    failed_urls: list[str],
    pending_urls: list[str],
) -> Path:
    """Atomically write job state to {output_path}/.job_state.json.

    Returns the path to the written state file.
    Raises on write error.
    """
    state = {
        "job_id": job_id,
        "request": request_dict,
        "completed_urls": completed_urls,
        "failed_urls": failed_urls,
        "pending_urls": pending_urls,
    }
    state_path = output_path / STATE_FILENAME
    tmp_path = state_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp_path, state_path)
    logger.info(
        f"Job state saved: {len(completed_urls)} done, {len(failed_urls)} failed, {len(pending_urls)} pending"
    )
    return state_path


def load_job_state(state_path: Path) -> JobState:
    """Load job state from a .job_state.json file.

    Raises ValueError if the file is corrupt or missing required fields.
    """
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to read state file {state_path}: {e}") from e

    required = {"job_id", "request", "completed_urls", "failed_urls", "pending_urls"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"State file missing fields: {missing}")

    return JobState(
        job_id=data["job_id"],
        request=data["request"],
        completed_urls=data["completed_urls"],
        failed_urls=data["failed_urls"],
        pending_urls=data["pending_urls"],
    )
```

---

## `src/llm/__init__.py`

```python

```

---

## `src/llm/cleanup.py`

```python
"""LLM-based markdown cleanup with smart skip and dynamic timeouts."""

import asyncio
import re
import logging
from typing import Any, Literal

from src.llm.client import generate

logger = logging.getLogger(__name__)

CLEANUP_SYSTEM_PROMPT = """You are a documentation cleaner. Clean up markdown from HTML docs.
Remove navigation residue, footers, ads, fix formatting. Keep all documentation content intact."""

CLEANUP_PROMPT_TEMPLATE = """Clean this markdown. Remove nav menus, breadcrumbs, footer, sidebar residue, ads, broken formatting.
Keep all documentation content, code examples, and links.
Return only cleaned markdown.

{markdown}"""

HEAVY_CLEANUP_PROMPT_TEMPLATE = """Clean this markdown. Remove nav menus, breadcrumbs, footer, sidebar residue, ads.
Additionally:
- Repair broken Markdown tables (add missing separator rows with ---)
- Fix LaTeX/math expressions: preserve \\frac{{}}{{}}, \\begin{{}}{{}}, $...$, etc.
- Restore correct table alignment and column structure.
Keep all documentation content, code examples, and links.
Return only cleaned markdown.

{markdown}"""

MAX_RETRIES = 3
# Exponential backoff: 1s, 2s, 4s (2**attempt)

# Dynamic timeout constants
BASE_TIMEOUT = 45  # seconds for small chunks
TIMEOUT_PER_KB = 10  # extra seconds per KB of content
MAX_TIMEOUT = 90  # cap

# Noise indicators for needs_llm_cleanup()
_NOISE_INDICATORS = [
    "cookie",
    "privacy policy",
    "terms of service",
    "subscribe",
    "toggle dark",
    "toggle light",
    "dark mode",
    "light mode",
    "skip to content",
    "table of contents",
    "on this page",
    "all rights reserved",
    "powered by",
]

_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")

# PR 2.2 — Expanded Heuristics
CleanupLevel = Literal["skip", "cleanup", "heavy"]

# Broken table heuristic: pipe-separated row without a separator row (---|---) nearby
_TABLE_ROW_RE = re.compile(r"^\|.+\|$", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|$", re.MULTILINE)

# LaTeX patterns (avoid false positives like $9.99)
_LATEX_PATTERNS = [
    re.compile(r"\\frac\{"),
    re.compile(r"\\begin\{"),
    re.compile(r"\\end\{"),
    re.compile(r"\\[a-zA-Z]+\{"),  # \command{
    re.compile(r"\$[^$\d][^$]*\$"),  # $expr$ but not $9.99
]
# Price-like patterns to subtract from LaTeX score
_PRICE_RE = re.compile(r"\$\d+[\d.,]*")


def _has_broken_tables(markdown: str) -> bool:
    """Return True if the markdown has table rows but no separator row."""
    table_rows = _TABLE_ROW_RE.findall(markdown)
    if len(table_rows) < 2:
        return False
    sep_rows = _TABLE_SEP_RE.findall(markdown)
    # If there are table rows but no separator at all, it's broken
    return len(sep_rows) == 0


def _has_latex(markdown: str) -> bool:
    """Return True if the markdown likely contains LaTeX math expressions.

    Mitigates false positives from price strings like $9.99 by requiring
    at least one unambiguous LaTeX command match.
    """
    latex_matches = sum(1 for p in _LATEX_PATTERNS if p.search(markdown))
    if latex_matches == 0:
        return False
    # If only dollar-sign matches and they look like prices, skip
    price_matches = len(_PRICE_RE.findall(markdown))
    if latex_matches == 1 and price_matches > 0:
        return False
    return True


def _code_density(markdown: str) -> float:
    """Return fraction of the markdown that is inside fenced code blocks."""
    if not markdown:
        return 0.0
    code_blocks = _CODE_BLOCK_RE.findall(markdown)
    code_chars = sum(len(b) for b in code_blocks)
    return code_chars / len(markdown)


def classify_chunk(markdown: str) -> CleanupLevel:
    """Classify a chunk by the level of LLM cleanup needed.

    Returns:
        "skip"    — chunk is already clean (mostly code, or short without noise)
        "cleanup" — standard LLM cleanup needed
        "heavy"   — cleanup + table repair + LaTeX fix needed (PR 2.2)
    """
    lower = markdown.lower()

    # Check for noise indicators — always needs at least cleanup
    has_noise = any(indicator in lower for indicator in _NOISE_INDICATORS)

    # Mostly-code chunks are clean
    if _code_density(markdown) > 0.6:
        return "skip"

    # Short clean text without noise
    if len(markdown) < 2000 and not has_noise:
        return "skip"

    # Heavy cleanup for complex content
    if _has_broken_tables(markdown) or _has_latex(markdown):
        return "heavy"

    if has_noise:
        return "cleanup"

    return "cleanup" if len(markdown) >= 2000 else "skip"


def needs_llm_cleanup(markdown: str) -> bool:
    """Check if a chunk needs LLM cleanup or is already clean.

    Backward-compatible wrapper around classify_chunk() (PR 2.2).
    Returns False only for "skip" level.
    """
    return classify_chunk(markdown) != "skip"


def _estimate_tokens(text: str) -> int:
    """Estimate token count using code-density-adjusted char/token ratios (PR 2.5).

    Ratios (chars per token):
    - code-heavy (density > 0.5): 3.0 — code tokens are shorter on average
    - mixed (density > 0.2):      3.5
    - prose:                       4.0

    This replaces the flat len(text) // 4 heuristic throughout cleanup and filter.
    """
    density = _code_density(text)
    if density > 0.5:
        ratio = 3.0
    elif density > 0.2:
        ratio = 3.5
    else:
        ratio = 4.0
    return max(1, int(len(text) / ratio))


def _cleanup_options(markdown: str) -> dict[str, Any]:
    """Calculate Ollama options optimized for cleanup tasks.

    num_ctx is sized to the actual content so Ollama never silently truncates
    the input — closes CONS-011 / issue #57.
    """
    estimated_input_tokens = _estimate_tokens(markdown)  # PR 2.5: adaptive ratio
    # Reserve ~512 tokens for system prompt + cleanup prompt overhead
    num_ctx = max(2048, estimated_input_tokens + 1024)
    return {
        "num_ctx": num_ctx,
        "num_predict": min(estimated_input_tokens + 512, 4096),
        "temperature": 0.1,
        "num_batch": 1024,
    }


def _calculate_timeout(content: str) -> int:
    """Calculate dynamic timeout based on chunk size and token estimate (PR 2.5)."""
    tokens = _estimate_tokens(content)
    timeout = int(BASE_TIMEOUT + (tokens / 250) * 10)
    return min(timeout, MAX_TIMEOUT)


async def cleanup_markdown(markdown: str, model: str) -> str:
    """Use LLM to clean up markdown content.

    Uses dynamic timeout based on chunk size. Retries with backoff.
    Selects standard or heavy prompt based on classify_chunk() (PR 2.2).
    Raises RuntimeError if all retries are exhausted so the caller can
    handle the failure (e.g. increment pages_partial counter).
    """
    # Wrap content in XML delimiters to isolate scraped data from prompt — closes CONS-006 / issue #58
    wrapped = f"<document>\n{markdown}\n</document>"
    level = classify_chunk(markdown)
    template = (
        HEAVY_CLEANUP_PROMPT_TEMPLATE if level == "heavy" else CLEANUP_PROMPT_TEMPLATE
    )
    prompt = template.format(markdown=wrapped)
    timeout = _calculate_timeout(markdown)
    options = _cleanup_options(markdown)

    for attempt in range(MAX_RETRIES):
        try:
            cleaned = await generate(
                model,
                prompt,
                system=CLEANUP_SYSTEM_PROMPT,
                timeout=timeout,
                options=options,
            )
            if cleaned.strip():
                return cleaned.strip()
        except Exception as e:
            logger.warning(
                f"Cleanup attempt {attempt + 1} failed ({timeout}s timeout): {e}"
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)  # 1s, 2s, 4s

    raise RuntimeError(
        f"All {MAX_RETRIES} cleanup attempts failed for chunk of {len(markdown)} chars"
    )
```

---

## `src/llm/client.py`

*File truncated: showing first 500 of 525 lines.*

```python
"""LLM client supporting multiple providers: Ollama, OpenRouter, OpenCode."""

# 🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.

import os
import time
import logging
from typing import Any

import httpx

from src.exceptions import LLMConnectionError, LLMTimeoutError, LLMRateLimitError

logger = logging.getLogger(__name__)

# Model list cache: provider -> (models, timestamp)
_model_cache: dict[str, tuple[list[dict[str, Any]], float]] = {}
MODEL_CACHE_TTL = 60  # seconds

# Environment variables
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENCODE_API_KEY = os.environ.get("OPENCODE_API_KEY", "")
LMSTUDIO_URL = os.environ.get("LMSTUDIO_URL", "http://localhost:1234/v1")
LMSTUDIO_API_KEY = os.environ.get("LMSTUDIO_API_KEY", "")
LLAMACPP_URL = os.environ.get("LLAMACPP_URL", "http://localhost:8080/v1")
LLAMACPP_API_KEY = os.environ.get("LLAMACPP_API_KEY", "")

# Provider configurations
PROVIDERS = {
    "ollama": {
        "base_url": OLLAMA_URL,
        "requires_api_key": False,
        "model_format": "model",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "requires_api_key": True,
        "model_format": "model",
    },
    "opencode": {
        "base_url": "https://api.opencode.ai/v1",
        "requires_api_key": True,
        "model_format": "model",
    },
    "lmstudio": {
        "base_url": LMSTUDIO_URL,
        "requires_api_key": False,
        "model_format": "model",
    },
    "llamacpp": {
        "base_url": LLAMACPP_URL,
        "requires_api_key": False,
        "model_format": "model",
    },
}

# Known models by provider (for UI selectors)
# These are used to filter/populate the model selectors based on provider
PROVIDER_MODELS = {
    "ollama": [],  # Dynamic - fetched from Ollama API
    "openrouter": [],  # Dynamic - fetched from OpenRouter API
    "opencode": [
        "opencode/claude-sonnet-4-5",
        "opencode/claude-haiku-4-5",
        "opencode/gpt-5-nano",
        "opencode/minimax-m2.5-free",
        "opencode/kimi-k2.5-free",
        "opencode/glm-4.7-free",
    ],
    "llamacpp": [],  # Dynamic - fetched from llama.cpp API
}


async def get_available_models(provider: str = "ollama") -> list[dict[str, Any]]:
    """Get list of available models for a provider. Results cached for MODEL_CACHE_TTL seconds."""
    now = time.monotonic()
    cached = _model_cache.get(provider)
    if cached is not None:
        models, ts = cached
        if now - ts < MODEL_CACHE_TTL:
            logger.debug(f"Model cache hit for provider '{provider}'")
            return models

    if provider == "ollama":
        models = await _get_ollama_models()
    elif provider == "openrouter":
        models = await _get_openrouter_models()
    elif provider == "opencode":
        models = _get_opencode_models()
    elif provider == "lmstudio":
        models = await _get_lmstudio_models()
    elif provider == "llamacpp":
        models = await _get_llamacpp_models()
    else:
        return []

    _model_cache[provider] = (models, now)
    return models


async def _get_ollama_models() -> list[dict[str, Any]]:
    """Get list of available Ollama models."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags", timeout=10)
            response.raise_for_status()
            data = response.json()
            return [
                {
                    "name": m["name"],
                    "size": m.get("size"),
                    "provider": "ollama",
                    "is_free": True,
                }
                for m in data.get("models", [])
            ]
    except Exception as e:
        logger.error(f"Failed to get Ollama models: {e}")
        return []


async def _get_lmstudio_models() -> list[dict[str, Any]]:
    """Get list of available LM Studio models."""
    try:
        headers = {}
        if LMSTUDIO_API_KEY:
            headers["Authorization"] = f"Bearer {LMSTUDIO_API_KEY}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{LMSTUDIO_URL}/models", headers=headers, timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return [
                {
                    "name": f"lmstudio/{m['id']}",
                    "size": None,
                    "provider": "lmstudio",
                    "is_free": True,
                }
                for m in data.get("data", [])
            ]
    except Exception as e:
        logger.error(f"Failed to get LM Studio models: {e}")
        return []


async def _get_llamacpp_models() -> list[dict[str, Any]]:
    """Get list of available llama.cpp server models."""
    try:
        headers = {}
        if LLAMACPP_API_KEY:
            headers["Authorization"] = f"Bearer {LLAMACPP_API_KEY}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{LLAMACPP_URL}/models", headers=headers, timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return [
                {
                    "name": f"llamacpp/{m['id']}",
                    "size": None,
                    "provider": "llamacpp",
                    "is_free": True,
                }
                for m in data.get("data", [])
            ]
    except Exception as e:
        logger.error(f"Failed to get llama.cpp models: {e}")
        return []


def _is_free_model(model_name: str, provider: str) -> bool:
    """Determine if a model is free based on name patterns."""
    if provider == "ollama":
        return True
    if provider == "lmstudio":
        return True
    if provider == "llamacpp":
        return True
    if provider == "openrouter":
        return ":free" in model_name
    if provider == "opencode":
        return "-free" in model_name or "free" in model_name.lower()
    return False


async def _get_openrouter_models() -> list[dict[str, Any]]:
    """Get list of OpenRouter models from API — async to avoid blocking event loop (closes CONS-013 / issue #59)."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            models = []
            for m in data.get("data", []):
                model_id = m.get("id", "")
                pricing = m.get("pricing", {})
                name = m.get("name", "") or ""
                description = m.get("description", "") or ""

                prompt_price = float(pricing.get("prompt", "0") or 0)

                is_free = (
                    prompt_price == 0
                    or ":free" in model_id
                    or "free" in name.lower()
                    or "free" in description.lower()
                )

                models.append(
                    {
                        "name": model_id,
                        "size": None,
                        "provider": "openrouter",
                        "is_free": is_free,
                    }
                )
            return models
    except Exception as e:
        logger.error(f"Failed to get OpenRouter models: {e}")
        return []


def _get_opencode_models() -> list[dict[str, Any]]:
    """Get list of OpenCode models."""
    return [
        {
            "name": m,
            "size": None,
            "provider": "opencode",
            "is_free": _is_free_model(m, "opencode"),
        }
        for m in PROVIDER_MODELS["opencode"]
    ]


def get_provider_for_model(model: str) -> str:
    """Determine provider based on model name."""
    if "/" in model:
        # Models with namespace (e.g., openai/gpt-4, qwen/qwen3-14b)
        provider_prefix = model.split("/")[0]
        if provider_prefix in PROVIDERS:
            return provider_prefix
    # Default to ollama for bare model names
    return "ollama"


async def generate(
    model: str,
    prompt: str,
    system: str | None = None,
    timeout: int = 120,
    options: dict[str, Any] | None = None,
) -> str:
    """Generate text using the appropriate provider."""
    provider = get_provider_for_model(model)

    if provider == "ollama":
        return await _generate_ollama(model, prompt, system, timeout, options)
    elif provider == "openrouter":
        return await _generate_openrouter(model, prompt, system, timeout, options)
    elif provider == "opencode":
        return await _generate_opencode(model, prompt, system, timeout, options)
    elif provider == "lmstudio":
        return await _generate_lmstudio(model, prompt, system, timeout, options)
    elif provider == "llamacpp":
        return await _generate_llamacpp(model, prompt, system, timeout, options)
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def _generate_ollama(
    model: str,
    prompt: str,
    system: str | None,
    timeout: int,
    options: dict[str, Any] | None,
) -> str:
    """Generate text using Ollama."""
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system
    if options:
        payload["options"] = options

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            logger.info(
                "llm_tokens",
                extra={
                    "prompt_tokens": data.get("prompt_eval_count"),
                    "completion_tokens": data.get("eval_count"),
                    "model": model,
                },
            )
            return data.get("response", "")
    except httpx.TimeoutException:
        logger.error(f"Ollama request timed out after {timeout}s")
        raise LLMTimeoutError("ollama", timeout)
    except httpx.ConnectError as e:
        logger.error(f"Ollama connection failed: {e}")
        raise LLMConnectionError("ollama", str(e))
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        raise


async def _generate_openrouter(
    model: str,
    prompt: str,
    system: str | None,
    timeout: int,
    options: dict[str, Any] | None,
) -> str:
    """Generate text using OpenRouter."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not configured")

    payload: dict[str, Any] = {
        "model": model,
        "messages": [],
    }
    if system:
        payload["messages"].append({"role": "system", "content": system})
    payload["messages"].append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PROVIDERS['openrouter']['base_url']}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            if response.status_code == 429:
                retry_after_str = response.headers.get("retry-after", "")
                retry_after = (
                    int(retry_after_str) if retry_after_str.isdigit() else None
                )
                raise LLMRateLimitError("openrouter", retry_after)
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except LLMRateLimitError:
        raise
    except httpx.TimeoutException:
        logger.error(f"OpenRouter request timed out after {timeout}s")
        raise LLMTimeoutError("openrouter", timeout)
    except httpx.ConnectError as e:
        logger.error(f"OpenRouter connection failed: {e}")
        raise LLMConnectionError("openrouter", str(e))
    except Exception as e:
        logger.error(f"OpenRouter request failed: {e}")
        raise


async def _generate_opencode(
    model: str,
    prompt: str,
    system: str | None,
    timeout: int,
    options: dict[str, Any] | None,
) -> str:
    """Generate text using OpenCode."""
    if not OPENCODE_API_KEY:
        raise ValueError("OPENCODE_API_KEY not configured")

    payload: dict[str, Any] = {
        "model": model,
        "messages": [],
    }
    if system:
        payload["messages"].append({"role": "system", "content": system})
    payload["messages"].append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {OPENCODE_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PROVIDERS['opencode']['base_url']}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except httpx.TimeoutException:
        logger.error(f"OpenCode request timed out after {timeout}s")
        raise LLMTimeoutError("opencode", timeout)
    except httpx.ConnectError as e:
        logger.error(f"OpenCode connection failed: {e}")
        raise LLMConnectionError("opencode", str(e))
    except Exception as e:
        logger.error(f"OpenCode request failed: {e}")
        raise


async def _generate_lmstudio(
    model: str,
    prompt: str,
    system: str | None,
    timeout: int,
    options: dict[str, Any] | None,
) -> str:
    """Generate text using LM Studio."""
    model_id = model.removeprefix("lmstudio/")
    payload: dict[str, Any] = {
        "model": model_id,
        "messages": [],
    }
    if system:
        payload["messages"].append({"role": "system", "content": system})
    payload["messages"].append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json"}
    if LMSTUDIO_API_KEY:
        headers["Authorization"] = f"Bearer {LMSTUDIO_API_KEY}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{LMSTUDIO_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except httpx.TimeoutException:
        logger.error(f"LM Studio request timed out after {timeout}s")
        raise LLMTimeoutError("lmstudio", timeout)
    except httpx.ConnectError as e:
        logger.error(f"LM Studio connection failed: {e}")
        raise LLMConnectionError("lmstudio", str(e))
    except Exception as e:
        logger.error(f"LM Studio request failed: {e}")
        raise


async def _generate_llamacpp(
    model: str,
    prompt: str,
    system: str | None,
    timeout: int,
    options: dict[str, Any] | None,
) -> str:
    """Generate text using llama.cpp server."""
    model_id = model.removeprefix("llamacpp/")
    payload: dict[str, Any] = {
        "model": model_id,
        "messages": [],
    }
    if system:
        payload["messages"].append({"role": "system", "content": system})
    payload["messages"].append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json"}
    if LLAMACPP_API_KEY:
        headers["Authorization"] = f"Bearer {LLAMACPP_API_KEY}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{LLAMACPP_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except httpx.TimeoutException:
# ... truncated ...
```

---

## `src/llm/filter.py`

```python
"""LLM-based URL filtering."""

import asyncio
import json
import logging
from typing import Any

from src.llm.client import generate
from src.llm.cleanup import _estimate_tokens  # PR 2.5: adaptive token estimate

logger = logging.getLogger(__name__)

FILTER_SYSTEM_PROMPT = """You are a documentation URL filter. Given a list of URLs from a documentation website,
filter out URLs that are not documentation content (e.g., blog posts, changelogs, API references if not requested).
Return only the filtered list of URLs in JSON format."""

FILTER_PROMPT_TEMPLATE = """Filter these documentation URLs, keeping only actual documentation pages.
Remove: blog posts, changelogs, release notes, download pages, asset files.
Keep: guides, tutorials, concepts, reference docs, getting started.

URLs:
{urls}

Return a JSON array of filtered URLs, ordered by suggested reading order (basics first, advanced later).
Only return the JSON array, no other text."""


def _filter_options(urls: list[str]) -> dict[str, Any]:
    """Build Ollama options scaled to the actual URL list size.

    Avoids silent truncation when sites have 100+ URLs — closes CONS-011 / issue #57.
    PR 2.5: uses _estimate_tokens() for adaptive ratio instead of flat // 4.
    """
    urls_text = "\n".join(urls)
    estimated_input_tokens = _estimate_tokens(urls_text) + 300  # + prompt overhead
    num_ctx = max(4096, estimated_input_tokens + 1024)
    return {
        "num_ctx": num_ctx,
        "num_predict": min(len(urls) * 20 + 256, 4096),  # output ≤ input URLs reprinted
        "temperature": 0.0,
        "num_batch": 1024,
    }


FILTER_MAX_RETRIES = 3


async def filter_urls_with_llm(urls: list[str], model: str) -> list[str]:
    """
    Use LLM to filter and order documentation URLs.

    Retries up to FILTER_MAX_RETRIES times with exponential backoff.
    Falls back to original list if all retries fail.
    """
    if not urls:
        return urls

    # Wrap URLs in XML delimiters to isolate user content from prompt — closes CONS-006 / issue #58
    urls_block = "<urls>\n" + "\n".join(urls) + "\n</urls>"
    prompt = FILTER_PROMPT_TEMPLATE.format(urls=urls_block)

    for attempt in range(FILTER_MAX_RETRIES):
        try:
            response = await generate(
                model,
                prompt,
                system=FILTER_SYSTEM_PROMPT,
                options=_filter_options(urls),
            )

            # Try to parse JSON from response
            # Handle potential markdown code blocks
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1])

            filtered = json.loads(response)
            if isinstance(filtered, list):
                # Validate all items are from original list
                valid = [url for url in filtered if url in urls]
                logger.info(f"LLM filtered {len(urls)} URLs to {len(valid)}")
                return valid

        except Exception as e:
            if attempt < FILTER_MAX_RETRIES - 1:
                wait = 2**attempt  # 1s, 2s, 4s
                logger.warning(
                    f"LLM filtering attempt {attempt + 1} failed, retrying in {wait}s: {e}"
                )
                await asyncio.sleep(wait)
            else:
                logger.warning(
                    f"LLM filtering failed after {FILTER_MAX_RETRIES} attempts, using original list: {e}"
                )

    return urls
```

---

## `src/main.py`

```python
"""FastAPI application entry point."""

import json
import logging
import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import router, limiter, job_manager
from src.scraper.page import PagePool


# ── Structured JSON logging — closes #109 ────────────────────────────────────


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "taskName",
            ):
                log[key] = value
        if record.exc_info:
            log["exc_type"] = (
                record.exc_info[0].__name__ if record.exc_info[0] else None
            )
        return json.dumps(log, default=str)


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)

logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared resources on startup, clean up on shutdown."""
    # PR 1.2 — Page Pool: pre-warm a pool of Playwright pages shared across jobs.
    # PAGE_POOL_SIZE=0 disables the pool (legacy per-page create/close path).
    pool_size = int(os.environ.get("PAGE_POOL_SIZE", "5"))
    if pool_size > 0:
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        pool = PagePool(browser, size=pool_size)
        await pool.initialize()
        job_manager.page_pool = pool
        logger.info(f"PagePool ready (size={pool_size})")
    else:
        playwright = None
        browser = None
        pool = None
        logger.info("PagePool disabled (PAGE_POOL_SIZE=0)")

    # PR 1.5: start background cleanup loop (removes expired completed jobs)
    import asyncio as _asyncio

    cleanup_task = _asyncio.create_task(job_manager.start_cleanup_loop())

    yield

    # Shutdown: cancel cleanup loop, then cancel jobs, then close pool and browser
    cleanup_task.cancel()
    await job_manager.shutdown()
    if pool is not None:
        await pool.close()
    if browser is not None:
        await browser.close()
    if playwright is not None:
        await playwright.stop()


# ── App ───────────────────────────────────────────────────────────────────────

API_VERSION = "0.9.10"

app = FastAPI(title="Docrawl", version=API_VERSION, lifespan=lifespan)

UI_PATH = Path(__file__).parent / "ui"

# ── Rate limiter — closes CONS-007 / issue #53 ───────────────────────────────
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": str(exc.detail)})


# ── CORS — closes CONS-034 / issue #80 ───────────────────────────────────────
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else [],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Api-Key"],
)


# ── Security headers — closes CONS-022 / issue #68 ───────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self';"
        )
        response.headers["X-API-Version"] = API_VERSION
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ── API key auth — closes CONS-003 / issue #48 ───────────────────────────────
_API_KEY = os.environ.get("API_KEY", "").strip()

_AUTH_EXEMPT = {"/", "/api/health/ready"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _API_KEY:
            return await call_next(request)
        if request.url.path in _AUTH_EXEMPT:
            return await call_next(request)
        key = request.headers.get("X-Api-Key", "")
        if key != _API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized — X-Api-Key required"},
            )
        return await call_next(request)


app.add_middleware(ApiKeyMiddleware)

app.include_router(router, prefix="/api")


# ── Global error sanitization — closes #113 ──────────────────────────────────
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a sanitized error response; never expose internal details."""
    logger.error(
        "unhandled_exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "exc_type": type(exc).__name__,
            "detail": traceback.format_exc(),
        },
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )


@app.get("/")
async def serve_ui() -> FileResponse:
    """Serve the main UI."""
    return FileResponse(UI_PATH / "index.html")
```

---

## `src/scraper/__init__.py`

```python

```

---

## `src/scraper/cache.py`

```python
"""Per-job page HTML cache with TTL and atomic writes (PR 2.4).

Cache layout: {output_path}/.cache/{url_hash}.json
Each entry: {"url": str, "html": str, "timestamp": float}

Design decisions:
- opt-in via JobRequest.use_cache (default False)
- TTL 24h default (CACHE_TTL env var)
- atomic write: .tmp → os.replace() for Windows compat
- blocked responses are never cached (checked by caller)
- corrupted cache files are silently removed
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TTL = int(os.environ.get("CACHE_TTL", str(24 * 3600)))  # 24 hours


class PageCache:
    """Simple disk-based HTML cache with TTL.

    Args:
        cache_dir: Directory where cache files are stored.
        ttl: Time-to-live in seconds. 0 disables TTL (entries never expire).
    """

    def __init__(self, cache_dir: Path, ttl: int = DEFAULT_TTL) -> None:
        self._dir = cache_dir
        self._ttl = ttl
        self._hits = 0
        self._misses = 0
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, url: str) -> Path:
        """Derive a stable cache file path from the URL."""
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        return self._dir / f"{url_hash}.json"

    def get(self, url: str) -> str | None:
        """Return cached HTML for url, or None if cache miss / expired."""
        path = self._path(url)
        if not path.exists():
            self._misses += 1
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ts = float(data.get("timestamp", 0))
            if self._ttl > 0 and (time.time() - ts) > self._ttl:
                path.unlink(missing_ok=True)
                self._misses += 1
                return None
            if data.get("url") != url:
                # Hash collision (extremely rare) — treat as miss
                self._misses += 1
                return None
            self._hits += 1
            return data.get("html")
        except Exception:
            # Corrupt cache entry — remove silently
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            self._misses += 1
            return None

    def put(self, url: str, html: str) -> None:
        """Store HTML in cache using atomic write (.tmp → rename)."""
        path = self._path(url)
        tmp_path = path.with_suffix(".tmp")
        try:
            data = json.dumps({"url": url, "html": html, "timestamp": time.time()})
            tmp_path.write_text(data, encoding="utf-8")
            os.replace(tmp_path, path)  # atomic on Windows and POSIX
        except Exception as e:
            logger.debug(f"Cache write failed for {url}: {e}")
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses
```

---

## `src/scraper/converters/__init__.py`

```python
"""Converter registry for HTML -> Markdown backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MarkdownConverter(Protocol):
    def supports_tables(self) -> bool: ...
    def supports_code_blocks(self) -> bool: ...
    def convert(self, html: str) -> str: ...


_REGISTRY: dict[str, type] = {}


def register_converter(name: str, cls: type) -> None:
    _REGISTRY[name] = cls


def get_converter(name: str | None = None) -> MarkdownConverter:
    key = name or "markdownify"
    if key not in _REGISTRY:
        raise ValueError(f"Unknown converter: {key!r}. Available: {list(_REGISTRY)}")
    return _REGISTRY[key]()


def available_converters() -> list[str]:
    return list(_REGISTRY.keys())


# --- built-in registrations ---
from .markdownify_converter import MarkdownifyConverter  # noqa: E402

register_converter("markdownify", MarkdownifyConverter)

from .readerlm_converter import ReaderLMConverter  # noqa: E402

register_converter("readerlm", ReaderLMConverter)
register_converter(
    "readerlm-v1",
    type(
        "ReaderLMV1",
        (ReaderLMConverter,),
        {
            "__init__": lambda self, **kw: ReaderLMConverter.__init__(
                self, model="milkey/reader-lm:latest", **kw
            )
        },
    ),
)
```

---

## `src/scraper/converters/base.py`

```python
"""MarkdownConverter Protocol (PR 3.4).

All converters must implement this Protocol to be usable via the registry.
Uses @runtime_checkable for isinstance() checks.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class MarkdownConverter(Protocol):
    """Protocol for HTML → Markdown converters.

    Implementing this protocol is sufficient — no base class required.
    """

    def convert(self, html: str) -> str:
        """Convert HTML string to Markdown string."""
        ...

    def supports_tables(self) -> bool:
        """Return True if this converter renders HTML tables as Markdown tables."""
        ...

    def supports_code_blocks(self) -> bool:
        """Return True if this converter preserves fenced code block syntax."""
        ...
```

---

## `src/scraper/converters/markdownify_converter.py`

```python
"""Default MarkdownConverter using markdownify (PR 3.4).

This wraps the existing markdownify call used throughout the codebase.
Output is identical to the pre-converter-plugin behaviour.
"""

from markdownify import markdownify as _md


class MarkdownifyConverter:
    """Default HTML → Markdown converter using markdownify.

    Wraps the existing ``markdownify(html, heading_style="ATX", strip=[...])``
    call so it can be swapped out via the converter registry.
    """

    def convert(self, html: str) -> str:
        return _md(
            html, heading_style="ATX", strip=["script", "style", "nav", "footer"]
        )

    def supports_tables(self) -> bool:
        return True

    def supports_code_blocks(self) -> bool:
        return True
```

---

## `src/scraper/converters/readerlm_converter.py`

```python
"""ReaderLMConverter: HTML -> Markdown via ReaderLM-v2/v1 (Ollama).

Drop-in replacement for MarkdownifyConverter. Uses Ollama's /api/chat
endpoint to call a locally-hosted ReaderLM model trained specifically
for HTML-to-Markdown translation.

Usage (via registry)::

    converter = get_converter("readerlm")    # v2 (1.5B, default)
    converter = get_converter("readerlm-v1") # v1 (0.5B, CPU-friendly)

Or directly::

    from src.scraper.converters.readerlm_converter import ReaderLMConverter
    md = ReaderLMConverter().convert(html_string)
"""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Convert the following HTML to clean, well-formatted Markdown. "
    "Remove all navigation menus, footers, cookie banners, and ads. "
    "Preserve code blocks, tables, lists, and inline formatting exactly."
)

# Token-budget heuristic: HTML compresses ~3:1 to tokens; add 2 K headroom.
# Cap at 131 072 (ReaderLM-v2 max context).
_CTX_HEADROOM = 2048
_CTX_MAX = 131_072


class ReaderLMConverter:
    """Markdown converter that delegates HTML->MD to a local ReaderLM model.

    Implements the MarkdownConverter protocol expected by the converter
    registry (supports_tables, supports_code_blocks, convert).
    """

    def __init__(
        self,
        model: str = "milkey/reader-lm-v2:latest",
        ollama_base_url: str = "http://localhost:11434",
        timeout: float = 90.0,
    ) -> None:
        self.model = model
        self.base_url = ollama_base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # MarkdownConverter protocol
    # ------------------------------------------------------------------

    def supports_tables(self) -> bool:
        return True

    def supports_code_blocks(self) -> bool:
        return True

    def convert(self, html: str) -> str:
        """Convert *html* to Markdown synchronously (blocking)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an async context (e.g. pytest-asyncio).
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(asyncio.run, self._convert_async(html))
                return future.result()
        else:
            return asyncio.run(self._convert_async(html))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _convert_async(self, html: str) -> str:
        num_ctx = min(len(html) // 3 + _CTX_HEADROOM, _CTX_MAX)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": html},
            ],
            "stream": False,
            "options": {"num_ctx": num_ctx},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
```

---

## `src/scraper/detection.py`

```python
"""Blocked-response detection and content deduplication (PR 2.3)."""

import hashlib
import re

# 8 patterns for common blocked/bot-check responses.
# Threshold: >= 2 matches required to classify as blocked.
# This mitigates false positives in security documentation that mentions
# CAPTCHAs or Cloudflare as topics (those typically only match 1 pattern).
_BLOCKED_PATTERNS = [
    re.compile(r"checking your browser", re.IGNORECASE),
    re.compile(r"\bcaptcha\b", re.IGNORECASE),
    re.compile(r"\baccess denied\b", re.IGNORECASE),
    re.compile(r"\bcloudflare\b", re.IGNORECASE),
    re.compile(r"\bray id\b", re.IGNORECASE),
    re.compile(r"please enable javascript", re.IGNORECASE),
    re.compile(r"ddos protection", re.IGNORECASE),
    re.compile(r"just a moment", re.IGNORECASE),
]

_BLOCKED_THRESHOLD = 2


def is_blocked_response(content: str) -> bool:
    """Return True if content looks like a bot-check / blocked response.

    Uses a threshold of 2 out of 8 patterns to reduce false positives
    on documentation pages that *discuss* CAPTCHAs or Cloudflare.
    """
    if not content:
        return False
    matches = sum(1 for p in _BLOCKED_PATTERNS if p.search(content))
    return matches >= _BLOCKED_THRESHOLD


def content_hash(markdown: str) -> str:
    """Return an MD5 hex digest of the normalised markdown.

    Normalisation: collapse whitespace + lowercase before hashing.
    Used for per-job deduplication (~32 bytes per hash, ~32KB for 1000 URLs).
    """
    normalised = re.sub(r"\s+", " ", markdown.strip().lower())
    return hashlib.md5(normalised.encode("utf-8"), usedforsecurity=False).hexdigest()
```

---

## `src/scraper/markdown.py`

```python
"""HTML to Markdown conversion, pre-cleaning, and chunking."""

import re
import logging
from markdownify import markdownify as md

logger = logging.getLogger(__name__)

# Chunk size for LLM processing (in characters).
# 6000 chars ≈ 1500 tokens — fits safely in an 8192-token context window
# together with the system prompt and cleanup prompt overhead (~500 tokens).
# Fixes CONS-011 / issue #57: previous 16000-char chunks silently overflowed num_ctx.
DEFAULT_CHUNK_SIZE = 6000
CHUNK_OVERLAP = 200

# Regex patterns for noise in markdown (compiled for performance)
NOISE_PATTERNS = [
    re.compile(r"self\.__next_[a-zA-Z_]*", re.IGNORECASE),  # Next.js hydration
    re.compile(r"document\.querySelectorAll\([^)]*\)"),  # JS DOM manipulation
    re.compile(r"document\.getElementById\([^)]*\)"),
    re.compile(r"window\.addEventListener\([^)]*\)"),
    re.compile(r"data-page-mode\s*="),  # Framework attributes
    re.compile(r"suppressHydrationWarning"),
]

# Line-level noise patterns
NOISE_LINE_PATTERNS = [
    re.compile(r"^\s*On this page\s*$", re.IGNORECASE),
    re.compile(r"^\s*Edit this page\s*$", re.IGNORECASE),
    re.compile(r"^\s*Was this page helpful\??\s*$", re.IGNORECASE),
    re.compile(r"^\s*Last updated\s*(on\s+)?[\d/\-]+\s*$", re.IGNORECASE),
    re.compile(r"^\s*Skip to (main )?content\s*$", re.IGNORECASE),
    re.compile(r"^\s*Table of contents?\s*$", re.IGNORECASE),
    re.compile(r"^\s*Previous\s*$", re.IGNORECASE),
    re.compile(r"^\s*Next\s*$", re.IGNORECASE),
]


def _pre_clean_markdown(text: str) -> str:
    """Remove noise patterns from markdown before chunking."""
    # Remove lines matching noise patterns
    lines = text.split("\n")
    cleaned_lines: list[str] = []
    in_noise_block = False

    for line in lines:
        stripped = line.strip()

        # Skip CSS/JS blocks (lines between lone { and })
        if stripped == "{" and not in_noise_block:
            in_noise_block = True
            continue
        if in_noise_block:
            if stripped == "}" or stripped == "};":
                in_noise_block = False
            continue

        # Skip lines matching noise patterns
        if any(p.search(line) for p in NOISE_PATTERNS):
            continue

        # Skip noise lines
        if any(p.match(line) for p in NOISE_LINE_PATTERNS):
            continue

        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)

    # Collapse 3+ consecutive blank lines to 2
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def html_to_markdown(html: str) -> str:
    """Convert HTML to Markdown using markdownify."""
    return md(html, heading_style="ATX", strip=["script", "style", "nav", "footer"])


# Regex to find top-level headings (H1-H3) for semantic splitting (PR 2.1)
_HEADING_RE = re.compile(r"^(#{1,3})\s+", re.MULTILINE)
# Regex to find fenced code blocks for masking (PR 2.1)
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


def _mask_code_blocks(text: str) -> str:
    """Replace content inside fenced code blocks with spaces of equal length.

    This prevents # characters inside code blocks from being treated as
    heading boundaries during semantic chunking (PR 2.1).
    The returned string has the same character positions as the input.
    """

    def _blank(m: re.Match) -> str:
        # Keep the opening ``` and closing ``` fence markers; blank the content
        return " " * len(m.group(0))

    return _CODE_FENCE_RE.sub(_blank, text)


def _chunk_by_headings(text: str, chunk_size: int) -> list[str] | None:
    """Split markdown text at H1-H3 heading boundaries.

    Returns a list of sections, each starting with its heading.
    Returns None if fewer than 2 headings are found (fallback to size-based).
    Sections larger than chunk_size are further subdivided with _chunk_by_size().
    Code blocks are masked before scanning to avoid false heading matches.

    PR 2.1 — Semantic Chunking.
    """
    masked = _mask_code_blocks(text)
    heading_positions = [m.start() for m in _HEADING_RE.finditer(masked)]

    if len(heading_positions) < 2:
        return None

    sections: list[str] = []
    for idx, start in enumerate(heading_positions):
        end = (
            heading_positions[idx + 1]
            if idx + 1 < len(heading_positions)
            else len(text)
        )
        section = text[start:end].strip()
        if not section or len(section) < 50:
            continue
        if len(section) > chunk_size:
            # Subdivide oversized section
            sections.extend(_chunk_by_size(section, chunk_size))
        else:
            sections.append(section)

    return sections if sections else None


def _chunk_by_size(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    """Split text into chunks of at most chunk_size characters.

    Tries paragraph boundaries first, then single newlines, then hard-splits.
    Includes CHUNK_OVERLAP between consecutive chunks.
    This is the original chunking logic extracted from chunk_markdown() (PR 2.1).
    """
    if len(text) <= chunk_size:
        return [text] if len(text) >= 50 else ([text] if text.strip() else [])

    chunks: list[str] = []
    current_pos = 0

    while current_pos < len(text):
        end_pos = min(current_pos + chunk_size, len(text))

        if end_pos < len(text):
            # Try heading boundary first
            heading_pos = text.rfind("\n#", current_pos + chunk_size // 2, end_pos)
            if heading_pos > current_pos:
                end_pos = heading_pos + 1
            else:
                # Try paragraph boundary
                break_pos = text.rfind("\n\n", current_pos, end_pos)
                if break_pos > current_pos + chunk_size // 2:
                    end_pos = break_pos + 2
                else:
                    # Fall back to single newline
                    break_pos = text.rfind("\n", current_pos, end_pos)
                    if break_pos > current_pos + chunk_size // 2:
                        end_pos = break_pos + 1

        chunk = text[current_pos:end_pos].strip()
        if chunk and len(chunk) >= 50:
            chunks.append(chunk)

        current_pos = end_pos - CHUNK_OVERLAP if end_pos < len(text) else end_pos

    return chunks if chunks else [text.strip()]


def chunk_markdown(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    native_token_count: int | None = None,
) -> list[str]:
    """Split markdown into chunks for LLM processing.

    Pre-cleans markdown, then:
    1. Tries heading-based semantic splits (PR 2.1) — natural section boundaries.
    2. Falls back to size-based splitting if fewer than 2 headings are found.
    Skips tiny fragments (< 50 chars).
    """
    # Pre-clean before chunking
    text = _pre_clean_markdown(text)

    # If server provided a token count and it fits in one chunk, skip splitting.
    # Rough heuristic: 1 token ≈ 4 chars, so multiply token count by 4 to compare.
    if native_token_count is not None and native_token_count * 4 <= chunk_size:
        return [text] if len(text) >= 50 else ([text] if text.strip() else [])

    if len(text) <= chunk_size:
        return [text] if len(text) >= 50 else ([text] if text.strip() else [])

    # PR 2.1: try semantic heading-based chunking first
    heading_chunks = _chunk_by_headings(text, chunk_size)
    if heading_chunks:
        logger.info(
            f"Split markdown into {len(heading_chunks)} semantic chunks (headings)"
        )
        return heading_chunks

    # Fallback: size-based chunking
    size_chunks = _chunk_by_size(text, chunk_size)
    logger.info(f"Split markdown into {len(size_chunks)} chunks (size-based)")
    return size_chunks if size_chunks else [text.strip()]
```

---

## `src/scraper/page.py`

```python
"""Page scraping with Playwright — includes DOM noise removal and page pool."""

import asyncio
import logging
import httpx
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from playwright.async_api import async_playwright, Browser, Page

from src.utils.security import validate_url_not_ssrf

logger = logging.getLogger(__name__)


async def fetch_html_fast(url: str) -> str | None:
    """Try to fetch and convert a page to markdown without Playwright (HTTP fast-path).

    Uses httpx for a plain HTTP GET, converts the HTML response with markdownify,
    and returns the markdown only if it meets a minimum quality threshold (≥500 chars).
    Returns None if the page is JS-rendered, too short, or any error occurs.

    PR 1.3 — inserting before Playwright in the fallback chain saves
    browser overhead for static or server-rendered documentation sites.
    """
    validate_url_not_ssrf(url)
    try:
        headers = {
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "User-Agent": "DocRawl/0.9.8 (documentation crawler)",
        }
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return None
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None

            from markdownify import markdownify as md_convert

            markdown = md_convert(
                resp.text,
                heading_style="ATX",
                strip=["script", "style", "nav", "footer"],
            )
            if len(markdown) >= 500:
                return markdown
    except Exception:
        pass
    return None


async def fetch_markdown_native(url: str) -> tuple[str | None, int | None]:
    """Try to get native markdown via Accept: text/markdown content negotiation.

    Returns (markdown_content, token_count) or (None, None) if not available.
    """
    validate_url_not_ssrf(url)
    try:
        headers = {
            "Accept": "text/markdown, text/html;q=0.9, */*;q=0.8",
            "User-Agent": "Docrawl/1.0 (AI documentation crawler)",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=headers, timeout=15.0, follow_redirects=True
            )
            content_type = resp.headers.get("content-type", "")
            if "text/markdown" in content_type:
                token_count_str = resp.headers.get("x-markdown-tokens")
                token_count = int(token_count_str) if token_count_str else None
                return resp.text, token_count
    except Exception:
        pass
    return None, None


async def fetch_markdown_proxy(
    url: str, proxy_url: str = "https://markdown.new"
) -> tuple[str | None, None]:
    """Fetch markdown via a proxy service (markdown.new, r.jina.ai, etc).

    Returns (markdown_content, None) or (None, None) if unavailable.
    """
    validate_url_not_ssrf(url)
    try:
        proxy_target = f"{proxy_url.rstrip('/')}/{url}"
        headers = {"User-Agent": "Docrawl/1.0 (AI documentation crawler)"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                proxy_target, headers=headers, timeout=30.0, follow_redirects=True
            )
            if resp.status_code == 200 and len(resp.text) > 100:
                return resp.text, None
    except Exception:
        pass
    return None, None


# Selectors for noise elements to remove before extraction
NOISE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "nav",
    "footer",
    "header",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    ".sidebar",
    "#sidebar",
    ".navbar",
    "#navbar",
    ".table-of-contents",
    "#table-of-contents",
    ".breadcrumb",
    ".footer",
    ".header",
    ".cookie-banner",
    "[id*='mintlify']",
    ".prev-next-links",
    ".pagination-nav",
    ".edit-this-page",
    ".last-updated",
    ".theme-toggle",
    ".search-bar",
    "[data-search]",
]

# Selectors to try for main content extraction (in priority order)
CONTENT_SELECTORS = [
    "main",
    "article",
    "[role='main']",
    "#content",
    ".content",
    ".markdown-body",
    ".docs-content",
    ".documentation",
    "#main-content",
]

MIN_CONTENT_LENGTH = 200


class PageScraper:
    """Scrapes pages using Playwright with DOM pre-cleaning."""

    def __init__(self) -> None:
        self._browser: Browser | None = None
        self._playwright: object | None = None  # async_playwright context

    async def start(self) -> None:
        """Start the browser.

        Stores the playwright context so it can be properly stopped in stop(),
        preventing resource leaks if browser launch or subsequent operations fail.
        """
        playwright = await async_playwright().start()
        try:
            self._browser = await playwright.chromium.launch(headless=True)
        except Exception:
            await playwright.stop()
            raise
        self._playwright = playwright
        logger.info("Browser started")

    async def stop(self) -> None:
        """Stop the browser and the underlying playwright context."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            logger.info("Browser stopped")
        if self._playwright is not None:
            await self._playwright.stop()  # type: ignore[union-attr,attr-defined]
            self._playwright = None

    async def _remove_noise(
        self, page: Page, noise_selectors: list[str] | None = None
    ) -> None:
        """Remove noise elements from the DOM before extraction.

        Args:
            page: Playwright page to clean.
            noise_selectors: Additional CSS selectors to remove, prepended before
                the DocRawl defaults so user selectors are tried first.
        """
        selectors = list(noise_selectors or []) + NOISE_SELECTORS
        selector_list = ", ".join(selectors)
        removed = await page.evaluate(f"""() => {{
            const els = document.querySelectorAll(`{selector_list}`);
            let count = 0;
            els.forEach(el => {{ el.remove(); count++; }});
            return count;
        }}""")
        if removed:
            logger.debug(f"Removed {removed} noise elements from DOM")

    async def _extract_content(
        self, page: Page, content_selectors: list[str] | None = None
    ) -> str:
        """Extract main content HTML, trying specific selectors before body fallback.

        Args:
            page: Playwright page to extract from.
            content_selectors: Additional CSS selectors to try first, prepended before
                the DocRawl defaults so user selectors take priority.
        """
        selectors = list(content_selectors or []) + CONTENT_SELECTORS
        for selector in selectors:
            try:
                el = await page.query_selector(selector)
                if el:
                    html = await el.inner_html()
                    if len(html) >= MIN_CONTENT_LENGTH:
                        logger.debug(
                            f"Extracted content via '{selector}' ({len(html)} chars)"
                        )
                        return html
            except Exception:
                continue

        # readability-lxml fallback — extracts main content via Mozilla Readability algorithm
        try:
            from readability import Document
            from markdownify import markdownify as md_convert

            full_html = await page.content()
            doc = Document(full_html)
            summary_html = doc.summary()
            markdown = md_convert(summary_html, heading_style="ATX")
            if len(markdown) >= MIN_CONTENT_LENGTH:
                logger.debug(
                    f"Extracted content via readability-lxml ({len(markdown)} chars)"
                )
                return summary_html
        except Exception as e:
            logger.debug(f"readability-lxml fallback failed: {e}")

        # Fallback to body
        html = await page.inner_html("body")
        logger.debug(f"Fallback to body extraction ({len(html)} chars)")
        return html

    async def get_html(
        self,
        url: str,
        timeout: int = 30000,
        pool: "PagePool | None" = None,
        content_selectors: list[str] | None = None,
        noise_selectors: list[str] | None = None,
    ) -> str:
        """Navigate to URL, clean DOM, and extract content HTML.

        Args:
            url: Page URL to scrape.
            timeout: Navigation timeout in milliseconds.
            pool: If provided, borrows a page from the pool instead of creating one (PR 1.2).
            content_selectors: Custom content selectors to try before defaults
            noise_selectors: Custom noise selectors to remove before extraction
        """
        if not self._browser and pool is None:
            raise RuntimeError("Browser not started")

        # SSRF validation before Playwright navigates — closes CONS-002 / issue #51
        validate_url_not_ssrf(url)

        if pool is not None:
            async with pool.acquire() as page:
                await page.goto(url, timeout=timeout, wait_until="networkidle")
                await self._remove_noise(page, noise_selectors)
                return await self._extract_content(page, content_selectors)

        assert self._browser is not None  # guarded by RuntimeError above
        page = await self._browser.new_page()
        try:
            await page.goto(url, timeout=timeout, wait_until="networkidle")
            await self._remove_noise(page, noise_selectors)
            html = await self._extract_content(page, content_selectors)
            return html
        finally:
            await page.close()


class PagePool:
    """Pool of reusable Playwright pages backed by an asyncio.Queue (PR 1.2).

    Avoids the overhead of creating/closing a new page per URL.
    Pages are reset (about:blank + clear cookies) before re-use.
    If a page is found to be closed/broken on acquire, it is replaced automatically.

    Usage::

        pool = PagePool(browser, size=5)
        await pool.initialize()
        async with pool.acquire() as page:
            await page.goto(url)
        await pool.close()
    """

    def __init__(self, browser: Browser, size: int = 5) -> None:
        self._browser = browser
        self._size = size
        self._queue: asyncio.Queue[Page] = asyncio.Queue(maxsize=size)

    async def initialize(self) -> None:
        """Pre-create all pages and fill the queue."""
        for _ in range(self._size):
            page = await self._browser.new_page()
            await self._queue.put(page)
        logger.info(f"PagePool initialized with {self._size} pages")

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[Page, None]:
        """Context manager: borrow a page, reset it, return it to the pool."""
        page = await self._queue.get()
        try:
            # Reset state between uses
            try:
                await page.goto("about:blank", timeout=5000)
                await page.context.clear_cookies()
            except Exception:
                # Page is broken — replace it
                try:
                    await page.close()
                except Exception:
                    pass
                page = await self._browser.new_page()

            yield page
        except Exception:
            # Page might be in bad state — replace it
            try:
                await page.close()
            except Exception:
                pass
            page = await self._browser.new_page()
            raise
        finally:
            await self._queue.put(page)

    async def close(self) -> None:
        """Close all pages in the pool."""
        while not self._queue.empty():
            try:
                page = self._queue.get_nowait()
                await page.close()
            except Exception:
                pass
        logger.info("PagePool closed")
```

---

## `src/scraper/structured.py`

```python
"""Structured JSON output from HTML pages (PR 3.2).

Converts HTML to a typed block structure instead of plain markdown.
Block types: heading, paragraph, code, table, list, image, blockquote.

Design decisions:
- opt-in via JobRequest.output_format = "json" (default: "markdown")
- No LLM cleanup applied to JSON output (preserves raw content)
- BeautifulSoup parser, recurses into containers (div, section, article, main)
- Output file: same path as markdown but with .json extension
- Atomic write (.tmp → rename)
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

BlockType = Literal[
    "heading", "paragraph", "code", "table", "list", "image", "blockquote"
]

CONTAINER_TAGS = {"div", "section", "article", "main", "aside", "nav", "header"}


@dataclass
class ContentBlock:
    """A typed content block extracted from HTML."""

    type: BlockType
    content: str
    level: int | None = None  # For headings: 1-6
    language: str | None = None  # For code blocks: detected language
    alt: str | None = None  # For images: alt text


@dataclass
class StructuredPage:
    """Structured representation of a scraped page."""

    url: str
    title: str | None
    blocks: list[ContentBlock]


def _parse_element(el: Tag) -> list[ContentBlock]:
    """Recursively parse an HTML element into ContentBlocks."""
    blocks: list[ContentBlock] = []
    name = el.name if el.name else ""

    # Headings
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        text = el.get_text(separator=" ", strip=True)
        if text:
            blocks.append(
                ContentBlock(
                    type="heading",
                    content=text,
                    level=int(name[1]),
                )
            )
        return blocks

    # Code blocks
    if name == "pre":
        code_el = el.find("code")
        if code_el:
            lang = None
            for cls in code_el.get_attribute_list("class"):
                if cls.startswith("language-"):
                    lang = cls[len("language-") :]
                    break
            blocks.append(
                ContentBlock(
                    type="code",
                    content=code_el.get_text(),
                    language=lang,
                )
            )
        else:
            blocks.append(ContentBlock(type="code", content=el.get_text()))
        return blocks

    # Inline code (standalone)
    if name == "code" and (el.parent is None or el.parent.name != "pre"):
        text = el.get_text()
        if text.strip():
            blocks.append(ContentBlock(type="code", content=text))
        return blocks

    # Tables
    if name == "table":
        rows = []
        for row in el.find_all("tr"):
            cells = [
                td.get_text(separator=" ", strip=True)
                for td in row.find_all(["td", "th"])
            ]
            rows.append(cells)
        if rows:
            blocks.append(ContentBlock(type="table", content=json.dumps(rows)))
        return blocks

    # Lists
    if name in {"ul", "ol"}:
        items = [
            li.get_text(separator=" ", strip=True)
            for li in el.find_all("li", recursive=False)
        ]
        if items:
            blocks.append(ContentBlock(type="list", content="\n".join(items)))
        return blocks

    # Blockquotes
    if name == "blockquote":
        text = el.get_text(separator="\n", strip=True)
        if text:
            blocks.append(ContentBlock(type="blockquote", content=text))
        return blocks

    # Images
    if name == "img":
        src = el.get("src", "")
        alt = el.get("alt", "")
        if src:
            blocks.append(
                ContentBlock(
                    type="image", content=str(src), alt=str(alt) if alt else None
                )
            )
        return blocks

    # Paragraphs
    if name == "p":
        text = el.get_text(separator=" ", strip=True)
        if text:
            blocks.append(ContentBlock(type="paragraph", content=text))
        return blocks

    # Container elements — recurse
    if name in CONTAINER_TAGS or name in {"body", "html"}:
        for child in el.children:
            if isinstance(child, Tag):
                blocks.extend(_parse_element(child))
        return blocks

    # Fallback: extract text as paragraph for unrecognised tags.
    # 20-char threshold filters out stray single words / punctuation (e.g. nav labels).
    text = el.get_text(separator=" ", strip=True)
    if text and len(text) > 20:
        blocks.append(ContentBlock(type="paragraph", content=text))

    return blocks


def html_to_structured(url: str, html: str) -> StructuredPage:
    """Parse HTML into a StructuredPage with typed ContentBlocks."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title_el = soup.find("title")
    title = title_el.get_text(strip=True) if title_el else None

    # Find main content area
    content_el = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find("body")
        or soup
    )

    blocks: list[ContentBlock] = []
    if isinstance(content_el, Tag):
        blocks = _parse_element(content_el)

    return StructuredPage(url=url, title=title, blocks=blocks)


def save_structured(page: StructuredPage, file_path: Path) -> None:
    """Atomically write a StructuredPage as JSON to file_path.

    The file extension should be .json.
    """
    data = {
        "url": page.url,
        "title": page.title,
        "blocks": [asdict(b) for b in page.blocks],
    }
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.replace(tmp_path, file_path)
```

---

## `src/ui/__init__.py`

```python

```

---

## `src/utils/__init__.py`

```python

```

---

## `src/utils/security.py`

```python
"""Shared security utilities — SSRF validation."""

import ipaddress
import socket
from urllib.parse import urlparse

# Private/reserved network ranges
PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def validate_url_not_ssrf(url: str) -> None:
    """Raise ValueError if the URL resolves to a private/internal address.

    Closes CONS-002 / issue #51 (SSRF via Playwright).
    """
    host = urlparse(url).hostname
    if not host:
        raise ValueError(f"URL has no hostname: {url}")
    try:
        addr = ipaddress.ip_address(socket.gethostbyname(host))
        if any(addr in net for net in PRIVATE_NETS):
            raise ValueError(f"URL targets private/internal address: {url}")
    except socket.gaierror:
        pass  # DNS doesn't resolve — let it fail naturally later
```

---

## `src/ui/index.html`

*File truncated: showing first 500 of 1883 lines.*

```html
<!DOCTYPE html>
<!-- 🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review. -->
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Docrawl // SYNTHWAVE interface</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=VT323&family=IBM+Plex+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-deep: #0a0a12;
            --bg-panel: #12121f;
            --bg-input: #0d0d18;
            --accent-magenta: #ff00ff;
            --accent-cyan: #00ffff;
            --accent-amber: #ff6b00;
            --accent-green: #00ff88;
            --text-primary: #e0e0e0;
            --text-dim: #6a6a8a;
            --chrome-border: linear-gradient(180deg, #3a3a5a 0%, #1a1a2a 50%, #2a2a4a 100%);
            --glow-magenta: 0 0 10px #ff00ff, 0 0 20px #ff00ff40;
            --glow-cyan: 0 0 10px #00ffff, 0 0 20px #00ffff40;
            --glow-amber: 0 0 10px #ff6b00, 0 0 20px #ff6b0040;
            --scanline-opacity: 0.03;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'VT323', monospace;
            background: var(--bg-deep);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 1.5rem;
            padding-bottom: 3rem;
            font-size: 18px;
            line-height: 1.4;
            position: relative;
            overflow-x: hidden;
        }

        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                repeating-linear-gradient(
                    0deg,
                    transparent,
                    transparent 2px,
                    rgba(0, 255, 255, var(--scanline-opacity)) 2px,
                    rgba(0, 255, 255, var(--scanline-opacity)) 4px
                ),
                linear-gradient(180deg, #0a0a12 0%, #0f0f1a 50%, #0a0a12 100%);
            pointer-events: none;
            z-index: 1000;
        }

        body::after {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(ellipse at 50% 0%, rgba(255, 0, 255, 0.1) 0%, transparent 60%);
            pointer-events: none;
            z-index: -1;
        }

        .container {
            max-width: min(1600px, calc(100vw - 48px));
            margin: 0 auto;
            position: relative;
            z-index: 1001;
        }

        /* Two-column layout */
        .two-columns {
            display: grid;
            grid-template-columns: 65% 35%;
            gap: 32px;
            align-items: start;
        }

        .left-column {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
        }

        .right-column {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            position: sticky;
            top: 16px;
            max-height: calc(100vh - 80px);
            overflow-y: auto;
        }

        /* Job History Panel */
        .job-history-panel {
            min-height: 0;
            margin-bottom: 1.5rem;
        }

        .job-history-header {
            font-family: 'Orbitron', sans-serif;
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }

        .job-history-list {
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid var(--border);
            border-radius: 4px;
            background: var(--bg);
        }

        .job-history-empty {
            padding: 1rem;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.85rem;
        }

        .job-history-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.5rem 0.75rem;
            border-bottom: 1px solid var(--border);
            font-size: 0.8rem;
        }

        .job-history-item:last-child {
            border-bottom: none;
        }

        .job-history-id {
            font-family: monospace;
            color: var(--accent-cyan);
        }

        .job-history-status {
            padding: 0.15rem 0.5rem;
            border-radius: 3px;
            font-size: 0.7rem;
            text-transform: uppercase;
        }

        .job-history-status.running {
            background: rgba(59, 130, 246, 0.2);
            color: #3b82f6;
        }

        .job-history-status.completed {
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
        }

        .job-history-status.failed {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }

        .job-history-status.cancelled {
            background: rgba(245, 158, 11, 0.2);
            color: #f59e0b;
        }

        .job-history-converter {
            padding: 0.15rem 0.4rem;
            border-radius: 3px;
            font-size: 0.65rem;
            background: rgba(139, 92, 246, 0.15);
            color: #a78bfa;
            margin-left: 0.3rem;
        }

        .job-history-stop {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid #ef4444;
            color: #ef4444;
            padding: 0.15rem 0.5rem;
            border-radius: 3px;
            cursor: pointer;
            font-size: 0.7rem;
            text-transform: uppercase;
            transition: all 0.2s;
        }

        .job-history-stop:hover {
            background: #ef4444;
            color: white;
        }

        /* Wide layout reverts to single column below 1100px */
        @media (max-width: 1100px) {
            .two-columns { grid-template-columns: 1fr; }
            .right-column { position: static; max-height: none; overflow-y: visible; }
        }

        /* Responsive: stack on mobile */
        @media (max-width: 900px) {
            .two-columns {
                grid-template-columns: 1fr;
            }
        }

        h1 {
            font-family: 'Orbitron', sans-serif;
            font-weight: 900;
            font-size: 2.5rem;
            text-transform: uppercase;
            letter-spacing: 0.3em;
            margin-bottom: 1.5rem;
            background: linear-gradient(90deg, var(--accent-magenta), var(--accent-cyan));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-shadow: var(--glow-magenta);
            position: relative;
            display: inline-block;
        }

        h1::before {
            content: '//';
            color: var(--accent-cyan);
            margin-right: 0.5em;
            opacity: 0.7;
        }

        h1::after {
            content: 'DOCUMENTATION FLEET COMMAND';
            position: absolute;
            bottom: -1.5rem;
            left: 0;
            font-size: 0.5rem;
            letter-spacing: 0.5em;
            color: var(--text-dim);
            font-family: 'VT323', monospace;
            font-weight: normal;
        }

        /* Status Bar - Systems Diagnostics Panel */
        .status-bar {
            display: flex;
            gap: 0.5rem;
            padding: 0.75rem 1rem;
            background: var(--bg-panel);
            border: 1px solid #2a2a4a;
            border-radius: 4px;
            margin-bottom: 1.5rem;
            box-shadow: 
                inset 0 1px 0 rgba(255,255,255,0.05),
                0 0 20px rgba(0,0,0,0.5);
            flex-wrap: wrap;
        }

        .status-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.25rem 0.75rem;
            background: linear-gradient(180deg, #1a1a2a 0%, #0d0d18 100%);
            border: 1px solid #2a2a4a;
            border-radius: 2px;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--text-dim);
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.5);
        }

        .status-dot.ok { 
            background: var(--accent-green); 
            box-shadow: var(--glow-cyan), inset 0 1px 2px rgba(0,0,0,0.3);
            animation: blink-green 2s infinite;
        }

        .status-dot.warning { 
            background: var(--accent-amber); 
            box-shadow: var(--glow-amber);
            animation: blink-amber 1s infinite;
        }

        .status-dot.error { 
            background: #ff3366; 
            box-shadow: 0 0 10px #ff3366;
        }

        .status-dot.loading { 
            background: var(--accent-cyan); 
            box-shadow: var(--glow-cyan);
            animation: pulse 1s infinite;
        }

        @keyframes blink-green { 0%, 90%, 100% { opacity: 1; } 95% { opacity: 0.5; } }
        @keyframes blink-amber { 0%, 50%, 100% { opacity: 1; } 25%, 75% { opacity: 0.5; } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

        .status-label { 
            color: var(--accent-cyan); 
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }

        .status-value { 
            color: var(--text-primary); 
            font-size: 0.9rem;
        }

        /* Form Groups */
        .form-group { margin-bottom: 1rem; }

        label {
            display: block;
            margin-bottom: 0.4rem;
            color: var(--accent-cyan);
            font-size: 0.95rem;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            text-shadow: 0 0 5px rgba(0, 255, 255, 0.3);
        }

        label span {
            color: var(--text-dim);
            font-size: 0.8rem;
            text-transform: none;
            letter-spacing: 0;
        }

        input, select {
            width: 100%;
            padding: 0.7rem 1rem;
            background: var(--bg-input);
            border: 1px solid #2a2a4a;
            border-radius: 2px;
            color: var(--accent-green);
            font-family: 'VT323', monospace;
            font-size: 1.1rem;
            transition: all 0.2s;
            box-shadow: 
                inset 0 2px 4px rgba(0,0,0,0.3),
                0 0 0 1px transparent;
        }

        input:focus, select:focus {
            outline: none;
            border-color: var(--accent-magenta);
            box-shadow: 
                inset 0 2px 4px rgba(0,0,0,0.3),
                0 0 15px rgba(255, 0, 255, 0.3),
                inset 0 0 10px rgba(255, 0, 255, 0.1);
            color: var(--accent-magenta);
        }

        input::placeholder { color: #3a3a5a; }

        input[type="url"] {
            background: var(--bg-input);
            position: relative;
        }

        input[type="url"]::before {
            content: '>';
            position: absolute;
            left: 1rem;
            color: var(--accent-cyan);
        }

        .row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }

        @media (max-width: 600px) {
            .row { grid-template-columns: 1fr; }
        }

        /* Checkbox - Retro toggle */
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.5rem 0;
        }

        .checkbox-group input[type="checkbox"] {
            width: 20px;
            height: 20px;
            appearance: none;
            background: var(--bg-input);
            border: 2px solid #3a3a5a;
            border-radius: 2px;
            cursor: pointer;
            position: relative;
        }

        .checkbox-group input[type="checkbox"]:checked {
            background: var(--accent-magenta);
            border-color: var(--accent-magenta);
            box-shadow: var(--glow-magenta);
        }

        .checkbox-group input[type="checkbox"]:checked::after {
            content: '✓';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: var(--bg-deep);
            font-weight: bold;
            font-size: 14px;
        }

        .checkbox-group label {
            margin: 0;
            color: var(--text-primary);
            text-transform: none;
            letter-spacing: 0;
            cursor: pointer;
        }

        /* Models Section - Holographic Panel */
        .models-section {
            margin-bottom: 1rem;
            background: linear-gradient(180deg, #15152a 0%, #0d0d1a 100%);
            border: 1px solid #2a2a5a;
            border-radius: 4px;
            padding: 1rem;
            box-shadow: 
                0 0 30px rgba(0, 255, 255, 0.05),
                inset 0 1px 0 rgba(255, 255, 255, 0.05);
            position: relative;
            overflow: hidden;
        }

        .models-section::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent-cyan), transparent);
        }

        .section-label {
            display: block;
            color: var(--accent-magenta);
            font-family: 'Orbitron', sans-serif;
            font-size: 0.85rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.2em;
            margin-bottom: 0.75rem;
            text-shadow: var(--glow-magenta);
        }

        .model-row {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            margin-bottom: 0.75rem;
        }

        .model-row:last-child { margin-bottom: 0; }

        .model-select { flex: 1; min-width: 0; }

        .model-select label {
            font-size: 0.8rem;
            color: var(--accent-amber);
            margin-bottom: 0.25rem;
        }

        .model-hint {
            flex: 0 0 auto;
            max-width: 280px;
            display: flex;
            align-items: flex-start;
# ... truncated ...
```

---

## `requirements.txt`

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
playwright>=1.41.0
markdownify>=0.11.6
httpx>=0.26.0
pydantic>=2.5.0
sse-starlette>=1.8.0
beautifulsoup4>=4.12.0
defusedxml>=0.7.1
slowapi>=0.1.9
readability-lxml>=0.8.1
```

---

## `requirements-dev.txt`

```
-r requirements.txt
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
```

---

## `docker/Dockerfile`

```
# Docrawl Dockerfile
#
# 🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.

FROM python:3.12.9-slim-bookworm

WORKDIR /app

# Install system dependencies for Playwright (consolidated layer, no curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r docrawl && useradd -r -g docrawl -m -d /home/docrawl docrawl

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright system dependencies
RUN playwright install-deps chromium

# Copy application code
COPY src/ ./src/

# Create data directory and set permissions
RUN mkdir -p /data && chown -R docrawl:docrawl /data

# Switch to non-root user
USER docrawl

# Install Playwright browsers as docrawl user (installs to ~/.cache/ms-playwright)
RUN playwright install chromium

EXPOSE 8002

# Health check - verifies the API is responding (python urllib replaces curl dependency)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/api/health/ready')" || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002", "--timeout-graceful-shutdown", "5"]
```

---

## `docker-compose.yml`

```yaml
# Docrawl Docker Compose Configuration
#
# 🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free) and human review.

services:
  docrawl:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "127.0.0.1:8002:8002"
    volumes:
      - ./data:/data
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
       - OLLAMA_URL=http://host.docker.internal:11434
       - OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
       - OPENCODE_API_KEY=${OPENCODE_API_KEY:-}
       - API_KEY=${API_KEY:-}
       - CORS_ORIGINS=${CORS_ORIGINS:-}
       - MAX_CONCURRENT_JOBS=${MAX_CONCURRENT_JOBS:-5}
       - LMSTUDIO_URL=${LMSTUDIO_URL:-}
       - LMSTUDIO_API_KEY=${LMSTUDIO_API_KEY:-}
       - LLAMACPP_URL=${LLAMACPP_URL:-}
       - LLAMACPP_API_KEY=${LLAMACPP_API_KEY:-}
    restart: unless-stopped
    # Shared memory for Playwright - prevents crashes on large pages
    shm_size: '2gb'
    # Resource limits for stability
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
    # Health check configuration
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/api/health/ready"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  cloudflared:
    image: cloudflare/cloudflared:2024.12.2
    command: tunnel run
    environment:
      - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on:
      docrawl:
        condition: service_healthy
    restart: unless-stopped
```

---

## `pytest.ini`

```
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto

# Coverage settings
# Current threshold: 60% | Target: 65% (see docs/PROJECT_STATUS.md)
addopts =
    --verbose
    --color=yes
    --cov=src
    --cov-report=term-missing
    --cov-report=html
    --cov-branch
    --cov-fail-under=60
    -ra

# Markers for categorizing tests
markers =
    unit: Unit tests for individual functions
    integration: Integration tests for combined functionality
    slow: Tests that take longer to run
    asyncio: Tests that use async/await

# Ignore patterns
norecursedirs = .git .cache __pycache__ data docker
```

---

## `.env.example`

```
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Docrawl Environment Configuration
# 🤖 Generated with AI assistance by DocCrawler 🕷️ (model: qwen3-coder:free)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Copy this file to .env and fill in your values:
#   cp .env.example .env

# ─────────────────────────────────────────────────────────────────────────────
# OLLAMA CONFIGURATION (Local LLM)
# ─────────────────────────────────────────────────────────────────────────────
# URL where Ollama is running. Default works for most setups.
# Docker users: Use http://host.docker.internal:11434 (already set in compose)
# Remote Ollama: Use http://your-server-ip:11434
#
# Get Ollama: https://ollama.ai
# Pull models: ollama pull mistral:7b
OLLAMA_URL=http://localhost:11434

# ─────────────────────────────────────────────────────────────────────────────
# LM STUDIO CONFIGURATION (Local LLM — OpenAI-compatible)
# ─────────────────────────────────────────────────────────────────────────────
# URL where LM Studio server is running. Default works for most setups.
# API key is optional (LM Studio does not require one by default).
#
# Get LM Studio: https://lmstudio.ai
LMSTUDIO_URL=http://localhost:1234/v1
LMSTUDIO_API_KEY=

# ─────────────────────────────────────────────────────────────────────────────
# LLAMA.CPP SERVER (Local LLM — OpenAI-compatible)
# ─────────────────────────────────────────────────────────────────────────────
# URL where llama.cpp server is running. Default port is 8080.
# Start server: ./llama-server -m model.gguf --port 8080
# Models are referenced as "llamacpp/<alias>" where alias comes from --alias flag
# or defaults to the GGUF filename without extension.
#
# Get llama.cpp: https://github.com/ggml-org/llama.cpp/releases
LLAMACPP_URL=http://localhost:8080/v1
LLAMACPP_API_KEY=

# ─────────────────────────────────────────────────────────────────────────────
# OPENROUTER API (Cloud LLM Provider)
# ─────────────────────────────────────────────────────────────────────────────
# OpenRouter provides access to many LLM models via API.
# Free tier available with rate limits.
#
# Get your API key: https://openrouter.ai/keys
# Pricing: https://openrouter.ai/models (filter by :free for free models)
#
# Example free models:
#   - qwen/qwen3-coder:free
#   - meta-llama/llama-3.3-70b:free
#   - deepseek/deepseek-r1:free
OPENROUTER_API_KEY=

# ─────────────────────────────────────────────────────────────────────────────
# OPENCODE API (Alternative Cloud Provider)
# ─────────────────────────────────────────────────────────────────────────────
# OpenCode provides access to AI models via API.
#
# Get your API key: https://opencode.ai
OPENCODE_API_KEY=

# ─────────────────────────────────────────────────────────────────────────────
# CLOUDFLARE TUNNEL (Optional - Public Access)
# ─────────────────────────────────────────────────────────────────────────────
# Expose your local Docrawl instance to the internet securely.
# Requires setting up a Cloudflare Tunnel with Workers VPC.
#
# Get started: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/
# See docs/SETUP.md for detailed instructions.
CLOUDFLARE_TUNNEL_TOKEN=

# ─────────────────────────────────────────────────────────────────────────────
# SECURITY (v0.9.0+)
# ─────────────────────────────────────────────────────────────────────────────
# API key for all endpoints. If empty, auth is disabled (dev-local mode).
# In production, set a strong random value (e.g. openssl rand -hex 32).
# Clients must send: X-Api-Key: <value>
API_KEY=

# Comma-separated list of allowed CORS origins. If empty, only same-origin
# requests are allowed. Example: https://myapp.example.com,http://localhost:3000
CORS_ORIGINS=

# Maximum number of concurrent crawl jobs. Default: 5
MAX_CONCURRENT_JOBS=5

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING (Optional)
# ─────────────────────────────────────────────────────────────────────────────
# Set log level for debugging. Default: INFO
# Options: DEBUG, INFO, WARNING, ERROR
#LOG_LEVEL=DEBUG
```

