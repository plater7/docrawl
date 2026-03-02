"""Unit tests for parallel BFS discovery (src/crawler/discovery.py) — PR 1.4."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


from src.crawler.discovery import _extract_links, recursive_crawl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    html: str = "", status: int = 200, content_type: str = "text/html"
) -> MagicMock:
    """Return a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status
    resp.text = html
    resp.headers = {"content-type": content_type}
    return resp


def _make_client(response: MagicMock) -> AsyncMock:
    """Return a mock httpx.AsyncClient whose get() returns the given response."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# TestExtractLinks
# ---------------------------------------------------------------------------


class TestExtractLinks:
    """Tests for _extract_links() — per-URL parallel fetcher."""

    async def test_returns_same_domain_links(self):
        """_extract_links() should return links that share the same domain."""
        html = '<a href="https://example.com/page1">Link</a>'
        client = _make_client(_make_response(html))
        sem = asyncio.Semaphore(10)

        links = await _extract_links(
            "https://example.com/", "example.com", client, sem, jitter=False
        )

        assert "https://example.com/page1" in links

    async def test_ignores_external_links(self):
        """Links to other domains must not be included."""
        html = '<a href="https://other.com/page">External</a>'
        client = _make_client(_make_response(html))
        sem = asyncio.Semaphore(10)

        links = await _extract_links(
            "https://example.com/", "example.com", client, sem, jitter=False
        )

        assert links == []

    async def test_ignores_javascript_and_mailto(self):
        """javascript:, mailto:, tel:, and anchor (#) hrefs are skipped."""
        html = """
        <a href="javascript:void(0)">JS</a>
        <a href="mailto:a@b.com">Email</a>
        <a href="#section">Anchor</a>
        <a href="tel:+1234">Phone</a>
        """
        client = _make_client(_make_response(html))
        sem = asyncio.Semaphore(10)

        links = await _extract_links(
            "https://example.com/", "example.com", client, sem, jitter=False
        )

        assert links == []

    async def test_returns_empty_list_on_404(self):
        """A 404 response should yield an empty link list."""
        client = _make_client(_make_response(status=404))
        sem = asyncio.Semaphore(10)

        links = await _extract_links(
            "https://example.com/missing", "example.com", client, sem, jitter=False
        )

        assert links == []

    async def test_returns_empty_list_on_non_html_content(self):
        """Non-HTML responses (e.g., JSON) should be skipped."""
        client = _make_client(
            _make_response(html="{}", content_type="application/json")
        )
        sem = asyncio.Semaphore(10)

        links = await _extract_links(
            "https://example.com/api", "example.com", client, sem, jitter=False
        )

        assert links == []

    async def test_returns_empty_list_on_timeout(self):
        """Timeout exceptions should be swallowed and return empty list."""
        import httpx

        client = AsyncMock()
        client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        sem = asyncio.Semaphore(10)

        links = await _extract_links(
            "https://example.com/slow", "example.com", client, sem, jitter=False
        )

        assert links == []

    async def test_resolves_relative_urls(self):
        """Relative hrefs should be resolved against the base URL."""
        html = '<a href="/docs/guide">Guide</a>'
        client = _make_client(_make_response(html))
        sem = asyncio.Semaphore(10)

        links = await _extract_links(
            "https://example.com/", "example.com", client, sem, jitter=False
        )

        assert "https://example.com/docs/guide" in links


# ---------------------------------------------------------------------------
# TestRecursiveCrawl
# ---------------------------------------------------------------------------


class TestRecursiveCrawl:
    """Tests for recursive_crawl() parallel BFS."""

    async def test_respects_url_cap_of_1000(self):
        """recursive_crawl() must never return more than 1000 URLs."""

        # Generate a response with 200 unique links per fetch
        def _big_html(base: str) -> str:
            links = "".join(f'<a href="{base}/page{i}">p{i}</a>' for i in range(200))
            return f"<html><body>{links}</body></html>"

        call_count = 0

        async def _mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_response(_big_html("https://docs.example.com"))

        with patch("httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.get = _mock_get
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_instance

            urls = await recursive_crawl(
                "https://docs.example.com/", max_depth=5, concurrency=5
            )

        assert len(urls) <= 1000

    async def test_deduplicates_urls(self):
        """The same URL must not appear twice in the result."""
        html = """
        <a href="https://docs.example.com/guide">Guide</a>
        <a href="https://docs.example.com/guide">Guide duplicate</a>
        """
        with patch("httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=_make_response(html))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_instance

            urls = await recursive_crawl(
                "https://docs.example.com/", max_depth=1, concurrency=1
            )

        assert len(urls) == len(set(urls))
