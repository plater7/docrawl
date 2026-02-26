"""Tests for src/utils/security.py — validate_url_not_ssrf."""

import socket
import pytest
from unittest.mock import patch

from src.utils.security import validate_url_not_ssrf


class TestValidateUrlNotSsrf:
    """Unit tests for validate_url_not_ssrf."""

    # ------------------------------------------------------------------
    # Cases that must raise ValueError
    # ------------------------------------------------------------------

    def test_no_hostname_raises(self):
        """URL without a hostname must raise ValueError."""
        with pytest.raises(ValueError, match="no hostname"):
            validate_url_not_ssrf("https://")

    def test_loopback_127_raises(self):
        """Direct loopback IP 127.0.0.1 must be blocked."""
        with patch("src.utils.security.socket.gethostbyname", return_value="127.0.0.1"):
            with pytest.raises(ValueError, match="private/internal"):
                validate_url_not_ssrf("http://127.0.0.1/admin")

    def test_loopback_127_x_raises(self):
        """Any 127.x.x.x address must be blocked (full /8 range)."""
        with patch("src.utils.security.socket.gethostbyname", return_value="127.0.0.2"):
            with pytest.raises(ValueError, match="private/internal"):
                validate_url_not_ssrf("http://127.0.0.2/")

    def test_link_local_raises(self):
        """Link-local address 169.254.x.x (cloud metadata) must be blocked."""
        with patch(
            "src.utils.security.socket.gethostbyname", return_value="169.254.169.254"
        ):
            with pytest.raises(ValueError, match="private/internal"):
                validate_url_not_ssrf("http://169.254.169.254/latest/meta-data/")

    def test_private_10_raises(self):
        """10.x.x.x RFC-1918 address must be blocked."""
        with patch("src.utils.security.socket.gethostbyname", return_value="10.0.0.1"):
            with pytest.raises(ValueError, match="private/internal"):
                validate_url_not_ssrf("http://internal.corp/api")

    def test_private_192_168_raises(self):
        """192.168.x.x RFC-1918 address must be blocked."""
        with patch(
            "src.utils.security.socket.gethostbyname", return_value="192.168.1.100"
        ):
            with pytest.raises(ValueError, match="private/internal"):
                validate_url_not_ssrf("http://router.local/")

    def test_private_172_16_raises(self):
        """172.16.x.x RFC-1918 address must be blocked."""
        with patch(
            "src.utils.security.socket.gethostbyname", return_value="172.16.0.1"
        ):
            with pytest.raises(ValueError, match="private/internal"):
                validate_url_not_ssrf("http://172.16.0.1/")

    # ------------------------------------------------------------------
    # Cases that must NOT raise (pass silently)
    # ------------------------------------------------------------------

    def test_public_ip_passes(self):
        """Public IP address must not raise."""
        with patch("src.utils.security.socket.gethostbyname", return_value="8.8.8.8"):
            # Should not raise
            validate_url_not_ssrf("https://dns.google/")

    def test_public_ip_non_google_passes(self):
        """Another public IP must not raise."""
        with patch("src.utils.security.socket.gethostbyname", return_value="1.1.1.1"):
            validate_url_not_ssrf("https://one.one.one.one/")

    def test_dns_gaierror_passes(self):
        """If DNS resolution fails (gaierror), the function must pass silently."""
        with patch(
            "src.utils.security.socket.gethostbyname",
            side_effect=socket.gaierror("Name or service not known"),
        ):
            # Must not raise — DNS failure is allowed to pass through
            validate_url_not_ssrf("https://nonexistent.invalid/page")

    def test_url_with_path_and_public_ip_passes(self):
        """Full URL with path resolving to a public IP must pass."""
        with patch(
            "src.utils.security.socket.gethostbyname", return_value="93.184.216.34"
        ):
            validate_url_not_ssrf("https://example.com/some/path?q=1")
