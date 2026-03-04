"""Unit tests for pipeline mode (src/jobs/runner.py) — PR 3.3."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.models import JobRequest
from src.jobs.manager import Job
from src.jobs.runner import ScrapedPage, _PIPELINE_SENTINEL, _run_pipeline_mode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(**overrides) -> JobRequest:
    """Minimal JobRequest that skips all non-Playwright fetch paths by default."""
    base: dict = {
        "url": "https://example.com",
        "crawl_model": "mistral:7b",
        "pipeline_model": "qwen3:14b",
        "reasoning_model": "deepseek-r1:32b",
        # Disable optional fetch paths so tests only exercise Playwright mock.
        "use_native_markdown": False,
        "use_markdown_proxy": False,
        "use_http_fast_path": False,
    }
    base.update(overrides)
    return JobRequest(**base)


def _make_job() -> Job:
    return Job(id="test-pipeline", request=_make_request())


class TestScrapedPage:
    """Tests for the ScrapedPage dataclass."""

    def test_can_be_constructed_with_all_fields(self):
        """ScrapedPage should accept all expected fields."""
        page = ScrapedPage(
            index=0,
            url="https://example.com/page",
            markdown="# Title\n\nContent.",
            raw_html="<h1>Title</h1><p>Content.</p>",
            native_token_count=42,
            fetch_method="playwright",
            load_time=1.23,
        )
        assert page.index == 0
        assert page.url == "https://example.com/page"
        assert page.markdown == "# Title\n\nContent."
        assert page.raw_html == "<h1>Title</h1><p>Content.</p>"
        assert page.native_token_count == 42
        assert page.fetch_method == "playwright"
        assert page.load_time == 1.23

    def test_raw_html_can_be_none(self):
        """raw_html is Optional — should accept None for non-Playwright paths."""
        page = ScrapedPage(
            index=1,
            url="https://example.com/fast",
            markdown="Fast content.",
            raw_html=None,
            native_token_count=None,
            fetch_method="http_fast",
            load_time=0.5,
        )
        assert page.raw_html is None
        assert page.native_token_count is None

    def test_fetch_method_reflects_path_used(self):
        """fetch_method field should store whichever fetch strategy was used."""
        for method in ("playwright", "http_fast", "proxy", "native", "cache"):
            page = ScrapedPage(
                index=0,
                url="u",
                markdown="m",
                raw_html=None,
                native_token_count=None,
                fetch_method=method,
                load_time=0.1,
            )
            assert page.fetch_method == method


class TestPipelineSentinel:
    """Tests for the pipeline SENTINEL value."""

    def test_sentinel_is_none(self):
        """_PIPELINE_SENTINEL must be None (falsy) so queue.get() can detect end."""
        assert _PIPELINE_SENTINEL is None

    def test_sentinel_identity_check(self):
        """Consumer loop uses `is _PIPELINE_SENTINEL` — must work with None."""
        item = None
        assert item is _PIPELINE_SENTINEL


# ---------------------------------------------------------------------------
# TestRunPipelineMode — integration tests that exercise the consumer paths
# ---------------------------------------------------------------------------


class TestRunPipelineMode:
    """Integration tests for _run_pipeline_mode producer/consumer pipeline.

    These tests mock scraper.get_html and LLM calls to cover the three
    consumer outcomes: markdown success, JSON success, and consumer exception.
    """

    async def test_markdown_success_appends_to_completed_urls(
        self, tmp_path: Path
    ) -> None:
        """Successful markdown page is written to disk and URL added to completed_urls."""
        job = _make_job()
        completed_urls: list[str] = []
        failed_urls: list[str] = []
        mock_converter = MagicMock()
        mock_converter.convert.return_value = "# mocked markdown"
        scraper = MagicMock()
        scraper.get_html = AsyncMock(return_value="<p>Hello pipeline.</p>")

        with patch("src.jobs.runner.needs_llm_cleanup", return_value=False):
            ok, partial, failed, *_ = await _run_pipeline_mode(
                job=job,
                urls=["https://example.com/page"],
                base_url="https://example.com",
                output_path=tmp_path,
                request=_make_request(),
                scraper=scraper,
                page_pool=None,
                page_cache=None,
                seen_hashes=set(),
                _hash_lock=asyncio.Lock(),
                converter=mock_converter,
                completed_urls=completed_urls,
                failed_urls=failed_urls,
                delay_s=0.0,
            )

        assert "https://example.com/page" in completed_urls
        assert failed_urls == []
        assert ok == 1
        assert failed == 0

    async def test_json_output_format_appends_to_completed_urls(
        self, tmp_path: Path
    ) -> None:
        """JSON output_format path saves a .json file and appends URL to completed_urls."""
        job = _make_job()
        completed_urls: list[str] = []
        failed_urls: list[str] = []
        mock_converter = MagicMock()
        mock_converter.convert.return_value = "# mocked markdown"
        scraper = MagicMock()
        scraper.get_html = AsyncMock(return_value="<p>Structured content.</p>")

        ok, partial, failed, *_ = await _run_pipeline_mode(
            job=job,
            urls=["https://example.com/doc"],
            base_url="https://example.com",
            output_path=tmp_path,
            request=_make_request(output_format="json"),
            scraper=scraper,
            page_pool=None,
            page_cache=None,
            seen_hashes=set(),
            _hash_lock=asyncio.Lock(),
            converter=mock_converter,
            completed_urls=completed_urls,
            failed_urls=failed_urls,
            delay_s=0.0,
        )

        assert "https://example.com/doc" in completed_urls
        assert failed_urls == []
        assert ok == 1

    async def test_consumer_exception_appends_to_failed_urls(
        self, tmp_path: Path
    ) -> None:
        """When consumer processing raises, the URL is appended to failed_urls."""
        job = _make_job()
        completed_urls: list[str] = []
        failed_urls: list[str] = []
        mock_converter = MagicMock()
        mock_converter.convert.return_value = "# mocked markdown"
        scraper = MagicMock()
        scraper.get_html = AsyncMock(return_value="<p>Will fail.</p>")

        with patch(
            "src.jobs.runner.chunk_markdown", side_effect=RuntimeError("chunk error")
        ):
            ok, partial, failed, *_ = await _run_pipeline_mode(
                job=job,
                urls=["https://example.com/fail"],
                base_url="https://example.com",
                output_path=tmp_path,
                request=_make_request(),
                scraper=scraper,
                page_pool=None,
                page_cache=None,
                seen_hashes=set(),
                _hash_lock=asyncio.Lock(),
                converter=mock_converter,
                completed_urls=completed_urls,
                failed_urls=failed_urls,
                delay_s=0.0,
            )

        assert "https://example.com/fail" in failed_urls
        assert completed_urls == []
        assert failed == 1
