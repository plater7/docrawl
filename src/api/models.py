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


class OllamaModel(BaseModel):
    """LLM model info."""

    name: str
    size: int | None = None
    provider: str = "ollama"
    is_free: bool = True
