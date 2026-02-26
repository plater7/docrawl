"""Pydantic models for API request/response."""

from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, HttpUrl, Field, field_validator

from src.utils.security import validate_url_not_ssrf


class JobRequest(BaseModel):
    """Request to create a new crawl job."""

    url: HttpUrl
    crawl_model: str = Field(pattern=r"^[\w./:@-]{1,100}$")
    pipeline_model: str = Field(pattern=r"^[\w./:@-]{1,100}$")
    reasoning_model: str = Field(pattern=r"^[\w./:@-]{1,100}$")
    output_path: str = Field(default="/data/output")
    delay_ms: int = Field(default=500, ge=100, le=60000)
    max_concurrent: int = Field(default=3, ge=1, le=10)
    max_depth: int = Field(default=5, ge=1, le=20)
    respect_robots_txt: bool = True
    use_native_markdown: bool = True
    use_markdown_proxy: bool = False
    markdown_proxy_url: str | None = Field(default=None)
    language: str = Field(default="en", max_length=10)
    filter_sitemap_by_path: bool = True

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
