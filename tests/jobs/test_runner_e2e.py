"""E2E smoke test for run_job() with a fully mocked HTTP+Playwright layer.

Exercises the complete happy path with no real network calls and no real Playwright.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import pytest

from src.api.models import JobRequest
from src.jobs.manager import Job
from src.jobs.runner import run_job


def _make_e2e_request(output_path: str = "/data/test-e2e") -> JobRequest:
    return JobRequest.model_construct(
        url="https://docs.example.com",
        pipeline_model="ollama/qwen3:14b",
        crawl_model="ollama/mistral:7b",
        reasoning_model=None,
        output_path=output_path,
        delay_ms=0,
        max_concurrent=1,
        max_depth=2,
        respect_robots_txt=False,
        use_native_markdown=False,
        use_markdown_proxy=False,
        use_http_fast_path=True,
        use_cache=False,
        output_format="markdown",
        use_pipeline_mode=False,
        converter=None,
        language="en",
        filter_sitemap_by_path=False,
        skip_llm_cleanup=False,
        content_selectors=None,
        noise_selectors=None,
        markdown_proxy_url=None,
    )


@pytest.mark.asyncio
async def test_run_job_happy_path_completes(tmp_path):
    """run_job() reaches 'completed' status with all external I/O mocked."""
    request = _make_e2e_request(output_path=str(tmp_path))
    job = Job(id="e2e-smoke-001", request=request)
    discovered_urls = ["https://docs.example.com/page1"]
    markdown_content = "# Page 1\n\n" + "Content sentence. " * 50

    # Mock PageScraper so start()/stop() don't attempt real Playwright
    mock_scraper = MagicMock()
    mock_scraper.start = AsyncMock()
    mock_scraper.stop = AsyncMock()
    mock_scraper.get_html = AsyncMock(return_value="<html>unused</html>")

    with (
        patch("src.jobs.runner.PageScraper", return_value=mock_scraper),
        patch("src.jobs.runner.discover_urls", new=AsyncMock(return_value=discovered_urls)),
        patch("src.jobs.runner.filter_urls", return_value=discovered_urls),
        patch("src.jobs.runner.filter_urls_with_llm", new=AsyncMock(return_value=discovered_urls)),
        patch("src.jobs.runner.validate_models", new=AsyncMock(return_value=[])),
        patch("src.jobs.runner.fetch_html_fast", new=AsyncMock(return_value=markdown_content)),
        patch("src.jobs.runner.fetch_markdown_native", new=AsyncMock(return_value=(None, None))),
        patch("src.jobs.runner.needs_llm_cleanup", return_value=False),
        patch("src.jobs.runner.cleanup_markdown", new=AsyncMock(return_value=markdown_content)),
        patch("src.jobs.runner.is_blocked_response", return_value=False),
        patch("src.jobs.runner.content_hash", return_value="unique-hash-001"),
        patch("src.jobs.runner.save_job_state"),
        patch("src.jobs.runner._generate_index"),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.write_text"),
        patch("pathlib.Path.rename"),
        patch("pathlib.Path.stat", return_value=MagicMock(st_size=1024)),
        patch("pathlib.Path.relative_to", return_value=MagicMock(__str__=lambda s: "page1.md")),
    ):
        await run_job(job, page_pool=None)

    assert job.status == "completed"


@pytest.mark.asyncio
async def test_run_job_cancelled_mid_run(tmp_path):
    """run_job() respects cancellation signal and sets status to 'cancelled'."""
    request = _make_e2e_request(output_path=str(tmp_path))
    job = Job(id="e2e-cancel-001", request=request)

    async def _cancel_then_return(*a, **kw):
        job.cancel()
        return ["https://docs.example.com/page1"]

    # Mock PageScraper so start()/stop() don't attempt real Playwright
    mock_scraper = MagicMock()
    mock_scraper.start = AsyncMock()
    mock_scraper.stop = AsyncMock()

    with (
        patch("src.jobs.runner.PageScraper", return_value=mock_scraper),
        patch("src.jobs.runner.discover_urls", new=AsyncMock(side_effect=_cancel_then_return)),
        patch("src.jobs.runner.validate_models", new=AsyncMock(return_value=[])),
        patch("src.jobs.runner.save_job_state"),
        patch("pathlib.Path.mkdir"),
    ):
        await run_job(job, page_pool=None)

    assert job.status == "cancelled"
