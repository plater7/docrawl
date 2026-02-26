"""
Unit tests for src/llm/filter.py — filter_urls_with_llm()

Tests cover:
- Empty list returns empty list immediately (no LLM call)
- LLM returns valid JSON array → filtered URLs returned
- LLM returns JSON in markdown code block → correctly parsed
- LLM returns invalid JSON → falls back to original list
- LLM raises exception → falls back to original list
- LLM returns URLs not in original → only valid (intersection) URLs returned
"""

import pytest
from unittest.mock import patch, AsyncMock

from src.llm.filter import filter_urls_with_llm


SAMPLE_URLS = [
    "https://docs.example.com/guide/intro",
    "https://docs.example.com/guide/install",
    "https://docs.example.com/reference/api",
]


class TestFilterUrlsWithLlmEmptyInput:
    """Empty input should short-circuit without calling the LLM."""

    async def test_empty_list_returns_empty_immediately(self):
        """Empty URL list returns [] without any LLM call."""
        with patch("src.llm.filter.generate") as mock_generate:
            result = await filter_urls_with_llm([], "mistral:7b")
        assert result == []
        mock_generate.assert_not_called()


class TestFilterUrlsWithLlmValidJson:
    """LLM returns a valid JSON array."""

    async def test_valid_json_array_returned(self):
        """Valid JSON list from LLM is returned as-is (filtered to originals)."""
        subset = SAMPLE_URLS[:2]
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            return_value=f'["{subset[0]}", "{subset[1]}"]',
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert result == subset

    async def test_all_urls_returned_if_llm_keeps_all(self):
        """LLM keeping all URLs returns the full list."""
        import json
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            return_value=json.dumps(SAMPLE_URLS),
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert result == SAMPLE_URLS

    async def test_single_url_returned(self):
        """LLM returning a single URL list is handled correctly."""
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            return_value=f'["{SAMPLE_URLS[0]}"]',
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert result == [SAMPLE_URLS[0]]


class TestFilterUrlsWithLlmMarkdownCodeBlock:
    """LLM returns JSON wrapped in a markdown code block."""

    async def test_json_in_backtick_block_parsed(self):
        """```json ... ``` wrapper is stripped before JSON parsing."""
        import json
        markdown_response = "```json\n" + json.dumps(SAMPLE_URLS[:2]) + "\n```"
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            return_value=markdown_response,
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert result == SAMPLE_URLS[:2]

    async def test_json_in_plain_backtick_block_parsed(self):
        """``` ... ``` wrapper (no 'json') is stripped before JSON parsing."""
        import json
        markdown_response = "```\n" + json.dumps(SAMPLE_URLS[:1]) + "\n```"
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            return_value=markdown_response,
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert result == SAMPLE_URLS[:1]


class TestFilterUrlsWithLlmInvalidJson:
    """LLM returns invalid JSON → falls back to original list."""

    async def test_invalid_json_falls_back_to_original(self):
        """Non-JSON response causes fallback to the original URL list."""
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            return_value="Sorry, I cannot filter these URLs.",
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert result == SAMPLE_URLS

    async def test_truncated_json_falls_back_to_original(self):
        """Truncated JSON response causes fallback."""
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            return_value='["https://docs.example.com/guide/intro",',
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert result == SAMPLE_URLS

    async def test_json_object_not_array_falls_back(self):
        """JSON object (not array) causes fallback to original list."""
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            return_value='{"urls": ["https://docs.example.com/guide/intro"]}',
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert result == SAMPLE_URLS


class TestFilterUrlsWithLlmException:
    """LLM raises exception → falls back to original list."""

    async def test_exception_falls_back_to_original(self):
        """Exception from generate() causes fallback to original URL list."""
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM unavailable"),
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert result == SAMPLE_URLS

    async def test_timeout_exception_falls_back_to_original(self):
        """Timeout from generate() causes fallback."""
        import httpx
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert result == SAMPLE_URLS


class TestFilterUrlsWithLlmIntersection:
    """Only URLs that appear in the original list are returned."""

    async def test_urls_not_in_original_excluded(self):
        """URLs hallucinated by LLM (not in input) are dropped."""
        hallucinated_url = "https://docs.example.com/hallucinated"
        llm_response = f'["{SAMPLE_URLS[0]}", "{hallucinated_url}"]'
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert hallucinated_url not in result
        assert SAMPLE_URLS[0] in result

    async def test_all_hallucinated_urls_returns_empty(self):
        """If LLM returns only hallucinated URLs, result is empty list."""
        llm_response = '["https://totally.different.com/page"]'
        with patch(
            "src.llm.filter.generate",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await filter_urls_with_llm(SAMPLE_URLS, "mistral:7b")

        assert result == []
