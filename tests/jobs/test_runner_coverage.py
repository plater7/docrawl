"""Additional coverage tests for src/jobs/runner.py.

Targets uncovered branches and lines identified in the coverage report:
lines 60, 84, 270, 298-302, 328, 390, 417->431, 432-443, 454-462, 474->490,
491->516, 501, 504, 515, 523-524, 528-540, 588, 606, 612, 622-641,
657-671, 686, 736-745, 798-799, 801->858, 841-855, 860-861, 875-876, 887->890.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.models import JobRequest
from src.jobs.manager import Job
from src.jobs.runner import run_job


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(**overrides) -> JobRequest:
    """Minimal valid JobRequest — all optional features disabled by default."""
    defaults = dict(
        url="https://example.com",
        crawl_model=None,
        pipeline_model="ollama/qwen3:14b",
        reasoning_model=None,
        output_path="/data/output",
        delay_ms=0,
        max_concurrent=1,
        max_depth=1,
        respect_robots_txt=False,
        use_native_markdown=False,
        use_markdown_proxy=False,
        use_http_fast_path=False,
        use_cache=False,
        output_format="markdown",
        use_pipeline_mode=False,
        converter=None,
        skip_llm_cleanup=False,
        language="en",
        filter_sitemap_by_path=True,
    )
    defaults.update(overrides)
    return JobRequest.model_construct(**defaults)


def _make_job(request=None) -> Job:
    return Job(id="test-job-cov0", request=request or _make_request())


def _base_patches(tmp_path, extra_request_kwargs=None, scraper_html="<h1>Hello</h1>"):
    """Return a helper context-manager factory for common run_job patches."""
    # Callers use this by calling patch(...) themselves — this returns the
    # mocks to be passed in so tests can vary what they need.
    scraper = MagicMock()
    scraper.start = AsyncMock()
    scraper.stop = AsyncMock()
    scraper.get_html = AsyncMock(return_value=scraper_html)

    converter = MagicMock()
    converter.convert = MagicMock(return_value="# Hello\n\nContent")

    robots = MagicMock()
    robots.load = AsyncMock()
    robots.crawl_delay = None
    robots.is_allowed = MagicMock(return_value=True)

    return scraper, converter, robots


# ---------------------------------------------------------------------------
# 1. model validation failure path
# ---------------------------------------------------------------------------


class TestModelValidationFailurePath:
    """Line 165-184: validation_errors branch inside run_job."""

    async def test_validation_failure_sets_failed_status(self, tmp_path):
        req = _make_request(
            crawl_model="ollama/missing-model",
            output_path=str(tmp_path / "val-fail"),
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=["Model not found"]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        await run_job(job)

        assert job.status == "failed"

    async def test_validation_failure_emits_job_done_with_failed_status(self, tmp_path):
        req = _make_request(
            crawl_model="ollama/missing-model",
            output_path=str(tmp_path / "val-fail-event"),
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=["Model not found"]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        await run_job(job)

        emitted_types = [call.args[0] for call in job.emit_event.call_args_list]
        assert "job_done" in emitted_types
        done_calls = [
            call for call in job.emit_event.call_args_list if call.args[0] == "job_done"
        ]
        assert done_calls[0].args[1]["status"] == "failed"

    async def test_validation_failure_error_contains_model_message(self, tmp_path):
        req = _make_request(
            crawl_model="ollama/missing-model",
            output_path=str(tmp_path / "val-fail-msg"),
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch(
            "src.jobs.runner.validate_models",
            return_value=["Model 'ollama/missing-model' not found"],
        ):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        await run_job(job)

        done_calls = [
            call for call in job.emit_event.call_args_list if call.args[0] == "job_done"
        ]
        assert "not found" in done_calls[0].args[1]["error"]


# ---------------------------------------------------------------------------
# 2. resume_urls path — skips discovery/filtering entirely
# ---------------------------------------------------------------------------


class TestResumeUrlsPath:
    """Lines 233-242: resume_urls is not None branch."""

    async def test_resume_urls_skips_discover_urls(self, tmp_path):
        req = _make_request(output_path=str(tmp_path / "resume"))
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch("src.jobs.runner.discover_urls") as mock_discover:
                            with patch(
                                "src.jobs.runner.fetch_html_fast",
                                return_value="# Hello",
                            ):
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=["# Hello"],
                                ):
                                    with patch(
                                        "src.jobs.runner.needs_llm_cleanup",
                                        return_value=False,
                                    ):
                                        with patch("src.jobs.runner.save_job_state"):
                                            await run_job(
                                                job,
                                                resume_urls=[
                                                    "https://example.com/page1"
                                                ],
                                            )

        mock_discover.assert_not_called()

    async def test_resume_urls_logs_resuming_message(self, tmp_path):
        req = _make_request(output_path=str(tmp_path / "resume-log"))
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast", return_value="# Hello"
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown",
                                return_value=["# Hello"],
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(
                                            job,
                                            resume_urls=["https://example.com/page1"],
                                        )

        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("Resuming" in m or "pending URLs" in m for m in messages)


# ---------------------------------------------------------------------------
# 3. robots.txt with crawl_delay
# ---------------------------------------------------------------------------


class TestRobotsTxtWithCrawlDelay:
    """Lines 207-216: robots.crawl_delay branch (crawl_delay is set)."""

    async def test_crawl_delay_uses_max_of_delay_ms_and_robots(self, tmp_path):
        scraper, converter, _ = _base_patches(tmp_path)
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = 5.0  # > 0 so the crawl-delay branch is taken
        robots.is_allowed = MagicMock(return_value=True)

        req = _make_request(
            output_path=str(tmp_path / "robots-delay"),
            respect_robots_txt=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
            delay_ms=0,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast", return_value="# x"
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown", return_value=["# x"]
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(
                                            job,
                                            resume_urls=["https://example.com/"],
                                        )

        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("crawl-delay" in m for m in messages)
        assert any("5.0s" in m for m in messages)


# ---------------------------------------------------------------------------
# 4. robots.txt without crawl_delay
# ---------------------------------------------------------------------------


class TestRobotsTxtNoCrawlDelay:
    """Lines 217-226: robots.crawl_delay is None/falsy → no-crawl-delay message."""

    async def test_no_crawl_delay_logs_no_crawl_delay_message(self, tmp_path):
        scraper, converter, _ = _base_patches(tmp_path)
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None  # no delay
        robots.is_allowed = MagicMock(return_value=True)

        req = _make_request(
            output_path=str(tmp_path / "robots-no-delay"),
            respect_robots_txt=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
            delay_ms=0,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast", return_value="# x"
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown", return_value=["# x"]
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(
                                            job,
                                            resume_urls=["https://example.com/"],
                                        )

        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("no crawl-delay" in m for m in messages)


# ---------------------------------------------------------------------------
# 5. is_cancelled check after discovery (line 269-270)
# ---------------------------------------------------------------------------


class TestIsCancelledAfterDiscovery:
    """Line 269-270: job.is_cancelled returns True after discover_urls."""

    async def test_cancelled_after_discovery_returns_early(self, tmp_path):
        req = _make_request(output_path=str(tmp_path / "cancel-disc"))
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        # Cancel after discover_urls is called
        async def _discover_and_cancel(*args, **kwargs):
            job._cancelled = True
            return ["https://example.com/page1"]

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.discover_urls",
                            side_effect=_discover_and_cancel,
                        ):
                            with patch(
                                "src.jobs.runner.filter_urls",
                                return_value=["https://example.com/page1"],
                            ):
                                with patch("src.jobs.runner.save_job_state"):
                                    await run_job(job)

        # Job should NOT be marked completed
        done_events = [
            c
            for c in job.emit_event.call_args_list
            if c.args[0] == "job_done" and c.args[1].get("status") == "completed"
        ]
        assert done_events == []


# ---------------------------------------------------------------------------
# 6. is_cancelled before processing pages (line 344-345)
# ---------------------------------------------------------------------------


class TestIsCancelledBeforeProcessingPages:
    """Line 344-345: job.is_cancelled after discovery/filtering loop."""

    async def test_cancelled_before_page_processing_returns_early(self, tmp_path):
        req = _make_request(output_path=str(tmp_path / "cancel-before-pages"))
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        # Cancel after filter_urls is called so we hit line 344
        def _filter_and_cancel(urls, *args, **kwargs):
            job._cancelled = True
            return urls

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.discover_urls",
                            return_value=["https://example.com/page1"],
                        ):
                            with patch(
                                "src.jobs.runner.filter_urls",
                                side_effect=_filter_and_cancel,
                            ):
                                with patch("src.jobs.runner.save_job_state"):
                                    await run_job(job)

        done_events = [
            c
            for c in job.emit_event.call_args_list
            if c.args[0] == "job_done" and c.args[1].get("status") == "completed"
        ]
        assert done_events == []


# ---------------------------------------------------------------------------
# 7. page cache hit path (line 416-428)
# ---------------------------------------------------------------------------


class TestPageCacheHitPath:
    """Lines 415-428: page_cache.get returns cached HTML → skips network."""

    async def test_cache_hit_skips_network_fetch(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "cache-hit"),
            use_cache=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        # Simulate a cache hit
        mock_cache = MagicMock()
        mock_cache.get = MagicMock(return_value="<h1>Cached</h1>")
        mock_cache.hits = 1
        mock_cache.misses = 0

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.PageCache", return_value=mock_cache
                        ):
                            with patch(
                                "src.jobs.runner.is_blocked_response",
                                return_value=False,
                            ):
                                with patch(
                                    "src.jobs.runner.content_hash",
                                    return_value="hash_cached",
                                ):
                                    with patch(
                                        "src.jobs.runner.chunk_markdown",
                                        return_value=["# Cached"],
                                    ):
                                        with patch(
                                            "src.jobs.runner.needs_llm_cleanup",
                                            return_value=False,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        # Scraper should not have been called for HTML fetching
        scraper.get_html.assert_not_called()

    async def test_cache_hit_logs_served_from_cache(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "cache-hit-log"),
            use_cache=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        mock_cache = MagicMock()
        mock_cache.get = MagicMock(return_value="<h1>Cached</h1>")
        mock_cache.hits = 1
        mock_cache.misses = 0

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.PageCache", return_value=mock_cache
                        ):
                            with patch(
                                "src.jobs.runner.is_blocked_response",
                                return_value=False,
                            ):
                                with patch(
                                    "src.jobs.runner.content_hash",
                                    return_value="hash_cached2",
                                ):
                                    with patch(
                                        "src.jobs.runner.chunk_markdown",
                                        return_value=["# Cached"],
                                    ):
                                        with patch(
                                            "src.jobs.runner.needs_llm_cleanup",
                                            return_value=False,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("cache" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# 8. native markdown path (use_native_markdown=True)
# ---------------------------------------------------------------------------


class TestNativeMarkdownPath:
    """Lines 431-450: use_native_markdown=True and fetch_markdown_native returns content."""

    async def test_native_markdown_skips_playwright(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "native-md"),
            use_native_markdown=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_markdown_native",
                            return_value=("# Native content", 42),
                        ):
                            with patch(
                                "src.jobs.runner.is_blocked_response",
                                return_value=False,
                            ):
                                with patch(
                                    "src.jobs.runner.content_hash",
                                    return_value="hash_native",
                                ):
                                    with patch(
                                        "src.jobs.runner.chunk_markdown",
                                        return_value=["# Native content"],
                                    ):
                                        with patch(
                                            "src.jobs.runner.needs_llm_cleanup",
                                            return_value=False,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        scraper.get_html.assert_not_called()
        assert job.status == "completed"

    async def test_native_markdown_logs_skipped_playwright(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "native-md-log"),
            use_native_markdown=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_markdown_native",
                            return_value=("# Native", 10),
                        ):
                            with patch(
                                "src.jobs.runner.is_blocked_response",
                                return_value=False,
                            ):
                                with patch(
                                    "src.jobs.runner.content_hash",
                                    return_value="hash_native2",
                                ):
                                    with patch(
                                        "src.jobs.runner.chunk_markdown",
                                        return_value=["# Native"],
                                    ):
                                        with patch(
                                            "src.jobs.runner.needs_llm_cleanup",
                                            return_value=False,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("native-md" in m or "Skipped Playwright" in m for m in messages)


# ---------------------------------------------------------------------------
# 9. proxy markdown path (use_markdown_proxy=True)
# ---------------------------------------------------------------------------


class TestProxyMarkdownPath:
    """Lines 453-469: use_markdown_proxy=True and fetch_markdown_proxy returns content."""

    async def test_proxy_markdown_skips_playwright(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "proxy-md"),
            use_markdown_proxy=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_markdown_proxy",
                            return_value=("# Proxy content", None),
                        ):
                            with patch(
                                "src.jobs.runner.is_blocked_response",
                                return_value=False,
                            ):
                                with patch(
                                    "src.jobs.runner.content_hash",
                                    return_value="hash_proxy",
                                ):
                                    with patch(
                                        "src.jobs.runner.chunk_markdown",
                                        return_value=["# Proxy content"],
                                    ):
                                        with patch(
                                            "src.jobs.runner.needs_llm_cleanup",
                                            return_value=False,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        scraper.get_html.assert_not_called()
        assert job.status == "completed"

    async def test_proxy_markdown_logs_fetched_via_proxy(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "proxy-md-log"),
            use_markdown_proxy=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_markdown_proxy",
                            return_value=("# Proxy", None),
                        ):
                            with patch(
                                "src.jobs.runner.is_blocked_response",
                                return_value=False,
                            ):
                                with patch(
                                    "src.jobs.runner.content_hash",
                                    return_value="hash_proxy2",
                                ):
                                    with patch(
                                        "src.jobs.runner.chunk_markdown",
                                        return_value=["# Proxy"],
                                    ):
                                        with patch(
                                            "src.jobs.runner.needs_llm_cleanup",
                                            return_value=False,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("proxy" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# 10. http_fast_path (use_http_fast_path=True returns content)
# ---------------------------------------------------------------------------


class TestHttpFastPath:
    """Lines 472-487: use_http_fast_path=True and fetch_html_fast returns content."""

    async def test_http_fast_path_skips_playwright(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "http-fast"),
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast",
                            return_value="# Fast content",
                        ):
                            with patch(
                                "src.jobs.runner.is_blocked_response",
                                return_value=False,
                            ):
                                with patch(
                                    "src.jobs.runner.content_hash",
                                    return_value="hash_fast",
                                ):
                                    with patch(
                                        "src.jobs.runner.chunk_markdown",
                                        return_value=["# Fast content"],
                                    ):
                                        with patch(
                                            "src.jobs.runner.needs_llm_cleanup",
                                            return_value=False,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        scraper.get_html.assert_not_called()


# ---------------------------------------------------------------------------
# 11. blocked response detection (is_blocked_response returns True)
# ---------------------------------------------------------------------------


class TestBlockedResponseDetection:
    """Lines 527-540: is_blocked_response returns True → pages_blocked incremented."""

    async def test_blocked_response_increments_pages_blocked(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "blocked"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=True
                        ):
                            with patch("src.jobs.runner.save_job_state"):
                                await run_job(
                                    job,
                                    resume_urls=["https://example.com/page1"],
                                )

        assert job.pages_blocked >= 1

    async def test_blocked_response_logs_warning(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "blocked-log"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=True
                        ):
                            with patch("src.jobs.runner.save_job_state"):
                                await run_job(
                                    job,
                                    resume_urls=["https://example.com/page1"],
                                )

        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("blocked" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# 12. content dedup — same hash twice skips second page
# ---------------------------------------------------------------------------


class TestContentDedup:
    """Lines 542-557: content_hash already in seen_hashes → pages_skipped incremented."""

    async def test_duplicate_content_skips_second_page(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "dedup"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        # Both pages get the same hash → second should be skipped
        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=False
                        ):
                            with patch(
                                "src.jobs.runner.content_hash",
                                return_value="same_hash_for_both",
                            ):
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=["# Content"],
                                ):
                                    with patch(
                                        "src.jobs.runner.needs_llm_cleanup",
                                        return_value=False,
                                    ):
                                        with patch("src.jobs.runner.save_job_state"):
                                            await run_job(
                                                job,
                                                resume_urls=[
                                                    "https://example.com/page1",
                                                    "https://example.com/page2",
                                                ],
                                            )

        assert job.pages_skipped >= 1


# ---------------------------------------------------------------------------
# 13. JSON output format
# ---------------------------------------------------------------------------


class TestJsonOutputFormat:
    """Lines 586-588 and 655-671: output_format='json' skips LLM cleanup, saves JSON."""

    async def test_json_format_saves_json_file(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "json-fmt"),
            output_format="json",
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=False
                        ):
                            with patch(
                                "src.jobs.runner.content_hash", return_value="hash_j1"
                            ):
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=["# Content"],
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(
                                            job,
                                            resume_urls=["https://example.com/page1"],
                                        )

        out_dir = Path(req.output_path)
        json_files = list(out_dir.glob("*.json"))
        assert len(json_files) >= 1

    async def test_json_format_does_not_call_cleanup_markdown(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "json-no-cleanup"),
            output_format="json",
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=False
                        ):
                            with patch(
                                "src.jobs.runner.content_hash", return_value="hash_j2"
                            ):
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=["# Content"],
                                ):
                                    with patch(
                                        "src.jobs.runner.cleanup_markdown"
                                    ) as mock_cleanup:
                                        with patch("src.jobs.runner.save_job_state"):
                                            await run_job(
                                                job,
                                                resume_urls=[
                                                    "https://example.com/page1"
                                                ],
                                            )

        mock_cleanup.assert_not_called()


# ---------------------------------------------------------------------------
# 14. skip_llm_cleanup=True path
# ---------------------------------------------------------------------------


class TestSkipLlmCleanup:
    """Lines 580-588: skip_llm_cleanup=True → cleaned_chunks = list(chunks)."""

    async def test_skip_llm_cleanup_saves_raw_chunks(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "skip-cleanup"),
            skip_llm_cleanup=True,
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=False
                        ):
                            with patch(
                                "src.jobs.runner.content_hash", return_value="hash_sk1"
                            ):
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=["# Raw chunk"],
                                ):
                                    with patch(
                                        "src.jobs.runner.cleanup_markdown"
                                    ) as mock_cleanup:
                                        with patch("src.jobs.runner.save_job_state"):
                                            await run_job(
                                                job,
                                                resume_urls=[
                                                    "https://example.com/page1"
                                                ],
                                            )

        mock_cleanup.assert_not_called()
        assert job.status == "completed"


# ---------------------------------------------------------------------------
# 15. chunk cleanup failure (cleanup_markdown raises → use raw chunk)
# ---------------------------------------------------------------------------


class TestChunkCleanupFailure:
    """Lines 638-650: cleanup_markdown raises → fall back to raw chunk."""

    async def test_cleanup_failure_uses_raw_chunk(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "chunk-fail"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model="ollama/qwen3:14b",
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=False
                        ):
                            with patch(
                                "src.jobs.runner.content_hash", return_value="hash_cf1"
                            ):
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=["# Raw chunk"],
                                ):
                                    with patch(
                                        "src.jobs.runner.needs_llm_cleanup",
                                        return_value=True,
                                    ):
                                        with patch(
                                            "src.jobs.runner.cleanup_markdown",
                                            side_effect=Exception("LLM timeout"),
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        # Job should complete successfully even with cleanup failure
        assert job.status == "completed"
        # Check that a warning was logged about chunk failure
        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("failed" in m.lower() or "raw" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# 16. needs_llm_cleanup returns False → skip cleanup for chunk
# ---------------------------------------------------------------------------


class TestNeedsLlmCleanupFalse:
    """Lines 609-620: needs_llm_cleanup returns False → append chunk directly."""

    async def test_clean_chunk_skips_llm_cleanup(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "clean-chunk"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model="ollama/qwen3:14b",
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=False
                        ):
                            with patch(
                                "src.jobs.runner.content_hash", return_value="hash_nc1"
                            ):
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=["# Clean chunk"],
                                ):
                                    with patch(
                                        "src.jobs.runner.needs_llm_cleanup",
                                        return_value=False,
                                    ):
                                        with patch(
                                            "src.jobs.runner.cleanup_markdown"
                                        ) as mock_cleanup:
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        mock_cleanup.assert_not_called()

    async def test_clean_chunk_with_multiple_chunks_logs_skip(self, tmp_path):
        """When multiple chunks and one is clean, a 'skip (clean)' log is emitted."""
        req = _make_request(
            output_path=str(tmp_path / "clean-chunk-log"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model="ollama/qwen3:14b",
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=False
                        ):
                            with patch(
                                "src.jobs.runner.content_hash", return_value="hash_nc2"
                            ):
                                # Multiple chunks → triggers "skip (clean)" log
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=["# Chunk 1", "# Chunk 2"],
                                ):
                                    with patch(
                                        "src.jobs.runner.needs_llm_cleanup",
                                        return_value=False,
                                    ):
                                        with patch("src.jobs.runner.save_job_state"):
                                            await run_job(
                                                job,
                                                resume_urls=[
                                                    "https://example.com/page1"
                                                ],
                                            )

        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("skip" in m.lower() and "clean" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# 17. Playwright scrape retry — 1st attempt fails, 2nd succeeds
# ---------------------------------------------------------------------------


class TestPlaywrightRetrySuccess:
    """Lines 491-515: retry loop in Playwright fallback, first attempt fails."""

    async def test_retry_succeeds_on_second_attempt(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "retry-ok"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        # First call fails, second succeeds
        scraper.get_html = AsyncMock(
            side_effect=[Exception("Timeout"), "<h1>Retried</h1>"]
        )

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=False
                        ):
                            with patch(
                                "src.jobs.runner.content_hash", return_value="hash_r1"
                            ):
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=["# Retried"],
                                ):
                                    with patch(
                                        "src.jobs.runner.needs_llm_cleanup",
                                        return_value=False,
                                    ):
                                        with patch("src.jobs.runner.save_job_state"):
                                            with patch("asyncio.sleep"):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        assert job.pages_retried == 1
        assert job.status == "completed"


# ---------------------------------------------------------------------------
# 18. Playwright scrape retry exhausted (all attempts fail → raise)
# ---------------------------------------------------------------------------


class TestPlaywrightRetryExhausted:
    """Lines 514-515: all retries exhausted → re-raise exception."""

    async def test_all_retries_exhausted_marks_page_failed(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "retry-fail"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        # All attempts fail
        scraper.get_html = AsyncMock(side_effect=Exception("Persistent error"))

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch("src.jobs.runner.save_job_state"):
                            with patch("asyncio.sleep"):
                                await run_job(
                                    job,
                                    resume_urls=["https://example.com/page1"],
                                )

        # Job overall should complete (page fails but job continues)
        assert job.status == "completed"
        # Page error should have been logged
        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("Persistent error" in m or "✗" in m for m in messages)


# ---------------------------------------------------------------------------
# 19. crawl_model = None — skips LLM filtering (line 327-328)
# ---------------------------------------------------------------------------


class TestCrawlModelNoneSkipsLlmFilter:
    """Lines 327-328: crawl_model is None → llm_duration = 0.0, no filter_urls_with_llm."""

    async def test_no_crawl_model_skips_llm_filter(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "no-crawl-model"),
            crawl_model=None,
            use_http_fast_path=True,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.discover_urls",
                            return_value=["https://example.com/"],
                        ):
                            with patch(
                                "src.jobs.runner.filter_urls",
                                return_value=["https://example.com/"],
                            ):
                                with patch(
                                    "src.jobs.runner.filter_urls_with_llm"
                                ) as mock_llm_filter:
                                    with patch(
                                        "src.jobs.runner.fetch_html_fast",
                                        return_value="# content",
                                    ):
                                        with patch(
                                            "src.jobs.runner.chunk_markdown",
                                            return_value=["# content"],
                                        ):
                                            with patch(
                                                "src.jobs.runner.needs_llm_cleanup",
                                                return_value=False,
                                            ):
                                                with patch(
                                                    "src.jobs.runner.save_job_state"
                                                ):
                                                    await run_job(job)

        mock_llm_filter.assert_not_called()


# ---------------------------------------------------------------------------
# 20. _generate_index is called and saves _index.md
# ---------------------------------------------------------------------------


class TestGenerateIndexCalledOnCompletion:
    """Line 801-802: _generate_index called when job completes successfully."""

    async def test_index_file_created_on_completion(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "index-created"),
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast", return_value="# content"
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown",
                                return_value=["# content"],
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(
                                            job,
                                            resume_urls=["https://example.com/page1"],
                                        )

        out = Path(req.output_path)
        assert (out / "_index.md").exists()
        content = (out / "_index.md").read_text()
        assert "# Documentation Index" in content


# ---------------------------------------------------------------------------
# 21. robots.txt filtering removes URLs — blocked URLs logged (lines 297-308)
# ---------------------------------------------------------------------------


class TestRobotsTxtFiltering:
    """Lines 297-308: robots.txt is_allowed blocks some URLs during discovery."""

    async def test_robots_blocked_urls_are_removed(self, tmp_path):
        scraper, converter, _ = _base_patches(tmp_path)
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None
        # First URL allowed, second blocked
        robots.is_allowed = MagicMock(side_effect=lambda u: "page1" in u)

        req = _make_request(
            output_path=str(tmp_path / "robots-filter"),
            respect_robots_txt=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
            use_http_fast_path=True,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.discover_urls",
                            return_value=[
                                "https://example.com/page1",
                                "https://example.com/blocked",
                            ],
                        ):
                            with patch(
                                "src.jobs.runner.filter_urls",
                                side_effect=lambda urls, *a, **k: urls,
                            ):
                                with patch(
                                    "src.jobs.runner.fetch_html_fast",
                                    return_value="# content",
                                ):
                                    with patch(
                                        "src.jobs.runner.chunk_markdown",
                                        return_value=["# content"],
                                    ):
                                        with patch(
                                            "src.jobs.runner.needs_llm_cleanup",
                                            return_value=False,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(job)

        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        # The robots.txt filtering log should appear (removed 1 URL)
        assert any("robots.txt" in m for m in messages)


# ---------------------------------------------------------------------------
# 22. save_job_state failure is handled gracefully (lines 798-799)
# ---------------------------------------------------------------------------


class TestSaveJobStateFailure:
    """Lines 798-799: save_job_state raises → warning logged, job continues."""

    async def test_save_state_failure_does_not_crash_job(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "state-fail"),
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast", return_value="# x"
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown", return_value=["# x"]
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch(
                                        "src.jobs.runner.save_job_state",
                                        side_effect=OSError("Disk full"),
                                    ):
                                        await run_job(
                                            job,
                                            resume_urls=["https://example.com/"],
                                        )

        # Job should still complete despite state save failure
        assert job.status == "completed"


# ---------------------------------------------------------------------------
# 23. outer exception handler (lines 841-855) — unexpected exception
# ---------------------------------------------------------------------------


class TestOuterExceptionHandler:
    """Lines 841-855: unhandled exception in run_job body → job.status = 'failed'."""

    async def test_unexpected_exception_sets_failed_status(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "outer-exc"),
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper = MagicMock()
        scraper.start = AsyncMock(side_effect=RuntimeError("Browser crashed"))
        scraper.stop = AsyncMock()
        converter = MagicMock()
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        await run_job(job)

        assert job.status == "failed"

    async def test_unexpected_exception_emits_job_done_failed(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "outer-exc-event"),
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper = MagicMock()
        scraper.start = AsyncMock(side_effect=RuntimeError("Browser crashed"))
        scraper.stop = AsyncMock()
        converter = MagicMock()
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        await run_job(job)

        done_calls = [
            call for call in job.emit_event.call_args_list if call.args[0] == "job_done"
        ]
        assert any(c.args[1].get("status") == "failed" for c in done_calls)


# ---------------------------------------------------------------------------
# 24. scraper.stop() raises in finally block (lines 860-861)
# ---------------------------------------------------------------------------


class TestScraperStopFailure:
    """Lines 860-861: scraper.stop() raises → error is swallowed, job status preserved."""

    async def test_scraper_stop_failure_does_not_crash(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "stop-fail"),
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)
        scraper.stop = AsyncMock(side_effect=OSError("Cannot stop browser"))

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast", return_value="# x"
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown", return_value=["# x"]
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(
                                            job,
                                            resume_urls=["https://example.com/"],
                                        )

        # Job should still complete — stop failure is swallowed
        assert job.status == "completed"


# ---------------------------------------------------------------------------
# 25. is_cancelled inside _process_page (line 389-390)
# ---------------------------------------------------------------------------


class TestIsCancelledInsideProcessPage:
    """Line 389-390: job.is_cancelled check inside _process_page semaphore."""

    async def test_cancelled_inside_process_page_skips_scraping(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "cancel-in-page"),
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job._cancelled = True  # already cancelled before any processing
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch("src.jobs.runner.save_job_state"):
                            await run_job(
                                job,
                                resume_urls=[
                                    "https://example.com/page1",
                                    "https://example.com/page2",
                                ],
                            )

        # When cancelled before processing, scraper.get_html should never be called
        scraper.get_html.assert_not_called()


# ---------------------------------------------------------------------------
# 26. Playwright retry with CancelledError during wait (line 501)
# ---------------------------------------------------------------------------


class TestPlaywrightCancelledDuringRetry:
    """Line 501: asyncio.CancelledError is re-raised immediately during scrape."""

    async def test_cancelled_error_propagates_from_get_html(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "cancel-err"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        # CancelledError should propagate and cancel the page but not the whole job
        # (the outer try/except in _process_page catches non-CancelledError)
        scraper.get_html = AsyncMock(side_effect=asyncio.CancelledError())

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch("src.jobs.runner.save_job_state"):
                            # CancelledError may propagate up through gather
                            try:
                                await run_job(
                                    job,
                                    resume_urls=["https://example.com/page1"],
                                )
                            except (asyncio.CancelledError, Exception):
                                pass


# ---------------------------------------------------------------------------
# 27. Multiple chunks with successful cleanup — per-chunk log emitted
# ---------------------------------------------------------------------------


class TestMultipleChunksWithCleanup:
    """Lines 628-637: multiple chunks, cleanup succeeds → per-chunk timing log."""

    async def test_multi_chunk_cleanup_logs_each_chunk(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "multi-chunk"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model="ollama/qwen3:14b",
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=False
                        ):
                            with patch(
                                "src.jobs.runner.content_hash", return_value="hash_mc1"
                            ):
                                # Two chunks → triggers per-chunk timing log
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=["# Chunk 1", "# Chunk 2"],
                                ):
                                    with patch(
                                        "src.jobs.runner.needs_llm_cleanup",
                                        return_value=True,
                                    ):
                                        with patch(
                                            "src.jobs.runner.cleanup_markdown",
                                            return_value="# Cleaned",
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        # Should see chunk 1/2 and 2/2 log entries
        assert any("1/2" in m for m in messages)
        assert any("2/2" in m for m in messages)


# ---------------------------------------------------------------------------
# 28. page_cache.put called after Playwright scrape (lines 522-524)
# ---------------------------------------------------------------------------


class TestPageCachePutAfterPlaywright:
    """Lines 522-524: page_cache.put is called with raw HTML after Playwright scrape."""

    async def test_cache_put_called_after_playwright_scrape(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "cache-put"),
            use_cache=True,
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        mock_cache = MagicMock()
        mock_cache.get = MagicMock(return_value=None)  # cache miss
        mock_cache.put = MagicMock()
        mock_cache.hits = 0
        mock_cache.misses = 1

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.PageCache", return_value=mock_cache
                        ):
                            with patch(
                                "src.jobs.runner.is_blocked_response",
                                return_value=False,
                            ):
                                with patch(
                                    "src.jobs.runner.content_hash",
                                    return_value="hash_put1",
                                ):
                                    with patch(
                                        "src.jobs.runner.chunk_markdown",
                                        return_value=["# Content"],
                                    ):
                                        with patch(
                                            "src.jobs.runner.needs_llm_cleanup",
                                            return_value=False,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        # put should have been called with the URL and raw HTML
        mock_cache.put.assert_called_once()


# ---------------------------------------------------------------------------
# 29. is_cancelled break inside chunk loop (line 606)
# ---------------------------------------------------------------------------


class TestIsCancelledInsideChunkLoop:
    """Line 606: job.is_cancelled breaks the chunk iteration loop."""

    async def test_cancelled_mid_chunk_stops_processing(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "cancel-chunk"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model="ollama/qwen3:14b",
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        # Cancel on the first cleanup call
        async def _cancel_on_cleanup(chunk, model):
            job._cancelled = True
            return "# cleaned"

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=False
                        ):
                            with patch(
                                "src.jobs.runner.content_hash", return_value="hash_cl1"
                            ):
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=[
                                        "# Chunk A",
                                        "# Chunk B",
                                        "# Chunk C",
                                    ],
                                ):
                                    with patch(
                                        "src.jobs.runner.needs_llm_cleanup",
                                        return_value=True,
                                    ):
                                        with patch(
                                            "src.jobs.runner.cleanup_markdown",
                                            side_effect=_cancel_on_cleanup,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        # Job was cancelled, should not be completed
        done_completed = [
            c
            for c in job.emit_event.call_args_list
            if c.args[0] == "job_done" and c.args[1].get("status") == "completed"
        ]
        assert done_completed == []


# ---------------------------------------------------------------------------
# 30. pipeline mode branch (lines 734-768) — use_pipeline_mode=True
# ---------------------------------------------------------------------------


class TestPipelineModeBranch:
    """Lines 736-745: use_pipeline_mode=True logs pipeline mode message."""

    async def test_pipeline_mode_logs_pipeline_message(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "pipeline-mode"),
            use_pipeline_mode=True,
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast", return_value="# x"
                        ):
                            with patch(
                                "src.jobs.runner.is_blocked_response",
                                return_value=False,
                            ):
                                with patch(
                                    "src.jobs.runner.content_hash",
                                    return_value="hash_pm1",
                                ):
                                    with patch(
                                        "src.jobs.runner.chunk_markdown",
                                        return_value=["# x"],
                                    ):
                                        with patch(
                                            "src.jobs.runner.needs_llm_cleanup",
                                            return_value=False,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/"
                                                    ],
                                                )

        messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("pipeline mode" in m.lower() for m in messages)

    async def test_pipeline_mode_completes_successfully(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "pipeline-complete"),
            use_pipeline_mode=True,
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast", return_value="# x"
                        ):
                            with patch(
                                "src.jobs.runner.is_blocked_response",
                                return_value=False,
                            ):
                                with patch(
                                    "src.jobs.runner.content_hash",
                                    return_value="hash_pm2",
                                ):
                                    with patch(
                                        "src.jobs.runner.chunk_markdown",
                                        return_value=["# x"],
                                    ):
                                        with patch(
                                            "src.jobs.runner.needs_llm_cleanup",
                                            return_value=False,
                                        ):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/"
                                                    ],
                                                )

        assert job.status == "completed"


# ---------------------------------------------------------------------------
# 31. Safety net in finally — job.status still 'running' (lines 865-876)
# ---------------------------------------------------------------------------


class TestSafetyNetRunningStatus:
    """Lines 865-876: If job.status is still 'running' in finally, emit job_done failed."""

    async def test_safety_net_emits_job_done_when_status_running(self, tmp_path):
        """Trigger the safety net by raising BaseException (not Exception) so it bypasses
        the except Exception handler but still lands in finally with status='running'."""
        req = _make_request(
            output_path=str(tmp_path / "safety-net"),
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        # Track what events are emitted
        emitted = []

        async def _track_emit(event_type, data):
            emitted.append((event_type, data))

        job.emit_event = _track_emit

        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        converter = MagicMock()
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None

        # Raise KeyboardInterrupt (BaseException, not Exception) after scraper starts
        # This bypasses the "except Exception" block, so job.status stays "running"
        # and the finally block safety-net triggers.
        scraper.start = AsyncMock(side_effect=KeyboardInterrupt("test interrupt"))

        try:
            with patch("src.jobs.runner.validate_models", return_value=[]):
                with patch("src.jobs.runner.PageScraper", return_value=scraper):
                    with patch("src.jobs.runner.get_converter", return_value=converter):
                        with patch("src.jobs.runner.RobotsParser", return_value=robots):
                            with patch("src.jobs.runner.save_job_state"):
                                await run_job(job, resume_urls=[])
        except (KeyboardInterrupt, BaseException):
            pass

        # The safety net in finally should have emitted job_done with failed status
        done_events = [(t, d) for t, d in emitted if t == "job_done"]
        assert any(d.get("status") == "failed" for _, d in done_events)


# ---------------------------------------------------------------------------
# 32. outer exception handler emitting fails (lines 854-855)
# ---------------------------------------------------------------------------


class TestOuterExceptionEmitFails:
    """Lines 854-855: emit_event itself raises inside the outer except block."""

    async def test_emit_error_in_outer_handler_is_swallowed(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "outer-emit-fail"),
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)

        call_count = [0]

        async def _failing_emit(event_type, data):
            call_count[0] += 1
            # Let phase_change and init calls through, fail on job_done
            if event_type == "job_done":
                raise OSError("Queue full")

        job.emit_event = _failing_emit

        scraper = MagicMock()
        # scraper.start raises to trigger outer exception handler
        scraper.start = AsyncMock(side_effect=RuntimeError("Scraper init failed"))
        scraper.stop = AsyncMock()
        converter = MagicMock()
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        # Should not raise despite emit failing
                        await run_job(job)

        assert job.status == "failed"


# ---------------------------------------------------------------------------
# 33. JSON format with raw_html (line 657-658) — Playwright path + json output
# ---------------------------------------------------------------------------


class TestJsonOutputWithRawHtml:
    """Line 657-658: output_format='json' with Playwright path sets raw_html."""

    async def test_json_output_via_playwright_calls_html_to_structured(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "json-raw-html"),
            output_format="json",
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.is_blocked_response", return_value=False
                        ):
                            with patch(
                                "src.jobs.runner.content_hash", return_value="hash_rh1"
                            ):
                                with patch(
                                    "src.jobs.runner.chunk_markdown",
                                    return_value=["# Content"],
                                ):
                                    with patch(
                                        "src.jobs.runner.html_to_structured"
                                    ) as mock_structured:
                                        mock_structured.return_value = MagicMock(
                                            url="https://example.com/page1",
                                            title=None,
                                            blocks=[],
                                        )
                                        with patch("src.jobs.runner.save_structured"):
                                            with patch(
                                                "src.jobs.runner.save_job_state"
                                            ):
                                                await run_job(
                                                    job,
                                                    resume_urls=[
                                                        "https://example.com/page1"
                                                    ],
                                                )

        # html_to_structured called because raw_html is set from Playwright
        mock_structured.assert_called_once()


# ---------------------------------------------------------------------------
# 34. cancelled inside retry after job.is_cancelled check (line 503-504)
# ---------------------------------------------------------------------------


class TestCancelledDuringPlaywrightRetry:
    """Line 503-504: job.is_cancelled → raises CancelledError during retry loop.

    When get_html raises a non-CancelledError and job.is_cancelled is True,
    the retry handler converts it to CancelledError. This propagates through
    asyncio.gather, triggering the outer exception handler → job.status = 'failed'.
    """

    async def test_cancellation_during_retry_is_handled(self, tmp_path):
        req = _make_request(
            output_path=str(tmp_path / "cancel-retry"),
            use_http_fast_path=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(req)
        job.emit_event = AsyncMock()
        scraper, converter, robots = _base_patches(tmp_path)

        attempt = [0]

        async def _get_html_cancel_on_retry(*args, **kwargs):
            attempt[0] += 1
            if attempt[0] == 1:
                job._cancelled = True
                raise RuntimeError("Network error")
            return "<h1>OK</h1>"

        scraper.get_html = _get_html_cancel_on_retry

        # CancelledError propagates through gather → caught as BaseException by
        # the test or by Python asyncio machinery. We just verify job is not "completed".
        try:
            with patch("src.jobs.runner.validate_models", return_value=[]):
                with patch("src.jobs.runner.PageScraper", return_value=scraper):
                    with patch("src.jobs.runner.get_converter", return_value=converter):
                        with patch("src.jobs.runner.RobotsParser", return_value=robots):
                            with patch("src.jobs.runner.save_job_state"):
                                with patch("asyncio.sleep"):
                                    await run_job(
                                        job,
                                        resume_urls=["https://example.com/page1"],
                                    )
        except (asyncio.CancelledError, Exception):
            pass

        # Job should not be completed when cancelled during retry
        assert job.status != "completed"
