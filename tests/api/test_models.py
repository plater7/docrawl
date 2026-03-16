"""Tests for src/api/models.py — JobRequest validators, OllamaModel, and JobStatus."""

import logging
import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from src.api.models import JobRequest, OllamaModel, JobStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_request(**kwargs) -> dict:
    """Return a minimal valid JobRequest payload, optionally overriding fields."""
    base = {
        "url": "https://example.com",
        "crawl_model": "model",
        "pipeline_model": "model",
        "reasoning_model": "model",
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# validate_output_path
# ---------------------------------------------------------------------------


class TestValidateOutputPath:
    """Tests for JobRequest.validate_output_path.

    The validator runs Path('/data').joinpath(v).resolve() and checks that the
    result starts with '/data'.  On Windows Path.resolve() returns Windows-style
    paths, so valid-path tests patch Path.resolve to simulate Linux behaviour.
    The traversal-rejection tests rely on the validator raising ValueError, which
    happens whenever str(resolved) does not start with '/data' — always true on
    Windows for non-/data paths too, so no patching is needed there.
    """

    def test_path_traversal_raises_value_error(self):
        """Path traversal via ../../etc/passwd must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(**_minimal_request(output_path="../../etc/passwd"))
        assert "output_path must be under /data" in str(exc_info.value)

    def test_path_traversal_deep_raises(self):
        """Deep traversal attempt that escapes /data must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(**_minimal_request(output_path="output/../../etc/shadow"))
        assert "output_path must be under /data" in str(exc_info.value)

    def test_valid_path_under_data_accepted(self):
        """A path that resolves inside /data must be accepted (Linux simulation)."""
        with patch(
            "src.api.models.Path.resolve",
            return_value=MagicMock(__str__=lambda s: "/data/output"),
        ):
            job = JobRequest(**_minimal_request(output_path="/data/output"))
        assert job.output_path == "/data/output"

    def test_relative_path_under_data_accepted(self):
        """A relative path that stays inside /data must be accepted (Linux simulation)."""
        with patch(
            "src.api.models.Path.resolve",
            return_value=MagicMock(__str__=lambda s: "/data/output/docs"),
        ):
            job = JobRequest(**_minimal_request(output_path="output/docs"))
        assert job.output_path == "/data/output/docs"

    def test_path_outside_data_raises(self):
        """If resolved path is outside /data the validator must raise."""
        with patch(
            "src.api.models.Path.resolve",
            return_value=MagicMock(__str__=lambda s: "/etc/passwd"),
        ):
            with pytest.raises(ValidationError) as exc_info:
                JobRequest(**_minimal_request(output_path="/etc/passwd"))
        assert "output_path must be under /data" in str(exc_info.value)

    def test_default_output_path_accepted(self):
        """Default output_path /data/output is accepted (Linux simulation)."""
        with patch(
            "src.api.models.Path.resolve",
            return_value=MagicMock(__str__=lambda s: "/data/output"),
        ):
            job = JobRequest(**_minimal_request())
        assert job.output_path == "/data/output"


# ---------------------------------------------------------------------------
# validate_proxy_url
# ---------------------------------------------------------------------------


class TestValidateProxyUrl:
    """Tests for JobRequest.validate_proxy_url."""

    def test_none_returns_none(self):
        """None value is passed through as None."""
        job = JobRequest(**_minimal_request(markdown_proxy_url=None))
        assert job.markdown_proxy_url is None

    def test_empty_string_returns_none(self):
        """Empty string is normalised to None."""
        job = JobRequest(**_minimal_request(markdown_proxy_url=""))
        assert job.markdown_proxy_url is None

    def test_http_scheme_raises(self):
        """Non-HTTPS URL must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(**_minimal_request(markdown_proxy_url="http://markdown.new"))
        assert "markdown_proxy_url must use HTTPS" in str(exc_info.value)

    def test_ftp_scheme_raises(self):
        """FTP URL must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(**_minimal_request(markdown_proxy_url="ftp://markdown.new"))
        assert "markdown_proxy_url must use HTTPS" in str(exc_info.value)

    def test_private_ip_127_raises(self):
        """HTTPS URL pointing to 127.x.x.x must be blocked as SSRF."""
        with patch("src.utils.security.socket.gethostbyname", return_value="127.0.0.1"):
            with pytest.raises(ValidationError) as exc_info:
                JobRequest(
                    **_minimal_request(markdown_proxy_url="https://127.0.0.1/proxy")
                )
        assert "private/internal" in str(exc_info.value)

    def test_private_ip_10_raises(self):
        """HTTPS URL whose hostname resolves to 10.x.x.x must be blocked."""
        with patch("src.utils.security.socket.gethostbyname", return_value="10.0.0.1"):
            with pytest.raises(ValidationError) as exc_info:
                JobRequest(
                    **_minimal_request(markdown_proxy_url="https://internal.corp/proxy")
                )
        assert "private/internal" in str(exc_info.value)

    def test_private_ip_192_168_raises(self):
        """HTTPS URL resolving to 192.168.x.x must be blocked."""
        with patch(
            "src.utils.security.socket.gethostbyname", return_value="192.168.1.1"
        ):
            with pytest.raises(ValidationError) as exc_info:
                JobRequest(
                    **_minimal_request(markdown_proxy_url="https://router.local/proxy")
                )
        assert "private/internal" in str(exc_info.value)

    def test_valid_https_url_accepted(self):
        """A valid public HTTPS URL is accepted."""
        with patch("src.utils.security.socket.gethostbyname", return_value="1.2.3.4"):
            job = JobRequest(
                **_minimal_request(markdown_proxy_url="https://markdown.new")
            )
        assert job.markdown_proxy_url == "https://markdown.new"


# ---------------------------------------------------------------------------
# JobRequest defaults
# ---------------------------------------------------------------------------


class TestJobRequestDefaults:
    """Test JobRequest default values."""

    def test_output_path_default(self):
        """output_path should default to /data/output."""
        req = JobRequest(**_minimal_request())
        assert req.output_path == "/data/output"

    def test_delay_ms_default(self):
        """delay_ms should default to 500."""
        req = JobRequest(**_minimal_request())
        assert req.delay_ms == 500

    def test_max_concurrent_default(self):
        """max_concurrent should default to 3."""
        req = JobRequest(**_minimal_request())
        assert req.max_concurrent == 3

    def test_max_depth_default(self):
        """max_depth should default to 5."""
        req = JobRequest(**_minimal_request())
        assert req.max_depth == 5

    def test_respect_robots_txt_default(self):
        """respect_robots_txt should default to True."""
        req = JobRequest(**_minimal_request())
        assert req.respect_robots_txt is True

    def test_use_native_markdown_default(self):
        """use_native_markdown should default to True."""
        req = JobRequest(**_minimal_request())
        assert req.use_native_markdown is True

    def test_use_markdown_proxy_default(self):
        """use_markdown_proxy should default to False."""
        req = JobRequest(**_minimal_request())
        assert req.use_markdown_proxy is False

    def test_language_default(self):
        """language should default to 'en'."""
        req = JobRequest(**_minimal_request())
        assert req.language == "en"

    def test_filter_sitemap_by_path_default(self):
        """filter_sitemap_by_path should default to True."""
        req = JobRequest(**_minimal_request())
        assert req.filter_sitemap_by_path is True

    def test_all_required_fields_accepted(self):
        """All required fields should be accepted without error."""
        req = JobRequest(**_minimal_request())
        assert str(req.url).rstrip("/") == "https://example.com"
        assert req.crawl_model == "model"

    def test_override_defaults(self):
        """Non-default values should override defaults."""
        req = JobRequest(
            **_minimal_request(
                delay_ms=1000,
                max_concurrent=5,
                max_depth=10,
                respect_robots_txt=False,
                language="es",
            )
        )
        assert req.delay_ms == 1000
        assert req.max_concurrent == 5
        assert req.max_depth == 10
        assert req.respect_robots_txt is False
        assert req.language == "es"


# ---------------------------------------------------------------------------
# JobRequest URL validation
# ---------------------------------------------------------------------------


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

    def test_crawl_model_now_optional(self):
        """crawl_model is optional; omitting it is valid (LLM URL filtering is skipped)."""
        # pipeline_model still required when LLM cleanup is needed (default behaviour)
        job = JobRequest(
            url="https://example.com",
            pipeline_model="m",
            reasoning_model="m",
        )
        assert job.crawl_model is None

    def test_missing_pipeline_model_with_llm_cleanup_fails(self):
        """pipeline_model is required when skip_llm_cleanup is False and no ReaderLM converter."""
        with pytest.raises(ValidationError, match="pipeline_model is required"):
            JobRequest(url="https://example.com")

    def test_pipeline_model_not_required_with_skip_llm_cleanup(self):
        """pipeline_model is NOT required when skip_llm_cleanup=True."""
        job = JobRequest(url="https://example.com", skip_llm_cleanup=True)
        assert job.pipeline_model is None

    def test_pipeline_model_not_required_with_readerlm(self):
        """pipeline_model is NOT required when converter='readerlm'."""
        job = JobRequest(url="https://example.com", converter="readerlm")
        assert job.pipeline_model is None


# ---------------------------------------------------------------------------
# OllamaModel
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# JobStatus
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# validate_selectors (content_selectors, noise_selectors)
# ---------------------------------------------------------------------------


class TestValidateSelectors:
    """Tests for JobRequest.validate_selectors."""

    def test_content_selectors_none_default(self):
        """content_selectors should default to None."""
        req = JobRequest(**_minimal_request())
        assert req.content_selectors is None

    def test_noise_selectors_none_default(self):
        """noise_selectors should default to None."""
        req = JobRequest(**_minimal_request())
        assert req.noise_selectors is None

    def test_content_selectors_valid_list(self):
        """A valid list of content selectors should be accepted."""
        req = JobRequest(
            **_minimal_request(
                content_selectors=[".custom-docs", "#main-content", "article.docs"]
            )
        )
        assert req.content_selectors == [
            ".custom-docs",
            "#main-content",
            "article.docs",
        ]

    def test_noise_selectors_valid_list(self):
        """A valid list of noise selectors should be accepted."""
        req = JobRequest(
            **_minimal_request(
                noise_selectors=[".advertisement", "#popup", ".cookie-banner"]
            )
        )
        assert req.noise_selectors == [".advertisement", "#popup", ".cookie-banner"]

    def test_content_selectors_max_20_items(self):
        """More than 20 content selectors should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(
                **_minimal_request(
                    content_selectors=[f".selector{i}" for i in range(21)]
                )
            )
        assert "max 20 items" in str(exc_info.value)

    def test_noise_selectors_max_20_items(self):
        """More than 20 noise selectors should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(
                **_minimal_request(noise_selectors=[f".selector{i}" for i in range(21)])
            )
        assert "max 20 items" in str(exc_info.value)

    def test_content_selector_max_200_chars(self):
        """A selector longer than 200 chars should be rejected."""
        long_selector = ".custom-" + "x" * 200
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(**_minimal_request(content_selectors=[long_selector]))
        assert "too long" in str(exc_info.value)

    def test_noise_selector_max_200_chars(self):
        """A noise selector longer than 200 chars should be rejected."""
        long_selector = ".noise-" + "x" * 200
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(**_minimal_request(noise_selectors=[long_selector]))
        assert "too long" in str(exc_info.value)


# ---------------------------------------------------------------------------
# validate_selectors — unsafe character rejection (Issue #177)
# ---------------------------------------------------------------------------


class TestValidateSelectorsUnsafeChars:
    """Selectors with backtick or braces must be rejected to prevent JS template literal injection."""

    def test_content_selector_with_backtick_raises(self):
        """Selector containing backtick must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(**_minimal_request(content_selectors=[".foo`; evilCode(); `"]))
        assert "unsafe characters" in str(exc_info.value)

    def test_noise_selector_with_backtick_raises(self):
        """Noise selector containing backtick must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(**_minimal_request(noise_selectors=[".bar`injection`"]))
        assert "unsafe characters" in str(exc_info.value)

    def test_selector_with_open_brace_raises(self):
        """Selector containing '{' must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(**_minimal_request(content_selectors=[".cls{color:red}"]))
        assert "unsafe characters" in str(exc_info.value)

    def test_selector_with_close_brace_raises(self):
        """Selector containing '}' must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            JobRequest(**_minimal_request(content_selectors=[".cls}"]))
        assert "unsafe characters" in str(exc_info.value)

    def test_normal_selector_no_backtick_accepted(self):
        """Normal CSS selectors without unsafe chars must be accepted."""
        req = JobRequest(
            **_minimal_request(
                content_selectors=[".main-content", "#article", "div.docs > p"]
            )
        )
        assert req.content_selectors == [".main-content", "#article", "div.docs > p"]

    def test_selector_with_brackets_accepted(self):
        """Attribute selectors using [] are safe and must be accepted."""
        req = JobRequest(
            **_minimal_request(content_selectors=["[data-testid='main']", "a[href]"])
        )
        assert len(req.content_selectors) == 2


# ---------------------------------------------------------------------------
# validate_models_required — skip_llm_cleanup warning (Issue #178)
# ---------------------------------------------------------------------------


class TestSkipLlmCleanupWarning:
    """skip_llm_cleanup=True on a non-ReaderLM job should emit a warning."""

    def test_skip_llm_cleanup_non_readerlm_logs_warning(self, caplog):
        """Warning must be logged when skip_llm_cleanup=True and converter is not ReaderLM."""
        with caplog.at_level(logging.WARNING, logger="src.api.models"):
            JobRequest(url="https://example.com", skip_llm_cleanup=True)
        assert any("skip_llm_cleanup=True" in r.message for r in caplog.records)

    def test_skip_llm_cleanup_with_readerlm_no_warning(self, caplog):
        """No warning must be emitted when converter='readerlm' (expected usage)."""
        with caplog.at_level(logging.WARNING, logger="src.api.models"):
            JobRequest(url="https://example.com", converter="readerlm")
        assert not any("skip_llm_cleanup" in r.message for r in caplog.records)

    def test_skip_llm_cleanup_with_readerlm_v1_no_warning(self, caplog):
        """No warning must be emitted when converter='readerlm-v1'."""
        with caplog.at_level(logging.WARNING, logger="src.api.models"):
            JobRequest(url="https://example.com", converter="readerlm-v1")
        assert not any("skip_llm_cleanup" in r.message for r in caplog.records)

    def test_skip_llm_cleanup_false_no_warning(self, caplog):
        """No warning must be emitted when skip_llm_cleanup=False (default)."""
        with caplog.at_level(logging.WARNING, logger="src.api.models"):
            JobRequest(**_minimal_request())
        assert not any("skip_llm_cleanup" in r.message for r in caplog.records)
