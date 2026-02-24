"""Tests for markdown content negotiation and proxy fallback."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch

from src.scraper.page import fetch_markdown_native, fetch_markdown_proxy
from src.scraper.markdown import chunk_markdown


@pytest.mark.asyncio
async def test_fetch_markdown_native_returns_none_for_html():
    """fetch_markdown_native returns (None, None) when server responds with text/html."""
    mock_response = httpx.Response(
        200,
        headers={"content-type": "text/html; charset=utf-8"},
        text="<html><body>Hello</body></html>",
        request=httpx.Request("GET", "https://example.com"),
    )
    with patch("src.scraper.page.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        content, token_count = await fetch_markdown_native("https://example.com")
        assert content is None
        assert token_count is None


@pytest.mark.asyncio
async def test_fetch_markdown_native_returns_content_for_markdown():
    """fetch_markdown_native returns content and token count for CF-enabled sites."""
    mock_response = httpx.Response(
        200,
        headers={
            "content-type": "text/markdown; charset=utf-8",
            "x-markdown-tokens": "150",
        },
        text="# Hello World\n\nThis is markdown content.",
        request=httpx.Request("GET", "https://docs.cloudflare.com/test"),
    )
    with patch("src.scraper.page.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        content, token_count = await fetch_markdown_native(
            "https://docs.cloudflare.com/test"
        )
        assert content == "# Hello World\n\nThis is markdown content."
        assert token_count == 150


@pytest.mark.asyncio
async def test_fetch_markdown_native_handles_timeout():
    """fetch_markdown_native returns (None, None) on timeout."""
    with patch("src.scraper.page.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.get.side_effect = httpx.TimeoutException("timed out")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        content, token_count = await fetch_markdown_native("https://slow-site.com")
        assert content is None
        assert token_count is None


@pytest.mark.asyncio
async def test_fetch_markdown_proxy_returns_content():
    """fetch_markdown_proxy returns content from proxy service."""
    mock_response = httpx.Response(
        200,
        text="# Proxied Content\n\nThis was converted by the proxy service with enough content to pass the length check.",
        request=httpx.Request("GET", "https://markdown.new/https://example.com"),
    )
    with patch("src.scraper.page.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        content, _ = await fetch_markdown_proxy(
            "https://example.com", "https://markdown.new"
        )
        assert content is not None
        assert "Proxied Content" in content


def test_chunk_markdown_uses_native_token_count():
    """When native_token_count is small enough, chunk_markdown returns a single chunk."""
    text = "# Title\n\nSome content that is definitely long enough to be a valid chunk."
    # 50 tokens * 4 = 200 chars, which is <= DEFAULT_CHUNK_SIZE (16000)
    chunks = chunk_markdown(text, native_token_count=50)
    assert len(chunks) == 1
    assert chunks[0] == text
