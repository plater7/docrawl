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
    from pathlib import Path
    base: dict = {
        "url": "https://example.com",
        "crawl_model": "ollama/mistral:7b",
        "pipeline_model": "ollama/qwen3:14b",
        "reasoning_model": "ollama/deepseek-r1:32b",
        "use_native_markdown": False,
        "use_markdown_proxy": False,
        "use_http_fast_path": False,
        "use_pipeline_mode": False,
        "respect_robots_txt": False,
        "use_cache": False,
        "output_format": "markdown",
    }
    if "tmp_dir" in overrides:
        tmp_dir = overrides.pop("tmp_dir")
        output_path = overrides.get("output_path", "test-output")
        base["output_path"] = str(tmp_dir / output_path)
    base.update(overrides)
    return JobRequest(**base)


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
            output_path="test-runner-status",
            tmp_dir=tmp_path,
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
            output_path="test-runner-event",
            tmp_dir=tmp_path,
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
            output_path="test-runner-files",
            tmp_dir=tmp_path,
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
            output_path="test-runner-index",
            tmp_dir=tmp_path,
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
