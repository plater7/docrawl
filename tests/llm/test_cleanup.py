"""
Unit tests for src/llm/cleanup.py

Tests cover:
- needs_llm_cleanup(): noise indicators, code block density, length threshold
- _cleanup_options(): num_predict formula, num_ctx hardcoded value
- _calculate_timeout(): small content → BASE_TIMEOUT, large → MAX_TIMEOUT cap
- cleanup_markdown(): success, empty response retries and falls back, all retries fail
"""

from unittest.mock import patch, AsyncMock

from src.llm.cleanup import (
    needs_llm_cleanup,
    _cleanup_options,
    _calculate_timeout,
    cleanup_markdown,
    BASE_TIMEOUT,
    MAX_TIMEOUT,
)


class TestNeedsLlmCleanup:
    """Test needs_llm_cleanup() logic."""

    def test_short_clean_text_returns_false(self):
        """Text shorter than 2000 chars with no noise returns False."""
        short_text = "# Introduction\n\nThis is a short doc page with some content."
        assert len(short_text) < 2000
        assert needs_llm_cleanup(short_text) is False

    def test_text_with_cookie_noise_returns_true(self):
        """Text containing 'cookie' noise indicator returns True."""
        noisy_text = "Accept cookie policy before continuing."
        assert needs_llm_cleanup(noisy_text) is True

    def test_text_with_privacy_policy_noise_returns_true(self):
        """Text containing 'privacy policy' returns True."""
        noisy_text = "Read our privacy policy for details."
        assert needs_llm_cleanup(noisy_text) is True

    def test_text_with_on_this_page_noise_returns_true(self):
        """Text containing 'on this page' returns True."""
        noisy_text = "On this page you will find information."
        assert needs_llm_cleanup(noisy_text) is True

    def test_text_mostly_code_blocks_returns_false(self):
        """Text where >60% is code blocks does not need cleanup."""
        code_block = "```python\n" + "x = 1\n" * 200 + "```"
        tiny_prose = "Some text."
        text = code_block + "\n" + tiny_prose
        # code_block dominates (>60%)
        assert needs_llm_cleanup(text) is False

    def test_long_text_without_noise_or_code_returns_true(self):
        """Long text (>2000 chars) without noise or code returns True."""
        long_text = "This is a documentation paragraph. " * 60
        assert len(long_text) >= 2000
        assert needs_llm_cleanup(long_text) is True

    def test_noise_indicator_case_insensitive(self):
        """Noise check is case-insensitive."""
        assert needs_llm_cleanup("Accept Cookies to continue browsing.") is True
        assert needs_llm_cleanup("COOKIE settings available here.") is True

    def test_powered_by_noise_returns_true(self):
        """Text containing 'powered by' returns True."""
        assert needs_llm_cleanup("Powered by Docusaurus v3.") is True

    def test_all_rights_reserved_noise_returns_true(self):
        """Text containing 'all rights reserved' returns True."""
        assert needs_llm_cleanup("Copyright 2024. All rights reserved.") is True


class TestCleanupOptions:
    """Test _cleanup_options() calculation."""

    def test_num_ctx_is_8192(self):
        """num_ctx should always be 8192."""
        opts = _cleanup_options("any content")
        assert opts["num_ctx"] == 8192

    def test_num_predict_formula_small_content(self):
        """num_predict = min(len(md)//4 + 512, 4096) for small content."""
        markdown = "x" * 400  # 400 chars → 100 estimated tokens
        opts = _cleanup_options(markdown)
        expected = min(400 // 4 + 512, 4096)
        assert opts["num_predict"] == expected

    def test_num_predict_formula_large_content(self):
        """num_predict is capped at 4096 for large content."""
        markdown = "x" * 20000  # 20000 chars → 5000 tokens → capped
        opts = _cleanup_options(markdown)
        assert opts["num_predict"] == 4096

    def test_num_predict_formula_medium_content(self):
        """num_predict for medium content follows the formula."""
        markdown = "x" * 8000  # 8000 chars → 2000 tokens + 512 = 2512
        opts = _cleanup_options(markdown)
        expected = min(8000 // 4 + 512, 4096)
        assert opts["num_predict"] == expected

    def test_temperature_is_low(self):
        """temperature should be set for deterministic cleanup."""
        opts = _cleanup_options("some markdown")
        assert opts["temperature"] == 0.1


class TestCalculateTimeout:
    """Test _calculate_timeout() dynamic timeout logic."""

    def test_empty_content_returns_base_timeout(self):
        """Empty content should yield BASE_TIMEOUT."""
        result = _calculate_timeout("")
        assert result == BASE_TIMEOUT

    def test_small_content_returns_near_base_timeout(self):
        """Small content (< 1KB) should return a timeout close to BASE_TIMEOUT."""
        small_content = "x" * 500  # 0.5 KB → int(45 + 0.488 * 10) = 49
        result = _calculate_timeout(small_content)
        assert BASE_TIMEOUT <= result < MAX_TIMEOUT

    def test_large_content_capped_at_max_timeout(self):
        """Very large content should be capped at MAX_TIMEOUT."""
        huge_content = "x" * 100_000  # ~97 KB
        result = _calculate_timeout(huge_content)
        assert result == MAX_TIMEOUT

    def test_medium_content_between_bounds(self):
        """Medium content timeout is between BASE and MAX."""
        # 5 KB → BASE + 5 * TIMEOUT_PER_KB = 45 + 50 = 95 → capped at 90
        medium = "x" * 5_000
        result = _calculate_timeout(medium)
        assert BASE_TIMEOUT <= result <= MAX_TIMEOUT

    def test_timeout_is_integer(self):
        """Returned timeout is an int."""
        result = _calculate_timeout("some content")
        assert isinstance(result, int)


class TestCleanupMarkdown:
    """Test cleanup_markdown() with mocked generate()."""

    async def test_successful_cleanup_returns_cleaned_text(self):
        """Successful generate() returns the cleaned (stripped) text."""
        original = "# Title\n\ncookie policy foo bar"
        cleaned = "# Title\n\nFoo bar."

        with patch(
            "src.llm.cleanup.generate",
            new_callable=AsyncMock,
            return_value=f"  {cleaned}  ",
        ):
            result = await cleanup_markdown(original, "mistral:7b")

        assert result == cleaned

    async def test_empty_response_retries(self):
        """Empty response triggers retry; fallback to original after all retries."""
        original = "Some content."

        with patch(
            "src.llm.cleanup.generate",
            new_callable=AsyncMock,
            return_value="   ",  # whitespace-only = falsy after strip
        ) as mock_gen:
            result = await cleanup_markdown(original, "mistral:7b")

        # All retries exhausted → returns original
        assert result == original
        # Should have been called MAX_RETRIES times (2)
        assert mock_gen.call_count == 2

    async def test_exception_retries_and_falls_back(self):
        """Exception on every attempt causes fallback to original markdown."""
        original = "Important documentation content."

        with patch(
            "src.llm.cleanup.generate",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM down"),
        ) as mock_gen:
            # Speed up retry backoff for tests
            with patch("src.llm.cleanup.asyncio.sleep", new_callable=AsyncMock):
                result = await cleanup_markdown(original, "mistral:7b")

        assert result == original
        assert mock_gen.call_count == 2  # MAX_RETRIES = 2

    async def test_first_attempt_fails_second_succeeds(self):
        """If first attempt fails but second succeeds, returns cleaned text."""
        original = "Noisy content here."
        cleaned = "Cleaned content here."

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first attempt fails")
            return cleaned

        with patch("src.llm.cleanup.generate", side_effect=side_effect):
            with patch("src.llm.cleanup.asyncio.sleep", new_callable=AsyncMock):
                result = await cleanup_markdown(original, "mistral:7b")

        assert result == cleaned
        assert call_count == 2

    async def test_cleanup_passes_model_to_generate(self):
        """cleanup_markdown passes the correct model name to generate()."""
        with patch(
            "src.llm.cleanup.generate",
            new_callable=AsyncMock,
            return_value="cleaned",
        ) as mock_gen:
            await cleanup_markdown("some markdown", "qwen3:14b")

        call_args = mock_gen.call_args
        assert call_args.args[0] == "qwen3:14b"

    async def test_cleanup_strips_whitespace_from_response(self):
        """Cleaned text has leading/trailing whitespace stripped."""
        with patch(
            "src.llm.cleanup.generate",
            new_callable=AsyncMock,
            return_value="\n\n  Cleaned docs.  \n\n",
        ):
            result = await cleanup_markdown("original", "mistral:7b")

        assert result == "Cleaned docs."
