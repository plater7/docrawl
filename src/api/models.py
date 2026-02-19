"""Pydantic models for API request/response."""

from pydantic import BaseModel, HttpUrl


class JobRequest(BaseModel):
    """Request to create a new crawl job."""
    url: HttpUrl
    crawl_model: str
    pipeline_model: str
    reasoning_model: str
    output_path: str = "/data/output"
    delay_ms: int = 500
    max_concurrent: int = 3
    max_depth: int = 5
    respect_robots_txt: bool = True
    use_native_markdown: bool = True
    use_markdown_proxy: bool = False
    markdown_proxy_url: str = "https://markdown.new"
    language: str = "en"


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
