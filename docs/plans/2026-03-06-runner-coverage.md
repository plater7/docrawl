# runner.py Coverage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Increase `src/jobs/runner.py` test coverage from 26% to ≥70% (target 80%) by adding `tests/jobs/test_runner.py`.

**Architecture:** Approach C — pure-function unit tests + heavily-mocked `run_job` paths. No real Playwright, no real HTTP, no real LLM calls. All I/O patched at the module level. File system via `tmp_path` pytest fixture.

**Tech Stack:** pytest-asyncio (`asyncio_mode = auto`), `unittest.mock` (AsyncMock, MagicMock, patch), `pathlib.Path`, `src.jobs.runner`, `src.api.models.JobRequest`, `src.jobs.manager.Job`

---

## Shared helpers (add at top of test file, before any class)

```python
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.api.models import JobRequest
from src.jobs.manager import Job
from src.jobs.runner import (
    validate_models,
    _log,
    _url_to_filepath,
    _generate_index,
    run_job,
)


def _make_request(**overrides) -> JobRequest:
    base = {
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
    base.update(overrides)
    return JobRequest(**base)


def _make_job(request=None) -> Job:
    return Job(id="test-job-0000", request=request or _make_request())
```

---

### Task 1: TestValidateModels — Ollama model found

**Files:**
- Create: `tests/jobs/test_runner.py`

**Step 1: Write the failing test**

```python
class TestValidateModels:
    async def test_returns_empty_when_ollama_model_found(self):
        with patch("src.jobs.runner.get_available_models",
                   return_value=[{"name": "mistral:7b"}]):
            with patch("src.jobs.runner.get_provider_for_model", return_value="ollama"):
                errors = await validate_models("mistral:7b", "mistral:7b", "mistral:7b")
        assert errors == []
```

**Step 2: Run to verify FAIL**
```bash
cd docrawl && python -m pytest tests/jobs/test_runner.py::TestValidateModels::test_returns_empty_when_ollama_model_found -x --no-cov -q
```
Expected: `ImportError` or `ModuleNotFoundError` (file doesn't exist yet).

**Step 3: Create `tests/jobs/test_runner.py`** with helpers + this test class.

**Step 4: Run to verify PASS**
```bash
python -m pytest tests/jobs/test_runner.py::TestValidateModels::test_returns_empty_when_ollama_model_found -x --no-cov -q
```

**Step 5: Add remaining TestValidateModels tests (no commit yet)**

```python
    async def test_error_when_ollama_model_not_in_list(self):
        with patch("src.jobs.runner.get_available_models",
                   return_value=[{"name": "llama3:8b"}]):
            with patch("src.jobs.runner.get_provider_for_model", return_value="ollama"):
                errors = await validate_models("mistral:7b", "mistral:7b", "mistral:7b")
        assert len(errors) == 3
        assert "mistral:7b" in errors[0]

    async def test_error_when_get_available_models_raises(self):
        with patch("src.jobs.runner.get_available_models",
                   side_effect=Exception("connection refused")):
            with patch("src.jobs.runner.get_provider_for_model", return_value="ollama"):
                errors = await validate_models("mistral:7b", "mistral:7b", "mistral:7b")
        assert len(errors) == 3
        assert "connection refused" in errors[0]

    async def test_ollama_base_name_match(self):
        """mistral:7b matches available mistral:latest via base name."""
        with patch("src.jobs.runner.get_available_models",
                   return_value=[{"name": "mistral:latest"}]):
            with patch("src.jobs.runner.get_provider_for_model", return_value="ollama"):
                errors = await validate_models("mistral:7b", "mistral:7b", "mistral:7b")
        assert errors == []

    async def test_no_error_for_lmstudio_provider(self):
        """Non-ollama providers (lmstudio) skip availability check."""
        with patch("src.jobs.runner.get_available_models", return_value=[{"name": "some-model"}]):
            with patch("src.jobs.runner.get_provider_for_model", return_value="lmstudio"):
                errors = await validate_models("lmstudio/m", "lmstudio/m", "lmstudio/m")
        assert errors == []
```

**Step 6: Run all TestValidateModels**
```bash
python -m pytest tests/jobs/test_runner.py::TestValidateModels --no-cov -q
```
Expected: 5 passed

**Step 7: Commit**
```bash
git add tests/jobs/test_runner.py
git commit -m "test(runner): TestValidateModels — 5 tests for model validation logic"
```

---

### Task 2: TestLog — SSE emit + logging

**Step 1: Write the failing tests**

```python
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
        # No exception, just emits event with no message logged
        await _log(job, "phase_change", {"phase": "init"})
        job.emit_event.assert_awaited_once()

    async def test_error_level_uses_logger_error(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        with patch("src.jobs.runner.logger") as mock_logger:
            await _log(job, "log", {"phase": "scraping", "message": "Failed", "level": "error"})
        mock_logger.error.assert_called_once()

    async def test_warning_level_uses_logger_warning(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        with patch("src.jobs.runner.logger") as mock_logger:
            await _log(job, "log", {"phase": "scraping", "message": "Warn", "level": "warning"})
        mock_logger.warning.assert_called_once()

    async def test_default_level_uses_logger_info(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        with patch("src.jobs.runner.logger") as mock_logger:
            await _log(job, "log", {"phase": "scraping", "message": "Info"})
        mock_logger.info.assert_called_once()

    async def test_model_suffix_appended_when_active_model_present(self):
        job = _make_job()
        job.emit_event = AsyncMock()
        with patch("src.jobs.runner.logger") as mock_logger:
            await _log(job, "log", {
                "phase": "cleanup", "message": "Cleaning", "active_model": "qwen3:14b"
            })
        call_args = mock_logger.info.call_args[0][0]
        assert "qwen3:14b" in call_args
```

**Step 2: Run to verify FAIL**
```bash
python -m pytest tests/jobs/test_runner.py::TestLog --no-cov -q
```

**Step 3: Add TestLog class to test file. Run to verify PASS.**
```bash
python -m pytest tests/jobs/test_runner.py::TestLog --no-cov -q
```
Expected: 6 passed

**Step 4: Commit**
```bash
git add tests/jobs/test_runner.py
git commit -m "test(runner): TestLog — 6 tests for SSE emit and log level routing"
```

---

### Task 3: TestUrlToFilepath — pure sync function

**Step 1: Write tests**

```python
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
```

**Step 2: Run to verify FAIL → PASS after adding class.**
```bash
python -m pytest tests/jobs/test_runner.py::TestUrlToFilepath --no-cov -q
```
Expected: 5 passed

**Step 3: Commit**
```bash
git add tests/jobs/test_runner.py
git commit -m "test(runner): TestUrlToFilepath — 5 tests for URL→filepath mapping"
```

---

### Task 4: TestGenerateIndex — writes _index.md

**Step 1: Write tests**

```python
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
```

**Step 2: Run to verify FAIL → PASS.**
```bash
python -m pytest tests/jobs/test_runner.py::TestGenerateIndex --no-cov -q
```
Expected: 5 passed

**Step 3: Commit**
```bash
git add tests/jobs/test_runner.py
git commit -m "test(runner): TestGenerateIndex — 5 tests for _index.md generation"
```

---

### Task 5: TestRunJobModelValidationFail — run_job early-exit on bad models

This is the most important `run_job` path. Key mocks needed:
- `validate_models` → returns errors
- `PageScraper` → AsyncMock (start/stop)
- `get_converter` → returns MagicMock converter
- `job.emit_event` → AsyncMock

**Step 1: Write tests**

```python
class TestRunJobModelValidationFail:
    """run_job exits early and sets status=failed when models are invalid."""

    def _make_mocks(self):
        scraper_mock = MagicMock()
        scraper_mock.start = AsyncMock()
        scraper_mock.stop = AsyncMock()
        converter_mock = MagicMock()
        return scraper_mock, converter_mock

    async def test_job_status_set_to_failed(self, tmp_path):
        job = _make_job(_make_request(output_path=str(tmp_path / "out")))
        job.emit_event = AsyncMock()
        scraper, converter = self._make_mocks()

        with patch("src.jobs.runner.validate_models", return_value=["Model not found"]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser"):
                        await run_job(job)

        assert job.status == "failed"

    async def test_job_done_event_emitted_with_failed_status(self, tmp_path):
        job = _make_job(_make_request(output_path=str(tmp_path / "out")))
        job.emit_event = AsyncMock()
        scraper, converter = self._make_mocks()

        with patch("src.jobs.runner.validate_models", return_value=["Model not found"]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser"):
                        await run_job(job)

        emitted_types = [call.args[0] for call in job.emit_event.call_args_list]
        assert "job_done" in emitted_types

    async def test_scraper_stop_called_in_finally(self, tmp_path):
        job = _make_job(_make_request(output_path=str(tmp_path / "out")))
        job.emit_event = AsyncMock()
        scraper, converter = self._make_mocks()

        with patch("src.jobs.runner.validate_models", return_value=["error"]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser"):
                        await run_job(job)

        scraper.stop.assert_awaited_once()
```

**Step 2: Run to verify FAIL → PASS.**
```bash
python -m pytest tests/jobs/test_runner.py::TestRunJobModelValidationFail --no-cov -q
```
Expected: 3 passed

**Step 3: Commit**
```bash
git add tests/jobs/test_runner.py
git commit -m "test(runner): TestRunJobModelValidationFail — 3 tests for early-exit on invalid models"
```

---

### Task 6: TestRunJobHappyPath — full run_job with resume_urls

Using `resume_urls` skips discovery/filtering (biggest mock surface). Mocks needed:
- `validate_models` → `[]`
- `PageScraper.start/stop` → AsyncMock
- `get_converter` → converter with `.convert()` returning markdown string
- `RobotsParser` → MagicMock
- `filter_urls_with_llm` → returns urls as-is (needed even with resume)
- `fetch_html_fast` → returns markdown (avoids Playwright)
- `chunk_markdown` → returns `["# Content"]`
- `needs_llm_cleanup` → False
- `save_job_state` → no-op
- `job.emit_event` → AsyncMock

**Step 1: Write tests**

```python
class TestRunJobHappyPath:
    """run_job completes successfully with resume_urls (skips discovery)."""

    def _patch_run_job(self, tmp_path, extra_overrides=None):
        """Context manager stack for a minimal happy-path run_job."""
        import contextlib

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
            output_path=str(tmp_path / "out"),
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper, converter, robots = self._patch_run_job(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch("src.jobs.runner.fetch_html_fast",
                                   return_value="# Page content"):
                            with patch("src.jobs.runner.chunk_markdown",
                                       return_value=["# Page content"]):
                                with patch("src.jobs.runner.needs_llm_cleanup",
                                           return_value=False):
                                    with patch("src.jobs.runner.save_job_state"):
                                        with patch("src.jobs.runner.filter_urls_with_llm",
                                                   return_value=urls):
                                            await run_job(job, resume_urls=urls)

        assert job.status == "completed"

    async def test_job_done_event_has_completed_status(self, tmp_path):
        urls = ["https://example.com/page1"]
        request = _make_request(
            output_path=str(tmp_path / "out"),
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper, converter, robots = self._patch_run_job(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch("src.jobs.runner.fetch_html_fast",
                                   return_value="# Page content"):
                            with patch("src.jobs.runner.chunk_markdown",
                                       return_value=["# Page content"]):
                                with patch("src.jobs.runner.needs_llm_cleanup",
                                           return_value=False):
                                    with patch("src.jobs.runner.save_job_state"):
                                        with patch("src.jobs.runner.filter_urls_with_llm",
                                                   return_value=urls):
                                            await run_job(job, resume_urls=urls)

        done_events = [
            call for call in job.emit_event.call_args_list
            if call.args[0] == "job_done"
        ]
        assert len(done_events) == 1
        assert done_events[0].args[1]["status"] == "completed"

    async def test_output_files_created_for_each_url(self, tmp_path):
        urls = ["https://example.com/page1", "https://example.com/page2"]
        out = tmp_path / "out"
        request = _make_request(
            output_path=str(out),
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper, converter, robots = self._patch_run_job(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch("src.jobs.runner.fetch_html_fast",
                                   return_value="# Page content"):
                            with patch("src.jobs.runner.chunk_markdown",
                                       return_value=["# Page content"]):
                                with patch("src.jobs.runner.needs_llm_cleanup",
                                           return_value=False):
                                    with patch("src.jobs.runner.save_job_state"):
                                        with patch("src.jobs.runner.filter_urls_with_llm",
                                                   return_value=urls):
                                            await run_job(job, resume_urls=urls)

        assert (out / "page1.md").exists()
        assert (out / "page2.md").exists()

    async def test_index_file_created(self, tmp_path):
        urls = ["https://example.com/page1"]
        out = tmp_path / "out"
        request = _make_request(
            output_path=str(out),
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        scraper, converter, robots = self._patch_run_job(tmp_path)

        with patch("src.jobs.runner.validate_models", return_value=[]):
            with patch("src.jobs.runner.PageScraper", return_value=scraper):
                with patch("src.jobs.runner.get_converter", return_value=converter):
                    with patch("src.jobs.runner.RobotsParser", return_value=robots):
                        with patch("src.jobs.runner.fetch_html_fast",
                                   return_value="# Page content"):
                            with patch("src.jobs.runner.chunk_markdown",
                                       return_value=["# Page content"]):
                                with patch("src.jobs.runner.needs_llm_cleanup",
                                           return_value=False):
                                    with patch("src.jobs.runner.save_job_state"):
                                        with patch("src.jobs.runner.filter_urls_with_llm",
                                                   return_value=urls):
                                            await run_job(job, resume_urls=urls)

        assert (out / "_index.md").exists()
```

**Step 2: Run to verify FAIL → PASS.**
```bash
python -m pytest tests/jobs/test_runner.py::TestRunJobHappyPath --no-cov -q
```
Expected: 4 passed

**Step 3: Commit**
```bash
git add tests/jobs/test_runner.py
git commit -m "test(runner): TestRunJobHappyPath — 4 tests for successful full job run"
```

---

### Task 7: TestRunJobCancellation + TestRunJobDiscovery

**Step 1: Write tests**

```python
class TestRunJobCancellation:
    """run_job respects job.is_cancelled during scraping."""

    async def test_cancelled_job_does_not_emit_completed(self, tmp_path):
        urls = ["https://example.com/page1"]
        request = _make_request(
            output_path=str(tmp_path / "out"),
            use_http_fast_path=True,
        )
        job = _make_job(request)
        job.emit_event = AsyncMock()
        job.is_cancelled = True  # pre-cancel before scraping starts

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
                        with patch("src.jobs.runner.fetch_html_fast", return_value="# x"):
                            with patch("src.jobs.runner.chunk_markdown", return_value=["# x"]):
                                with patch("src.jobs.runner.needs_llm_cleanup", return_value=False):
                                    with patch("src.jobs.runner.save_job_state"):
                                        with patch("src.jobs.runner.filter_urls_with_llm",
                                                   return_value=urls):
                                            await run_job(job, resume_urls=urls)

        done_events = [
            c for c in job.emit_event.call_args_list if c.args[0] == "job_done"
        ]
        # When cancelled before scraping loop, no "completed" job_done emitted
        completed = [e for e in done_events if e.args[1].get("status") == "completed"]
        assert completed == []


class TestRunJobDiscovery:
    """run_job calls discover_urls when resume_urls is None."""

    async def test_discovery_called_when_no_resume_urls(self, tmp_path):
        request = _make_request(output_path=str(tmp_path / "out"), use_http_fast_path=True)
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
                        with patch("src.jobs.runner.discover_urls",
                                   return_value=["https://example.com/"]) as mock_disc:
                            with patch("src.jobs.runner.filter_urls",
                                       return_value=["https://example.com/"]):
                                with patch("src.jobs.runner.filter_urls_with_llm",
                                           return_value=["https://example.com/"]):
                                    with patch("src.jobs.runner.fetch_html_fast",
                                               return_value="# content"):
                                        with patch("src.jobs.runner.chunk_markdown",
                                                   return_value=["# content"]):
                                            with patch("src.jobs.runner.needs_llm_cleanup",
                                                       return_value=False):
                                                with patch("src.jobs.runner.save_job_state"):
                                                    await run_job(job)

        mock_disc.assert_awaited_once()

    async def test_filter_urls_called_after_discovery(self, tmp_path):
        request = _make_request(output_path=str(tmp_path / "out"), use_http_fast_path=True)
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
                        with patch("src.jobs.runner.discover_urls",
                                   return_value=["https://example.com/"]):
                            with patch("src.jobs.runner.filter_urls",
                                       return_value=["https://example.com/"]) as mock_filter:
                                with patch("src.jobs.runner.filter_urls_with_llm",
                                           return_value=["https://example.com/"]):
                                    with patch("src.jobs.runner.fetch_html_fast",
                                               return_value="# content"):
                                        with patch("src.jobs.runner.chunk_markdown",
                                                   return_value=["# content"]):
                                            with patch("src.jobs.runner.needs_llm_cleanup",
                                                       return_value=False):
                                                with patch("src.jobs.runner.save_job_state"):
                                                    await run_job(job)

        mock_filter.assert_called_once()
```

**Step 2: Run to verify FAIL → PASS.**
```bash
python -m pytest tests/jobs/test_runner.py::TestRunJobCancellation tests/jobs/test_runner.py::TestRunJobDiscovery --no-cov -q
```
Expected: 3 passed

**Step 3: Commit**
```bash
git add tests/jobs/test_runner.py
git commit -m "test(runner): TestRunJobCancellation + TestRunJobDiscovery — 3 more run_job path tests"
```

---

### Task 8: Verify coverage target reached

**Step 1: Run full suite with coverage**
```bash
python -m pytest tests/ --cov=src/jobs/runner --cov-report=term-missing --no-header -q 2>&1 | grep "runner.py"
```
Expected: `runner.py ... ≥70%`

**Step 2: If below 70%, identify missing lines and add targeted tests for each uncovered block.**

Common gaps to fill:
- `run_job` exception path (outer `except Exception as e`) — patch `scraper.start` to raise
- `run_job` robots.txt crawl-delay path — `request.respect_robots_txt=True`, `robots.crawl_delay=2.0`
- `run_job` safety-net branch (`if job.status == "running"`) — raise in `emit_event` after scraping

**Step 3: Final commit + push**
```bash
git add tests/jobs/test_runner.py
git commit -m "test(runner): reach ≥70% coverage target"
git push -u origin feat/runner-coverage
```

---

### Task 9: Open PR

```bash
gh pr create \
  --title "test(runner): increase coverage from 26% to ≥70%" \
  --body "$(cat <<'EOF'
## Summary

- Add `tests/jobs/test_runner.py` with 7 test classes and 27+ tests
- Coverage: `src/jobs/runner.py` 26% → ≥70% (target 80%)

## Test classes

| Class | What it covers |
|---|---|
| `TestValidateModels` | Ollama exact/base-name match, errors, exception, lmstudio skip |
| `TestLog` | SSE emit, log levels (error/warning/info), model suffix |
| `TestUrlToFilepath` | Root→index, subpath, extension strip, base strip, nested |
| `TestGenerateIndex` | File creation, header, links, Home entry, empty list |
| `TestRunJobModelValidationFail` | Early-exit, failed status, scraper.stop in finally |
| `TestRunJobHappyPath` | status=completed, job_done event, output files, _index.md |
| `TestRunJobCancellation` | Cancelled before scraping → no completed event |
| `TestRunJobDiscovery` | discover_urls + filter_urls called when no resume_urls |

## Approach

All tests use mocks — no real Playwright, HTTP, or LLM calls.
`resume_urls` parameter used for happy-path to skip discovery/filtering mock surface.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
