"""Unit tests for is_blocked_response() and content_hash() (PR 2.3).

Source: src/scraper/detection.py
"""

import hashlib
import re


from src.scraper.detection import content_hash, is_blocked_response


class TestIsBlockedResponse:
    """Tests for is_blocked_response() — bot-check / blocked-page detection."""

    def test_returns_true_when_two_or_more_patterns_match(self):
        """Returns True when at least 2 of the 8 patterns are found in the content.

        'checking your browser' and 'captcha' both match, so threshold is met.
        """
        content = (
            "Checking your browser before accessing the site. "
            "Please complete the captcha to continue."
        )
        assert is_blocked_response(content) is True

    def test_returns_true_for_cloudflare_ddos_protection_page(self):
        """Returns True for a typical Cloudflare challenge page with multiple signals."""
        content = (
            "DDoS protection by Cloudflare. Just a moment... Checking your browser."
        )
        assert is_blocked_response(content) is True

    def test_returns_false_for_single_pattern_match(self):
        """Returns False when only one pattern matches.

        Security documentation that merely mentions Cloudflare should not be flagged.
        """
        content = (
            "This guide explains how Cloudflare handles TLS termination. "
            "No other bot-check signals are present."
        )
        assert is_blocked_response(content) is False

    def test_returns_false_for_empty_string(self):
        """Returns False for an empty content string."""
        assert is_blocked_response("") is False

    def test_returns_false_for_normal_documentation_content(self):
        """Returns False for a typical documentation page with no blocked-response signals."""
        content = (
            "# Getting Started\n\n"
            "Install the package with `pip install mylib`.\n\n"
            "## Configuration\n\nSet the API key in your environment."
        )
        assert is_blocked_response(content) is False

    def test_returns_true_for_access_denied_with_ray_id(self):
        """Returns True when 'access denied' and 'ray id' both appear."""
        content = "Access Denied. Ray ID: abc123def456."
        assert is_blocked_response(content) is True

    def test_case_insensitive_matching(self):
        """Pattern matching is case-insensitive."""
        content = "CHECKING YOUR BROWSER — PLEASE ENABLE JAVASCRIPT to proceed."
        assert is_blocked_response(content) is True


class TestContentHash:
    """Tests for content_hash() — MD5-based deduplication hash."""

    def test_returns_same_hash_for_identical_content(self):
        """Two calls with identical markdown strings must return the same hash."""
        md = "# Title\n\nSome paragraph text here."
        assert content_hash(md) == content_hash(md)

    def test_returns_different_hash_for_different_content(self):
        """Different markdown content must produce different hashes."""
        md1 = "# Page One\n\nContent A."
        md2 = "# Page Two\n\nContent B."
        assert content_hash(md1) != content_hash(md2)

    def test_normalises_extra_spaces_to_same_hash(self):
        """Extra whitespace is normalised, so both strings produce the same hash."""
        md_normal = "some text here"
        md_extra_spaces = "some   text    here"
        assert content_hash(md_normal) == content_hash(md_extra_spaces)

    def test_normalises_newlines_to_same_hash(self):
        """Newlines are collapsed to spaces during normalisation."""
        md_newlines = "some\ntext\nhere"
        md_spaces = "some text here"
        assert content_hash(md_newlines) == content_hash(md_spaces)

    def test_case_insensitive_normalisation(self):
        """Content hash is case-insensitive (content is lowercased before hashing)."""
        assert content_hash("Hello World") == content_hash("hello world")
        assert content_hash("HELLO WORLD") == content_hash("hello world")

    def test_returns_32_char_hex_string(self):
        """The hash is a 32-character hexadecimal MD5 digest."""
        result = content_hash("anything")
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_matches_manual_md5_computation(self):
        """The returned hash equals a manually computed MD5 of the normalised text."""
        markdown = "  Hello   World  "
        normalised = re.sub(r"\s+", " ", markdown.strip().lower())
        expected = hashlib.md5(normalised.encode("utf-8")).hexdigest()
        assert content_hash(markdown) == expected
