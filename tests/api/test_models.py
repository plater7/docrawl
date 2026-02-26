"""
Unit tests for src/api/models.py

Tests cover:
- JobRequest field defaults and validation
- OllamaModel field defaults
- JobStatus field defaults
"""

import pytest
from pydantic import ValidationError

from src.api.models import JobRequest, OllamaModel, JobStatus


class TestJobRequestDefaults:
    """Test JobRequest default values."""

    def _minimal_request(self, **overrides) -> dict:
        """Return a minimal valid payload with all required fields."""
        base = {
            "url": "https://example.com",
            "crawl_model": "mistral:7b",
            "pipeline_model": "qwen3:14b",
            "reasoning_model": "deepseek-r1:32b",
        }
        base.update(overrides)
        return base

    def test_output_path_default(self):
        """output_path should default to /data/output."""
        req = JobRequest(**self._minimal_request())
        assert req.output_path == "/data/output"

    def test_delay_ms_default(self):
        """delay_ms should default to 500."""
        req = JobRequest(**self._minimal_request())
        assert req.delay_ms == 500

    def test_max_concurrent_default(self):
        """max_concurrent should default to 3."""
        req = JobRequest(**self._minimal_request())
        assert req.max_concurrent == 3

    def test_max_depth_default(self):
        """max_depth should default to 5."""
        req = JobRequest(**self._minimal_request())
        assert req.max_depth == 5

    def test_respect_robots_txt_default(self):
        """respect_robots_txt should default to True."""
        req = JobRequest(**self._minimal_request())
        assert req.respect_robots_txt is True

    def test_use_native_markdown_default(self):
        """use_native_markdown should default to True."""
        req = JobRequest(**self._minimal_request())
        assert req.use_native_markdown is True

    def test_use_markdown_proxy_default(self):
        """use_markdown_proxy should default to False."""
        req = JobRequest(**self._minimal_request())
        assert req.use_markdown_proxy is False

    def test_language_default(self):
        """language should default to 'en'."""
        req = JobRequest(**self._minimal_request())
        assert req.language == "en"

    def test_filter_sitemap_by_path_default(self):
        """filter_sitemap_by_path should default to True."""
        req = JobRequest(**self._minimal_request())
        assert req.filter_sitemap_by_path is True

    def test_all_required_fields_accepted(self):
        """All required fields should be accepted without error."""
        req = JobRequest(**self._minimal_request())
        assert str(req.url).rstrip("/") == "https://example.com"
        assert req.crawl_model == "mistral:7b"
        assert req.pipeline_model == "qwen3:14b"
        assert req.reasoning_model == "deepseek-r1:32b"

    def test_override_defaults(self):
        """Non-default values should override defaults."""
        req = JobRequest(
            **self._minimal_request(
                output_path="/custom/path",
                delay_ms=1000,
                max_concurrent=5,
                max_depth=10,
                respect_robots_txt=False,
                language="es",
            )
        )
        assert req.output_path == "/custom/path"
        assert req.delay_ms == 1000
        assert req.max_concurrent == 5
        assert req.max_depth == 10
        assert req.respect_robots_txt is False
        assert req.language == "es"


class TestJobRequestValidation:
    """Test JobRequest URL validation."""

    def test_valid_http_url(self):
        """HTTP URL should be accepted."""
        req = JobRequest(
            url="http://example.com",
            crawl_model="m",
            pipeline_model="m",
            reasoning_model="m",
        )
        assert "example.com" in str(req.url)

    def test_valid_https_url(self):
        """HTTPS URL should be accepted."""
        req = JobRequest(
            url="https://docs.example.com/guide",
            crawl_model="m",
            pipeline_model="m",
            reasoning_model="m",
        )
        assert "docs.example.com" in str(req.url)

    def test_invalid_url_no_scheme(self):
        """URL without scheme should fail validation."""
        with pytest.raises(ValidationError):
            JobRequest(
                url="example.com",
                crawl_model="m",
                pipeline_model="m",
                reasoning_model="m",
            )

    def test_invalid_url_empty_string(self):
        """Empty string URL should fail validation."""
        with pytest.raises(ValidationError):
            JobRequest(
                url="",
                crawl_model="m",
                pipeline_model="m",
                reasoning_model="m",
            )

    def test_invalid_url_plain_text(self):
        """Plain text as URL should fail validation."""
        with pytest.raises(ValidationError):
            JobRequest(
                url="not-a-url",
                crawl_model="m",
                pipeline_model="m",
                reasoning_model="m",
            )

    def test_missing_required_url_field(self):
        """Missing required url field should fail validation."""
        with pytest.raises(ValidationError):
            JobRequest(
                crawl_model="m",
                pipeline_model="m",
                reasoning_model="m",
            )

    def test_missing_required_crawl_model(self):
        """Missing required crawl_model should fail validation."""
        with pytest.raises(ValidationError):
            JobRequest(
                url="https://example.com",
                pipeline_model="m",
                reasoning_model="m",
            )


class TestOllamaModelDefaults:
    """Test OllamaModel default values."""

    def test_provider_default(self):
        """provider should default to 'ollama'."""
        model = OllamaModel(name="mistral:7b")
        assert model.provider == "ollama"

    def test_is_free_default(self):
        """is_free should default to True."""
        model = OllamaModel(name="mistral:7b")
        assert model.is_free is True

    def test_size_default_is_none(self):
        """size should default to None."""
        model = OllamaModel(name="mistral:7b")
        assert model.size is None

    def test_name_is_required(self):
        """name is a required field."""
        with pytest.raises(ValidationError):
            OllamaModel()

    def test_size_can_be_set(self):
        """size can be set to an integer."""
        model = OllamaModel(name="llama3:8b", size=4_000_000_000)
        assert model.size == 4_000_000_000

    def test_provider_can_be_overridden(self):
        """provider can be overridden."""
        model = OllamaModel(name="gpt-4", provider="openrouter", is_free=False)
        assert model.provider == "openrouter"
        assert model.is_free is False


class TestJobStatusDefaults:
    """Test JobStatus default values."""

    def test_pages_completed_default(self):
        """pages_completed should default to 0."""
        status = JobStatus(id="abc-123", status="pending")
        assert status.pages_completed == 0

    def test_pages_total_default(self):
        """pages_total should default to 0."""
        status = JobStatus(id="abc-123", status="pending")
        assert status.pages_total == 0

    def test_current_url_default_is_none(self):
        """current_url should default to None."""
        status = JobStatus(id="abc-123", status="pending")
        assert status.current_url is None

    def test_id_and_status_are_required(self):
        """id and status are required fields."""
        with pytest.raises(ValidationError):
            JobStatus(status="pending")
        with pytest.raises(ValidationError):
            JobStatus(id="abc-123")

    def test_current_url_can_be_set(self):
        """current_url can be set to a string."""
        status = JobStatus(
            id="abc-123",
            status="running",
            pages_completed=5,
            pages_total=100,
            current_url="https://example.com/page5",
        )
        assert status.current_url == "https://example.com/page5"
        assert status.pages_completed == 5
        assert status.pages_total == 100
