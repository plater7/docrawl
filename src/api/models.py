"""Pydantic models for API request/response."""

from pydantic import BaseModel, HttpUrl


class JobRequest(BaseModel):
    """Request to create a new crawl job."""
    url: HttpUrl
    crawl_model: str          # Para discovery y filtrado de URLs
    pipeline_model: str       # Para cleanup de markdown chunks
    reasoning_model: str      # Para análisis de estructura y decisiones complejas
    output_path: str = "/data/output"
    delay_ms: int = 500
    max_concurrent: int = 3
    max_depth: int = 5
    respect_robots_txt: bool = True


class JobStatus(BaseModel):
    """Current status of a job."""
    id: str
    status: str
    pages_completed: int = 0
    pages_total: int = 0
    current_url: str | None = None


class OllamaModel(BaseModel):
    """Ollama model info."""
    name: str
    size: int | None = None
