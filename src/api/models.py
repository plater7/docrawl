"""Pydantic models for API request/response."""

import socket
import ipaddress
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, HttpUrl, Field, field_validator


# Private/reserved network ranges to block for SSRF prevention
_PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _block_private_host(hostname: str | None) -> None:
    """Raise ValueError if hostname resolves to a private/internal address."""
    if not hostname:
        raise ValueError("URL has no hostname")
    try:
        addr = ipaddress.ip_address(socket.gethostbyname(hostname))
        if any(addr in net for net in _PRIVATE_NETS):
            raise ValueError(f"URL targets private/internal address: {hostname}")
    except socket.gaierror:
        pass  # DNS doesn't resolve — let it fail naturally later


class JobRequest(BaseModel):
    """Request to create a new crawl job."""

    url: HttpUrl
    crawl_model: str = Field(pattern=r'^[\w./:@-]{1,100}$')
    pipeline_model: str = Field(pattern=r'^[\w./:@-]{1,100}$')
    reasoning_model: str = Field(pattern=r'^[\w./:@-]{1,100}$')
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

    @field_validator('output_path')
    @classmethod
    def validate_output_path(cls, v: str) -> str:
        """Prevent path traversal — closes CONS-001 / issue #47."""
        resolved = Path('/data').joinpath(v.lstrip('/')).resolve()
        if not str(resolved).startswith('/data'):
            raise ValueError('output_path must be under /data')
        return str(resolved)

    @field_validator('markdown_proxy_url', mode='before')
    @classmethod
    def validate_proxy_url(cls, v: object) -> object:
        """Prevent SSRF via markdown proxy URL — closes CONS-019 / issue #65."""
        if v is None or v == "":
            return None
        parsed = urlparse(str(v))
        if parsed.scheme != 'https':
            raise ValueError('markdown_proxy_url must use HTTPS')
        _block_private_host(parsed.hostname)
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
