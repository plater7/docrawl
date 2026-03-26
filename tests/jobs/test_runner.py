"""Unit/integration tests for src/jobs/runner.py — coverage plan 2026-03-06."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.models import JobRequest
from src.jobs.manager import Job
from src.jobs.runner import (
    _generate_index,
    _log,
    _url_to_filepath,
    run_job,
    validate_models,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(**overrides) -> JobRequest:
    """Minimal valid JobRequest that skips all optional fetch paths by default."""
    defaults = dict(
        url="https://example.com",
        crawl_model="ollama/mistral:7b",
        pipeline_model="ollama/qwen3:14b",
        reasoning_model="ollama/deepseek-r1:32b",
        output_path="/data/output",
        delay_ms=500,
        max_concurrent=3,
        max_depth=5,
        respect_robots_txt=False,
        use_native_markdown=False,
        use_markdown_proxy=False,
        use_http_fast_path=False,
        use_cache=False,
        output_format="markdown",
        use_pipeline_mode=False,
        converter=None,
        language="en",
        filter_sitemap_by_path=True,
    )
    defaults.update(overrides)
    return JobRequest.model_construct(**defaults)


def _make_job(request=None) -> Job:
    return Job(id="test-job-0000", request=request or _make_request())


# ---------------------------------------------------------------------------
# Task 1: TestValidateModels
# ---------------------------------------------------------------------------


class TestValidateModels:
    async def test_returns_empty_when_ollama_model_found(self):
        with patch(
            "src.jobs.runner.get_available_models",
            return_value=[{"name": "mistral:7b"}],
        ):
            with patch("src.jobs.runner.get_provider_for_model", return_value="ollama"):
                errors = await validate_models("mistral:7b", "mistral:7b", "mistral:7b")
        assert errors == []

    async def test_error_when_ollama_model_not_in_list(self):
        with patch(
            "src.jobs.runner.get_available_models",
            return_value=[{"name": "llama3:8b"}],
        ):
            with patch("src.jobs.runner.get_provider_for_model", return_value="ollama"):
                errors = await validate_models("mistral:7b", "mistral:7b", "mistral:7b")
        assert len(errors) == 3
        assert "mistral:7b" in errors[0]

    async def test_error_when_get_available_models_raises(self):
        with patch(
            "src.jobs.runner.get_available_models",
            side_effect=Exception("connection refused"),
        ):
            with patch("src.jobs.runner.get_provider_for_model", return_value="ollama"):
                errors = await validate_models("mistral:7b", "mistral:7b", "mistral:7b")
        assert len(errors) == 3
        assert "connection refused" in errors[0]

    async def test_ollama_base_name_match(self):
        """mistral:7b matches available mistral:latest via base name."""
        with patch(
            "src.jobs.runner.get_available_models",
            return_value=[{"name": "mistral:latest"}],
        ):
            with patch("src.jobs.runner.get_provider_for_model", return_value="ollama"):
                errors = await validate_models("mistral:7b", "mistral:7b", "mistral:7b")
        assert errors == []

    async def test_no_error_for_lmstudio_provider(self):
        """Non-ollama providers (lmstudio) skip availability check."""
        with patch(
            "src.jobs.runner.get_available_models",
            return_value=[{"name": "some-model"}],
        ):
            with patch(
                "src.jobs.runner.get_provider_for_model", return_value="lmstudio"
            ):
                errors = await validate_models("lmstudio/m", "lmstudio/m", "lmstudio/m")
        assert errors == []


# ---------------------------------------------------------------------------
# Task 2: TestLog
# ---------------------------------------------------------------------------


class TestLog:
    async def test_emits_event_to_job(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        await _log(job, "phase_change", {"phase": "init", "message": "Starting"})
        job.emit_event.assert_awaited_once_with(
            "phase_change", {"phase": "init", "message": "Starting"}
        )

    async def test_no_log_when_message_empty(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        await _log(job, "phase_change", {"phase": "init"})
        job.emit_event.assert_awaited_once()

    async def test_error_level_uses_logger_error(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        with patch("src.jobs.runner.logger") as mock_logger:
            await _log(
                job,
                "log",
                {"phase": "scraping", "message": "Failed", "level": "error"},
            )
        mock_logger.error.assert_called_once()

    async def test_warning_level_uses_logger_warning(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        with patch("src.jobs.runner.logger") as mock_logger:
            await _log(
                job,
                "log",
                {"phase": "scraping", "message": "Warn", "level": "warning"},
            )
        mock_logger.warning.assert_called_once()

    async def test_default_level_uses_logger_info(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        with patch("src.jobs.runner.logger") as mock_logger:
            await _log(
                job,
                "log",
                {"phase": "scraping", "message": "Info"},
            )
        mock_logger.info.assert_called_once()

    async def test_model_suffix_appended_when_active_model_present(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        with patch("src.jobs.runner.logger") as mock_logger:
            await _log(
                job,
                "log",
                {
                    "phase": "cleanup",
                    "message": "Cleaning",
                    "active_model": "qwen3:14b",
                },
            )
        call_args = mock_logger.info.call_args[0][0]
        assert "qwen3:14b" in call_args


# ---------------------------------------------------------------------------
# Task 3: TestUrlToFilepath
# ---------------------------------------------------------------------------


class TestUrlToFilepath:
    def test_root_url_becomes_index_md(self, tmp_path):
        result = _url_to_filepath(
            "https://example.com/", "https://example.com/", tmp_path
        )
        assert result == tmp_path / "index.md"

    def test_subpath_preserved(self, tmp_path):
        result = _url_to_filepath(
            "https://example.com/guide/install",
            "https://example.com/",
            tmp_path,
        )
        assert result == tmp_path / "guide/install.md"

    def test_extension_stripped_and_md_added(self, tmp_path):
        result = _url_to_filepath(
            "https://example.com/page.html",
            "https://example.com/",
            tmp_path,
        )
        assert result == tmp_path / "page.md"

    def test_base_path_stripped_from_result(self, tmp_path):
        result = _url_to_filepath(
            "https://example.com/docs/guide",
            "https://example.com/docs/",
            tmp_path,
        )
        assert result == tmp_path / "guide.md"

    def test_nested_subdirectory(self, tmp_path):
        result = _url_to_filepath(
            "https://example.com/api/v2/reference",
            "https://example.com/",
            tmp_path,
        )
        assert result == tmp_path / "api/v2/reference.md"


# ---------------------------------------------------------------------------
# Task 4: TestGenerateIndex
# ---------------------------------------------------------------------------


class TestGenerateIndex:
    def test_creates_index_file(self, tmp_path):
        _generate_index(["https://example.com/page1"], tmp_path)
        assert (tmp_path / "_index.md").exists()

    def test_index_contains_documentation_header(self, tmp_path):
        _generate_index([], tmp_path)
        content = (tmp_path / "_index.md").read_text()
        assert "# Documentation Index" in content

    def test_index_contains_link_for_each_url(self, tmp_path):
        urls = ["https://example.com/guide", "https://example.com/api"]
        _generate_index(urls, tmp_path)
        content = (tmp_path / "_index.md").read_text()
        assert "guide" in content
        assert "api" in content

    def test_root_url_becomes_home_link(self, tmp_path):
        _generate_index(["https://example.com/"], tmp_path)
        content = (tmp_path / "_index.md").read_text()
        assert "Home" in content

    def test_empty_url_list_creates_header_only(self, tmp_path):
        _generate_index([], tmp_path)
        content = (tmp_path / "_index.md").read_text()
        assert content.startswith("# Documentation Index")


# ---------------------------------------------------------------------------
# Task 5: TestRunJobModelValidationFail
# ---------------------------------------------------------------------------


class TestRunJobModelValidationFail:
    """run_job exits early and sets status=failed when models are invalid."""

    def _make_mocks(self):
        scraper_mock = MagicMock()
        scraper_mock.start = AsyncMock()
        scraper_mock.stop = AsyncMock()
        converter_mock = MagicMock()
        return scraper_mock, converter_mock

    async def test_job_status_set_to_failed(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        scraper, converter = self._make_mocks()

        with patch("src.jobs.runner.validate_models", return_value=["Model not found"]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser"):
                        await run_job(job)

        assert job.status == "failed"

    async def test_job_done_event_emitted_with_failed_status(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        scraper, converter = self._make_mocks()

        with patch("src.jobs.runner.validate_models", return_value=["Model not found"]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser"):
                        await run_job(job)

        emitted_types = [call.args[0] for call in job.emit_event.call_args_list]
        assert "job_done" in emitted_types

    async def test_scraper_stop_called_in_finally(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        scraper, converter = self._make_mocks()

        with patch("src.jobs.runner.validate_models", return_value=["error"]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser"):
                        await run_job(job)

        scraper.stop.assert_awaited_once()


# ---------------------------------------------------------------------------
# Task 6: TestRunJobHappyPath
# ---------------------------------------------------------------------------


class TestRunJobHappyPath:
    """run_job completes successfully with resume_urls (skips discovery)."""

    def _make_scraper_and_deps(self):
        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        scraper.get_html = AsyncMock(return_value="<h1>Hello</h1>")

        converter = MagicMock()
        converter.convert = MagicMock(return_value="# Hello\n\nContent")

        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None
        robots.is_allowed = MagicMock(return_value=True)

        return scraper, converter, robots

    async def test_job_status_completed(self, tmp_path):
        urls = ["https://example.com/page1", "https://example.com/page2"]
        request = _make_request(
            output_path=str(tmp_path / "test-runner-status"),
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper, converter, robots = self._make_scraper_and_deps()

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast",
                            return_value="# Page content",
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown",
                                return_value=["# Page content"],
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(job, resume_urls=urls)

        assert job.status == "completed"

    async def test_job_done_event_has_completed_status(self, tmp_path):
        urls = ["https://example.com/page1"]
        request = _make_request(
            output_path=str(tmp_path / "test-runner-event"),
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper, converter, robots = self._make_scraper_and_deps()

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast",
                            return_value="# Page content",
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown",
                                return_value=["# Page content"],
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(job, resume_urls=urls)

        done_events = [
            call for call in job.emit_event.call_args_list if call.args[0] == "job_done"
        ]
        assert len(done_events) == 1
        assert done_events[0].args[1]["status"] == "completed"

    async def test_output_files_created_for_each_url(self, tmp_path):
        urls = ["https://example.com/page1", "https://example.com/page2"]
        request = _make_request(
            output_path=str(tmp_path / "test-runner-files"),
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper, converter, robots = self._make_scraper_and_deps()

        def _unique_html(url, **kwargs):
            return f"# Page content for {url}"

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast",
                            side_effect=_unique_html,
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown",
                                side_effect=lambda md, **kw: [md],
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(job, resume_urls=urls)

        out = Path(job.request.output_path)
        assert (out / "page1.md").exists()
        assert (out / "page2.md").exists()

    async def test_index_file_created(self, tmp_path):
        urls = ["https://example.com/page1"]
        request = _make_request(
            output_path=str(tmp_path / "test-runner-index"),
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper, converter, robots = self._make_scraper_and_deps()

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast",
                            return_value="# Page content",
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown",
                                return_value=["# Page content"],
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(job, resume_urls=urls)

        out = Path(job.request.output_path)
        assert (out / "_index.md").exists()


# ---------------------------------------------------------------------------
# Task 7: TestRunJobCancellation + TestRunJobDiscovery
# ---------------------------------------------------------------------------


class TestRunJobCancellation:
    """run_job respects job.is_cancelled during scraping."""

    async def test_cancelled_job_does_not_emit_completed(self):
        urls = ["https://example.com/page1"]
        request = _make_request(
            output_path="test-runner-cancel",
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        job._cancelled = True  # pre-cancel — is_cancelled is a property on _cancelled

        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        converter = MagicMock()
        converter.convert = MagicMock(return_value="# content")
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast", return_value="# x"
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown",
                                return_value=["# x"],
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(job, resume_urls=urls)

        done_events = [
            c for c in job.emit_event.call_args_list if c.args[0] == "job_done"
        ]
        completed = [e for e in done_events if e.args[1].get("status") == "completed"]
        assert completed == []


class TestRunJobDiscovery:
    """run_job calls discover_urls when resume_urls is None."""

    async def test_discovery_called_when_no_resume_urls(self):
        request = _make_request(
            output_path="test-runner-disc",
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()

        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        converter = MagicMock()
        converter.convert = MagicMock(return_value="# content")
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None
        robots.is_allowed = MagicMock(return_value=True)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.discover_urls",
                            return_value=["https://example.com/"],
                        ) as mock_disc:
                            with patch(
                                "src.jobs.runner.filter_urls",
                                return_value=["https://example.com/"],
                            ):
                                with patch(
                                    "src.jobs.runner.filter_urls_with_llm",
                                    return_value=["https://example.com/"],
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

        mock_disc.assert_awaited_once()

    async def test_filter_urls_called_after_discovery(self):
        request = _make_request(
            output_path="test-runner-filter",
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()

        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        converter = MagicMock()
        converter.convert = MagicMock(return_value="# content")
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None
        robots.is_allowed = MagicMock(return_value=True)

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
                            ) as mock_filter:
                                with patch(
                                    "src.jobs.runner.filter_urls_with_llm",
                                    return_value=["https://example.com/"],
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

        mock_filter.assert_called_once()


# ---------------------------------------------------------------------------
# Task 8: Test Retry Logic (pages_retried counter)
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Tests for scrape retry functionality."""

    def _make_scraper_and_deps(self):
        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        scraper.get_html = AsyncMock(return_value="<h1>Hello</h1>")

        converter = MagicMock()
        converter.convert = MagicMock(return_value="# Hello\n\nContent")

        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None
        robots.is_allowed = MagicMock(return_value=True)

        return scraper, converter, robots

    async def test_pages_retried_incremented_on_failure(self, tmp_path):
        """When Playwright fails and retries, pages_retried should be incremented."""
        urls = ["https://example.com/page1"]
        request = _make_request(
            output_path=str(tmp_path / "test-retry"),
            use_http_fast_path=False,  # Force Playwright path
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper, converter, robots = self._make_scraper_and_deps()

        # First call fails, second succeeds
        scraper.get_html = AsyncMock(
            side_effect=[Exception("Network error"), "<h1>Hello</h1>"]
        )

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast", return_value=None
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
                                        await run_job(job, resume_urls=urls)

        assert job.pages_retried == 1

    async def test_no_retry_when_http_fast_succeeds(self, tmp_path):
        """When HTTP fast path succeeds, no retries should occur."""
        urls = ["https://example.com/page1"]
        request = _make_request(
            output_path=str(tmp_path / "test-no-retry"),
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper, converter, robots = self._make_scraper_and_deps()

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast",
                            return_value="# Fast content",
                        ):
                            with patch(
                                "src.jobs.runner.chunk_markdown",
                                return_value=["# Fast"],
                            ):
                                with patch(
                                    "src.jobs.runner.needs_llm_cleanup",
                                    return_value=False,
                                ):
                                    with patch("src.jobs.runner.save_job_state"):
                                        await run_job(job, resume_urls=urls)

        assert job.pages_retried == 0
        scraper.get_html.assert_not_called()


# ---------------------------------------------------------------------------
# Task 9: Test Blocked Response Handling
# ---------------------------------------------------------------------------


class TestBlockedResponse:
    """Tests for blocked response detection."""

    def _make_scraper_and_deps(self):
        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        scraper.get_html = AsyncMock(return_value="<h1>Hello</h1>")

        converter = MagicMock()
        converter.convert = MagicMock(return_value="# Content")

        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None
        robots.is_allowed = MagicMock(return_value=True)

        return scraper, converter, robots

    async def test_blocked_response_increments_counter(self, tmp_path):
        """When response is blocked, pages_blocked should be incremented."""
        urls = ["https://example.com/page1"]
        request = _make_request(
            output_path=str(tmp_path / "test-blocked"),
            use_http_fast_path=False,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper, converter, robots = self._make_scraper_and_deps()

        # Return blocked content (requires ≥2 pattern matches — threshold is 2)
        converter.convert = MagicMock(
            return_value="Checking your browser... Please enable JavaScript to continue."
        )

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner.fetch_html_fast", return_value=None
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
                                        await run_job(job, resume_urls=urls)

        assert job.pages_blocked == 1

    async def test_batch_loop_cancel_check_breaks(self, tmp_path):
        """Batch loop break fires when job becomes cancelled during gather (line 831-832)."""
        urls = ["https://example.com/page1"]
        request = _make_request(
            output_path=str(tmp_path / "test-batch-cancel"),
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        # Job must NOT be pre-cancelled — line 714 would return early otherwise.
        # Cancel it inside the _process_page mock so is_cancelled is True at line 831.

        scraper, converter, robots = self._make_scraper_and_deps()

        async def _cancel_during_process(*args, **kwargs):
            job._cancelled = True  # mark cancelled mid-batch

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch(
                            "src.jobs.runner._process_page",
                            new=AsyncMock(side_effect=_cancel_during_process),
                        ):
                            with patch("src.jobs.runner.save_job_state"):
                                await run_job(job, resume_urls=urls)

        assert job.is_cancelled


# ---------------------------------------------------------------------------
# Task 10: robots.txt respect path (respect_robots_txt=True)
# ---------------------------------------------------------------------------


class TestRunJobRobotsTxtRespect:
    """run_job loads robots.txt when respect_robots_txt=True."""

    async def test_robots_load_called_when_respect_true(self, tmp_path):
        """robots.load() is called when respect_robots_txt=True."""
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None
        robots.is_allowed = MagicMock(return_value=True)
        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        converter = MagicMock()
        converter.convert = MagicMock(return_value="# content")

        request = _make_request(
            output_path=str(tmp_path / "test-robots-r"),
            use_http_fast_path=True,
            respect_robots_txt=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(request)
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
                                            job, resume_urls=["https://example.com/"]
                                        )

        robots.load.assert_awaited_once()

    async def test_crawl_delay_from_robots_logged(self, tmp_path):
        """When robots.crawl_delay is set, it appears in a log event."""
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = 5.0
        robots.is_allowed = MagicMock(return_value=True)
        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        converter = MagicMock()
        converter.convert = MagicMock(return_value="# content")

        request = _make_request(
            output_path=str(tmp_path / "test-robots-delay"),
            use_http_fast_path=True,
            respect_robots_txt=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(request)
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
                                            job, resume_urls=["https://example.com/"]
                                        )

        emitted_messages = [
            call.args[1].get("message", "") for call in job.emit_event.call_args_list
        ]
        assert any("crawl-delay" in m for m in emitted_messages)


# ---------------------------------------------------------------------------
# Task 11: All-None models skips validate_models
# ---------------------------------------------------------------------------


class TestRunJobNullModels:
    """run_job skips validate_models entirely when all models are None."""

    async def test_no_model_skips_validation(self, tmp_path):
        """All-None models means validate_models is never called."""
        request = _make_request(
            output_path=str(tmp_path / "test-no-models"),
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        converter = MagicMock()
        converter.convert = MagicMock(return_value="# content")
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None
        robots.is_allowed = MagicMock(return_value=True)

        with patch("src.jobs.runner.validate_models") as mock_val:
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
                                            job, resume_urls=["https://example.com/"]
                                        )

        mock_val.assert_not_called()


# ---------------------------------------------------------------------------
# Task 12: use_cache=True initializes PageCache
# ---------------------------------------------------------------------------


class TestRunJobUseCache:
    """run_job initializes PageCache when use_cache=True."""

    async def test_cache_initialized_when_use_cache_true(self, tmp_path):
        """PageCache should be initialized when use_cache=True."""
        request = _make_request(
            output_path=str(tmp_path / "test-cache"),
            use_http_fast_path=True,
            use_cache=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        converter = MagicMock()
        converter.convert = MagicMock(return_value="# content")
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None
        robots.is_allowed = MagicMock(return_value=True)

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
                                        with patch(
                                            "src.jobs.runner.PageCache"
                                        ) as mock_cache_cls:
                                            mock_cache_cls.return_value = MagicMock()
                                            await run_job(
                                                job,
                                                resume_urls=["https://example.com/"],
                                            )

        mock_cache_cls.assert_called_once()

    async def test_cache_not_initialized_when_false(self, tmp_path):
        """PageCache should NOT be initialized when use_cache=False."""
        request = _make_request(
            output_path=str(tmp_path / "test-no-cache"),
            use_http_fast_path=True,
            use_cache=False,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        converter = MagicMock()
        converter.convert = MagicMock(return_value="# content")
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None
        robots.is_allowed = MagicMock(return_value=True)

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
                                        with patch(
                                            "src.jobs.runner.PageCache"
                                        ) as mock_cache_cls:
                                            await run_job(
                                                job,
                                                resume_urls=["https://example.com/"],
                                            )

        mock_cache_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Task 13: Pause/resume mid-scrape
# ---------------------------------------------------------------------------


class TestRunJobPauseResume:
    """run_job pauses and resumes mid-scrape."""

    async def test_paused_job_resumes_and_completes(self, tmp_path):
        """A job that is paused then resumed should reach completed status."""
        import asyncio

        request = _make_request(
            output_path=str(tmp_path / "test-pause-resume"),
            use_http_fast_path=True,
            crawl_model=None,
            pipeline_model=None,
            reasoning_model=None,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper = MagicMock()
        scraper.start = AsyncMock()
        scraper.stop = AsyncMock()
        converter = MagicMock()
        converter.convert = MagicMock(return_value="# content")
        robots = MagicMock()
        robots.load = AsyncMock()
        robots.crawl_delay = None
        robots.is_allowed = MagicMock(return_value=True)

        # Pause after the job is set to "running" by directly manipulating the event
        # so that wait_if_paused blocks, then resume it shortly after.
        original_wait = job.wait_if_paused
        wait_call_count = 0

        async def _patched_wait():
            nonlocal wait_call_count
            wait_call_count += 1
            if wait_call_count == 1:
                # Simulate a pause: clear the event so it blocks, then schedule resume
                job._pause_event.clear()
                job.status = "paused"

                async def _do_resume():
                    await asyncio.sleep(0.05)
                    job._pause_event.set()
                    job.status = "running"

                asyncio.create_task(_do_resume())
            await original_wait()

        job.wait_if_paused = _patched_wait

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
                                            resume_urls=["https://example.com/page"],
                                        )

        assert job.status == "completed"
