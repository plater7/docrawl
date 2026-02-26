"""Tests for JobRequest Pydantic validators in src/api/models.py."""

import pytest
from pathlib import PurePosixPath, PosixPath
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from src.api.models import JobRequest


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


def _mock_resolve_under_data(path_instance):
    """Return a mock Path whose str() starts with '/data', simulating Linux resolution."""
    mock_path = MagicMock()
    mock_path.__str__ = MagicMock(return_value="/data/output")
    return mock_path


def _mock_resolve_outside_data(path_instance):
    """Return a mock Path whose str() does NOT start with '/data'."""
    mock_path = MagicMock()
    mock_path.__str__ = MagicMock(return_value="/etc/passwd")
    return mock_path


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
        # socket.gethostbyname for 127.0.0.1 returns itself without DNS,
        # but we patch to be explicit and portable.
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
