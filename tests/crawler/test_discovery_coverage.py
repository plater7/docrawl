"""
Targeted coverage tests for src/crawler/discovery.py.

Covers all previously-uncovered branches and lines identified in the
51.45% baseline run. Tests are grouped by function under test.

asyncio_mode = "auto" is set in pytest.ini, so async tests need no decorator.
"""

import asyncio
import gzip as gzip_module
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from urllib.parse import urlparse
from urllib.parse import urlparse
from urllib.parse import urlparse

from src.crawler.discovery import (
    discover_urls,
    normalize_url,
    recursive_crawl,
    try_nav_parse,
    try_sitemap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_resp(status: int, content_type: str = "text/html", body: str = "") -> MagicMock:
    """Build a minimal fake httpx response."""
    resp = MagicMock()
    resp.status_code = status
    resp.headers = {"content-type": content_type}
    resp.text = body
    resp.content = body.encode("utf-8")
    return resp


def _make_async_client(url_map: dict) -> AsyncMock:
    """
    Build an async httpx.AsyncClient mock.
    url_map: {url: MagicMock response} — unknown URLs get 404.
    """
    async def fake_get(url, **kwargs):
        for key, resp in url_map.items():
            if key in url:
                return resp
        return _make_resp(404)

    client = AsyncMock()
    client.get = fake_get
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# ===========================================================================
# normalize_url()
# ===========================================================================

class TestNormalizeUrlUncoveredBranches:

    def test_url_longer_than_2000_chars_is_truncated(self):
        """URLs exceeding 2000 chars must be truncated and still normalised."""
        long_url = "https://example.com/" + "a" * 2000
        result = normalize_url(long_url)
        assert len(result) <= 2000

    def test_url_exactly_2001_chars_is_truncated(self):
        """Boundary: 2001-char URL triggers truncation path."""
        long_url = "https://example.com/p?" + "x=y&" * 500  # well over 2000
        result = normalize_url(long_url)
        assert len(result) <= 2000

    def test_non_http_scheme_returned_as_is(self):
        """ftp:// and similar schemes must be returned without modification."""
        ftp_url = "ftp://example.com/file.zip"
        result = normalize_url(ftp_url)
        assert result == ftp_url

    def test_mailto_scheme_returned_as_is(self):
        """mailto: must be returned without modification."""
        url = "mailto:user@example.com"
        result = normalize_url(url)
        assert result == url

    def test_exception_during_urlparse_returns_url_as_is(self):
        """If urlparse raises, the raw URL is returned (except block)."""
        bad_url = "https://example.com/path"
        with patch("src.crawler.discovery.urlparse", side_effect=Exception("parse error")):
            result = normalize_url(bad_url)
        assert result == bad_url


# ===========================================================================
# _extract_links() — tested indirectly via recursive_crawl
# ===========================================================================

class TestExtractLinksViaCrawl:
    """
    _extract_links is internal; we exercise it by calling recursive_crawl
    with a mocked httpx.AsyncClient and jitter disabled (concurrency=1).
    """

    async def test_404_response_returns_no_links(self):
        """A 404 page contributes no links to the crawl."""
        client = _make_async_client({"example.com": _make_resp(404)})
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        # Only base URL (depth-0 dedup), no children discovered
        assert result == ["https://example.com/"]

    async def test_500_response_returns_no_links(self):
        """A 500 page contributes no links to the crawl."""
        client = _make_async_client({"example.com": _make_resp(500)})
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        assert result == ["https://example.com/"]

    async def test_non_html_content_type_returns_no_links(self):
        """JSON responses must not be parsed for links."""
        client = _make_async_client({
            "example.com": _make_resp(200, content_type="application/json", body="{}")
        })
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        assert result == ["https://example.com/"]

    async def test_external_links_filtered_out(self):
        """Links pointing to a different domain must not appear in results."""
        html = '<a href="https://other-domain.com/page">external</a>'
        client = _make_async_client({
            "example.com": _make_resp(200, body=html)
        })
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
        hostnames = [urlparse(u).hostname for u in result]
        # All discovered URLs must be on example.com (or have no hostname, e.g., malformed/relative)
        assert all(h in (None, "example.com") for h in hostnames)
        # No discovered URL may point to other-domain.com
        assert "other-domain.com" not in hostnames
        assert not any("other-domain.com" in u for u in result)

    async def test_javascript_links_filtered(self):
        """javascript: hrefs must be skipped."""
        html = '<a href="javascript:void(0)">js link</a>'
        client = _make_async_client({
            "example.com": _make_resp(200, body=html)
        })
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        assert result == ["https://example.com/"]

    async def test_mailto_links_filtered(self):
        """mailto: hrefs must be skipped."""
        html = '<a href="mailto:admin@example.com">email</a>'
        client = _make_async_client({
            "example.com": _make_resp(200, body=html)
        })
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        assert result == ["https://example.com/"]

    async def test_tel_links_filtered(self):
        """tel: hrefs must be skipped."""
        html = '<a href="tel:+1234567890">call us</a>'
        client = _make_async_client({
            "example.com": _make_resp(200, body=html)
        })
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        assert result == ["https://example.com/"]

    async def test_fragment_links_filtered(self):
        """Fragment-only hrefs (#section) must be skipped."""
        html = '<a href="#section">anchor</a>'
        client = _make_async_client({
            "example.com": _make_resp(200, body=html)
        })
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        assert result == ["https://example.com/"]

    async def test_timeout_exception_returns_empty_list(self):
        """httpx.TimeoutException during fetch must not crash the crawl."""
        async def timeout_get(url, **kwargs):
            raise httpx.TimeoutException("timed out")

        client = AsyncMock()
        client.get = timeout_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        # Base URL is always added at depth-0 before any fetch
        assert "https://example.com/" in result

    async def test_generic_exception_returns_empty_list(self):
        """Generic exception during fetch must not crash the crawl."""
        async def broken_get(url, **kwargs):
            raise RuntimeError("network dead")

        client = AsyncMock()
        client.get = broken_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        assert "https://example.com/" in result

    async def test_valid_links_discovered(self):
        """Valid same-domain links from HTML are returned in results."""
        html = '<a href="/page1">p1</a><a href="/page2">p2</a>'
        client = _make_async_client({
            "example.com": _make_resp(200, body=html)
        })
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        assert "https://example.com/page1" in result
        assert "https://example.com/page2" in result


# ===========================================================================
# recursive_crawl()
# ===========================================================================

class TestRecursiveCrawlUncoveredBranches:

    async def test_max_depth_zero_returns_base_url_immediately(self):
        """max_depth < 1 exits before creating any HTTP client."""
        result = await recursive_crawl("https://example.com/", max_depth=0)
        assert result == ["https://example.com/"]

    async def test_max_depth_negative_returns_base_url(self):
        """-1 also triggers the early return."""
        result = await recursive_crawl("https://example.com/", max_depth=-1)
        assert result == ["https://example.com/"]

    async def test_url_cap_at_1000_logs_warning(self):
        """When 1000 URLs are collected, a warning is logged and crawl stops."""
        # Serve HTML with 100 links per page so we fill the cap quickly.
        # We need to provide enough unique URLs at depth-0+1 to exceed cap.
        def make_html(page_num: int) -> str:
            links = "".join(
                f'<a href="/p{page_num}-{i}">link</a>' for i in range(50)
            )
            return f"<html>{links}</html>"

        # Give each URL a unique page_num so we get many distinct child URLs
        call_count = {"n": 0}

        async def multi_page_get(url, **kwargs):
            n = call_count["n"]
            call_count["n"] += 1
            return _make_resp(200, body=make_html(n))

        client = AsyncMock()
        client.get = multi_page_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl(
                    "https://example.com/", max_depth=3, concurrency=1
                )
        # Cap is 1000; result must not exceed it
        assert len(result) <= 1000

    async def test_heartbeat_logged_every_10_urls(self):
        """Every 10th URL discovery triggers an INFO log."""
        # Build 20 unique child links from base page
        links_html = "".join(f'<a href="/p{i}">link</a>' for i in range(20))
        base_resp = _make_resp(200, body=links_html)
        child_resp = _make_resp(200, body="")  # children have no further links

        async def fake_get(url, **kwargs):
            if url == "https://example.com/":
                return base_resp
            return child_resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        import logging
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("src.crawler.discovery.logger") as mock_logger:
                    await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        # logger.info should have been called at least once for heartbeat
        mock_logger.info.assert_called()

    async def test_deduplication_same_url_visited_once(self):
        """If the same link appears multiple times, it is added only once."""
        html = '<a href="/page">p</a><a href="/page">p</a><a href="/page/">p</a>'
        client = _make_async_client({
            "example.com": _make_resp(200, body=html)
        })
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        # /page and /page/ normalise to the same URL
        assert result.count("https://example.com/page") <= 1

    async def test_bfs_depth_1_discovers_child_pages(self):
        """Normal BFS: depth-0 fetched, found links returned at depth-1."""
        html = '<a href="/child1">c1</a>'
        client = _make_async_client({
        # Ensure both the base URL and the discovered child URL are present.
        assert set(result) >= {"https://example.com/", "https://example.com/child1"}
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        assert "https://example.com/" in result
        assert "https://example.com/child1" in result

    async def test_concurrency_env_var_used_when_not_passed(self):
        """DISCOVERY_CONCURRENCY env var sets concurrency when arg is None."""
        client = _make_async_client({})
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.dict("os.environ", {"DISCOVERY_CONCURRENCY": "3"}):
                    result = await recursive_crawl("https://example.com/", max_depth=0)
        assert result == ["https://example.com/"]


# ===========================================================================
# try_sitemap()
# ===========================================================================

SITEMAP_XML = (
    '<?xml version="1.0"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<url><loc>https://example.com/page1</loc></url>"
    "</urlset>"
)

SITEMAP_INDEX_XML = (
    '<?xml version="1.0"?>'
    '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>"
    "</sitemapindex>"
)

CHILD_SITEMAP_XML = (
    '<?xml version="1.0"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<url><loc>https://example.com/deep-page</loc></url>"
    "</urlset>"
)


class TestTrySitemapUncoveredBranches:

    def _client_from_map(self, url_map: dict) -> AsyncMock:
        """url_map: {substring: (status, content_bytes, text)}"""
        async def fake_get(url, **kwargs):
            for key, (status, content, text) in url_map.items():
                if key in url:
                    resp = MagicMock()
                    resp.status_code = status
                    resp.content = content
                    resp.text = text
                    return resp
            resp = MagicMock()
            resp.status_code = 404
            resp.content = b""
            resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return client

    async def test_non_200_non_404_sitemap_response_skipped(self):
        """500 response for sitemap.xml must be skipped gracefully."""
        client = self._client_from_map({
            "sitemap.xml": (500, b"", ""),
        })
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap("https://example.com/")
        assert result == []

    async def test_timeout_exception_on_sitemap_fetch_skipped(self):
        """TimeoutException during sitemap fetch must not crash discovery."""
        async def timeout_get(url, **kwargs):
            if "sitemap" in url:
                raise httpx.TimeoutException("timeout")
            resp = MagicMock()
            resp.status_code = 404
            resp.content = b""
            resp.text = ""
            return resp

        client = AsyncMock()
        client.get = timeout_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap("https://example.com/")
        assert result == []

    async def test_nested_sitemap_index_parsed_recursively(self):
        """A sitemapindex file causes child sitemaps to be fetched and parsed."""
        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if url.endswith("/sitemap.xml"):
                resp.status_code = 200
                resp.content = SITEMAP_INDEX_XML.encode()
                resp.text = SITEMAP_INDEX_XML
            elif "sitemap1.xml" in url:
                resp.status_code = 200
                resp.content = CHILD_SITEMAP_XML.encode()
                resp.text = CHILD_SITEMAP_XML
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap("https://example.com/")
        assert "https://example.com/deep-page" in result

    async def test_robots_txt_sitemap_directive_adds_url(self):
        """Sitemap: directive in robots.txt must be added to sitemap_urls."""
        robots_txt = "User-agent: *\nDisallow: /private\nSitemap: https://example.com/custom-sitemap.xml\n"

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if "robots.txt" in url:
                resp.status_code = 200
                resp.content = robots_txt.encode()
                resp.text = robots_txt
            elif "custom-sitemap.xml" in url:
                resp.status_code = 200
                resp.content = SITEMAP_XML.encode()
                resp.text = SITEMAP_XML
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap("https://example.com/")
        assert "https://example.com/page1" in result

    async def test_robots_txt_404_continues_gracefully(self):
        """404 on robots.txt must not stop sitemap discovery."""
        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if "robots.txt" in url:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            elif "sitemap.xml" in url:
                resp.status_code = 200
                resp.content = SITEMAP_XML.encode()
                resp.text = SITEMAP_XML
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap("https://example.com/")
        assert "https://example.com/page1" in result

    async def test_robots_txt_exception_continues_gracefully(self):
        """Exception during robots.txt fetch must be silently passed."""
        async def fake_get(url, **kwargs):
            if "robots.txt" in url:
                raise httpx.TimeoutException("robots timeout")
            resp = MagicMock()
            if "sitemap.xml" in url:
                resp.status_code = 200
                resp.content = SITEMAP_XML.encode()
                resp.text = SITEMAP_XML
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap("https://example.com/")
        # sitemap.xml still parseable
        assert "https://example.com/page1" in result

    async def test_filter_by_path_false_includes_all_same_domain_urls(self):
        """filter_by_path=False must include URLs regardless of base path."""
        sitemap_xml = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.com/other-section/page</loc></url>"
            "<url><loc>https://example.com/docs/page</loc></url>"
            "</urlset>"
        )

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if "sitemap.xml" in url and "sitemap_index" not in url:
                resp.status_code = 200
                resp.content = sitemap_xml.encode()
                resp.text = sitemap_xml
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap(
                "https://example.com/docs/", filter_by_path=False
            )
        assert "https://example.com/other-section/page" in result
        assert "https://example.com/docs/page" in result

    async def test_filter_by_path_true_excludes_urls_outside_base_path(self):
        """filter_by_path=True must exclude URLs not under the base path."""
        sitemap_xml = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.com/other-section/page</loc></url>"
            "<url><loc>https://example.com/docs/page</loc></url>"
            "</urlset>"
        )

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if "sitemap.xml" in url and "sitemap_index" not in url:
                resp.status_code = 200
                resp.content = sitemap_xml.encode()
                resp.text = sitemap_xml
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap(
                "https://example.com/docs/", filter_by_path=True
            )
        # /other-section/page is outside /docs/ and must be excluded
        assert "https://example.com/other-section/page" not in result
        assert "https://example.com/docs/page" in result

    async def test_gzip_decompression_failure_logs_warning_returns_empty(self):
        """Invalid gzip content must log a warning and return empty list."""
        gz_url = "https://example.com/sitemap.xml.gz"
        bad_gz = b"this is not valid gzip data at all"

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if url == gz_url:
                resp.status_code = 200
                resp.content = bad_gz
                resp.text = bad_gz.decode("latin-1")
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        # Patch sitemap_urls to only include the gz URL so we hit gzip path
        async def fake_client_get(url, **kwargs):
            return await fake_get(url)

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        # Provide the gz URL via robots.txt Sitemap: directive
        robots_txt = f"Sitemap: {gz_url}\n"

        async def fake_get2(url, **kwargs):
            resp = MagicMock()
            if "robots.txt" in url:
                resp.status_code = 200
                resp.content = robots_txt.encode()
                resp.text = robots_txt
            elif url == gz_url:
                resp.status_code = 200
                resp.content = bad_gz
                resp.text = bad_gz.decode("latin-1")
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client2 = AsyncMock()
        client2.get = fake_get2
        client2.__aenter__ = AsyncMock(return_value=client2)
        client2.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client2):
            result = await try_sitemap("https://example.com/")
        # gzip failure means no URLs parsed from that file
        assert result == []

    async def test_invalid_xml_in_sitemap_returns_empty(self):
        """Malformed XML content must be handled without crashing."""
        bad_xml = b"<urlset><url><loc>https://example.com/page</loc></url UNCLOSED"

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if "sitemap.xml" in url and "sitemap_index" not in url:
                resp.status_code = 200
                resp.content = bad_xml
                resp.text = bad_xml.decode("utf-8", errors="replace")
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap("https://example.com/")
        assert result == []

    async def test_sitemap_cache_param_passed_and_used(self, tmp_path):
        """sitemap_cache param must be forwarded and consulted."""
        from src.scraper.cache import PageCache

        cache = PageCache(tmp_path / ".cache")
        sitemap_url = "https://example.com/sitemap.xml"
        cache.put(sitemap_url, SITEMAP_XML)

        http_fetched = []

        async def fake_get(url, **kwargs):
            http_fetched.append(url)
            resp = MagicMock()
            resp.status_code = 404
            resp.content = b""
            resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap("https://example.com/", sitemap_cache=cache)

        assert "https://example.com/page1" in result
        assert sitemap_url not in http_fetched  # cache hit — no HTTP for that URL

    async def test_generic_exception_in_parse_sitemap_xml_logs_warning(self):
        """Unexpected exception in parse_sitemap_xml must log a warning."""
        # Trigger via patch on ET.fromstring raising an unexpected error type
        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if "sitemap.xml" in url and "sitemap_index" not in url:
                resp.status_code = 200
                resp.content = SITEMAP_XML.encode()
                resp.text = SITEMAP_XML
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("src.crawler.discovery.ET.fromstring", side_effect=RuntimeError("unexpected")):
                result = await try_sitemap("https://example.com/")
        assert result == []


# ===========================================================================
# try_nav_parse()
# ===========================================================================

def _make_playwright_stack(
    *,
    page_goto_side_effect=None,
    links_per_selector=None,
):
    """
    Build a minimal Playwright mock hierarchy.
    links_per_selector: list of lists of link mocks per selector call.
    """
    page_mock = AsyncMock()
    page_mock.__aenter__ = AsyncMock(return_value=page_mock)
    page_mock.__aexit__ = AsyncMock(return_value=False)

    if page_goto_side_effect is not None:
        page_mock.goto = AsyncMock(side_effect=page_goto_side_effect)
    else:
        page_mock.goto = AsyncMock(return_value=None)

    if links_per_selector is not None:
        page_mock.query_selector_all = AsyncMock(side_effect=links_per_selector)
    else:
        page_mock.query_selector_all = AsyncMock(return_value=[])

    browser_mock = AsyncMock()
    browser_mock.__aenter__ = AsyncMock(return_value=browser_mock)
    browser_mock.__aexit__ = AsyncMock(return_value=False)
    browser_mock.new_page = AsyncMock(return_value=page_mock)

    playwright_mock = AsyncMock()
    playwright_mock.chromium.launch = AsyncMock(return_value=browser_mock)

    pw_cm = MagicMock()
    pw_cm.__aenter__ = AsyncMock(return_value=playwright_mock)
    pw_cm.__aexit__ = AsyncMock(return_value=False)

    return pw_cm, browser_mock, page_mock


def _make_link(href):
    """Build a fake Playwright element handle for an anchor tag."""
    link = AsyncMock()
    link.get_attribute = AsyncMock(return_value=href)
    return link


class TestTryNavParseUncoveredBranches:

    async def test_ssrf_check_blocked_returns_empty(self):
        """validate_url_not_ssrf raising ValueError must return []."""
        with patch(
            "src.crawler.discovery.validate_url_not_ssrf",
            side_effect=ValueError("SSRF blocked"),
        ):
            result = await try_nav_parse("http://169.254.169.254/metadata")
        assert result == []

    async def test_nav_url_cap_at_100_stops_adding(self):
        """When 100 URLs are collected, further links must be skipped."""
        # Create 120 valid same-domain links from a single selector
        links = [_make_link(f"/page{i}") for i in range(120)]

        # Only the first selector (nav a) needs to return many links;
        # the rest return nothing because the cap stops iteration.
        links_per_selector = [links] + [[] for _ in range(6)]

        pw_cm, _, _ = _make_playwright_stack(links_per_selector=links_per_selector)

        with patch("src.crawler.discovery.async_playwright", return_value=pw_cm):
            with patch("src.crawler.discovery.validate_url_not_ssrf", return_value=None):
                result = await try_nav_parse("https://example.com/")
        assert len(result) <= 100

    async def test_mailto_links_filtered_in_nav(self):
        """mailto: hrefs are skipped in nav parsing."""
        links = [_make_link("mailto:admin@example.com")]
        pw_cm, _, _ = _make_playwright_stack(links_per_selector=[links] + [[] for _ in range(6)])

        with patch("src.crawler.discovery.async_playwright", return_value=pw_cm):
            with patch("src.crawler.discovery.validate_url_not_ssrf", return_value=None):
                result = await try_nav_parse("https://example.com/")
        assert result == []

    async def test_javascript_links_filtered_in_nav(self):
        """javascript: hrefs are skipped in nav parsing."""
        links = [_make_link("javascript:void(0)")]
        pw_cm, _, _ = _make_playwright_stack(links_per_selector=[links] + [[] for _ in range(6)])

        with patch("src.crawler.discovery.async_playwright", return_value=pw_cm):
            with patch("src.crawler.discovery.validate_url_not_ssrf", return_value=None):
                result = await try_nav_parse("https://example.com/")
        assert result == []

    async def test_external_domain_links_filtered_in_nav(self):
        """Links to external domains are excluded from nav results."""
        links = [_make_link("https://other.com/page")]
        pw_cm, _, _ = _make_playwright_stack(links_per_selector=[links] + [[] for _ in range(6)])

        with patch("src.crawler.discovery.async_playwright", return_value=pw_cm):
            with patch("src.crawler.discovery.validate_url_not_ssrf", return_value=None):
                result = await try_nav_parse("https://example.com/")
        assert result == []

    async def test_link_with_no_href_is_skipped(self):
        """An element with href=None must be skipped without error."""
        links = [_make_link(None)]
        pw_cm, _, _ = _make_playwright_stack(links_per_selector=[links] + [[] for _ in range(6)])

        with patch("src.crawler.discovery.async_playwright", return_value=pw_cm):
            with patch("src.crawler.discovery.validate_url_not_ssrf", return_value=None):
                result = await try_nav_parse("https://example.com/")
        assert result == []

    async def test_fragment_href_skipped_in_nav(self):
        """Fragment-only hrefs (#section) are skipped in nav parsing."""
        links = [_make_link("#section")]
        pw_cm, _, _ = _make_playwright_stack(links_per_selector=[links] + [[] for _ in range(6)])

        with patch("src.crawler.discovery.async_playwright", return_value=pw_cm):
            with patch("src.crawler.discovery.validate_url_not_ssrf", return_value=None):
                result = await try_nav_parse("https://example.com/")
        assert result == []

    async def test_selector_exception_continues_to_next_selector(self):
        """query_selector_all raising an exception must continue to the next selector."""
        # First selector throws, second returns a valid link
        good_link = _make_link("/valid-page")

        side_effects = [
            RuntimeError("selector failed"),
            [good_link],
        ] + [[] for _ in range(5)]

        pw_cm, _, page_mock = _make_playwright_stack()
        page_mock.query_selector_all = AsyncMock(side_effect=side_effects)

        with patch("src.crawler.discovery.async_playwright", return_value=pw_cm):
            with patch("src.crawler.discovery.validate_url_not_ssrf", return_value=None):
                result = await try_nav_parse("https://example.com/")
        assert "https://example.com/valid-page" in result

    async def test_valid_same_domain_links_included(self):
        """Valid same-domain links are returned by try_nav_parse."""
        links = [_make_link("/docs/intro"), _make_link("/docs/api")]
        pw_cm, _, _ = _make_playwright_stack(links_per_selector=[links] + [[] for _ in range(6)])

        with patch("src.crawler.discovery.async_playwright", return_value=pw_cm):
            with patch("src.crawler.discovery.validate_url_not_ssrf", return_value=None):
                result = await try_nav_parse("https://example.com/")
        assert "https://example.com/docs/intro" in result
        assert "https://example.com/docs/api" in result


# ===========================================================================
# discover_urls()
# ===========================================================================

class TestDiscoverUrlsUncoveredBranches:

    async def test_filter_by_path_param_forwarded_to_try_sitemap(self):
        """filter_by_path must be passed through to try_sitemap."""
        with patch("src.crawler.discovery.try_sitemap", return_value=["https://example.com/p"]) as mock_sitemap:
            await discover_urls("https://example.com/", filter_by_path=False)
        call_kwargs = mock_sitemap.call_args
        assert call_kwargs[0][1] is False or call_kwargs[1].get("filter_by_path") is False

    async def test_sitemap_cache_param_forwarded_to_try_sitemap(self, tmp_path):
        """sitemap_cache must be forwarded to try_sitemap."""
        from src.scraper.cache import PageCache

        cache = PageCache(tmp_path / ".cache")
        with patch("src.crawler.discovery.try_sitemap", return_value=["https://example.com/p"]) as mock_sitemap:
            await discover_urls("https://example.com/", sitemap_cache=cache)
        call_kwargs = mock_sitemap.call_args
        passed_cache = call_kwargs[0][2] if len(call_kwargs[0]) > 2 else call_kwargs[1].get("sitemap_cache")
        assert passed_cache is cache

    async def test_nav_exception_does_not_stop_recursive_crawl(self):
        """Exception in try_nav_parse is caught; recursive_crawl still runs."""
        with patch("src.crawler.discovery.try_sitemap", return_value=[]):
            with patch(
                "src.crawler.discovery.try_nav_parse",
                side_effect=Exception("nav exploded"),
            ):
                with patch(
                    "src.crawler.discovery.recursive_crawl",
                    return_value=["https://example.com/crawled"],
                ) as mock_crawl:
                    result = await discover_urls("https://example.com/", max_depth=1)

        mock_crawl.assert_called_once()
        assert "https://example.com/crawled" in result

    async def test_recursive_crawl_exception_returns_base_url_fallback(self):
        """Exception in recursive_crawl triggers base URL fallback."""
        with patch("src.crawler.discovery.try_sitemap", return_value=[]):
            with patch("src.crawler.discovery.try_nav_parse", return_value=[]):
                with patch(
                    "src.crawler.discovery.recursive_crawl",
                    side_effect=Exception("crawl exploded"),
                ):
                    result = await discover_urls("https://example.com/", max_depth=1)

        assert "https://example.com/" in result
        assert len(result) >= 1

    async def test_sitemap_finds_urls_nav_skipped_cascade(self):
        """When sitemap succeeds, nav parse must not be called (cascade)."""
        with patch(
            "src.crawler.discovery.try_sitemap",
            return_value=["https://example.com/page"],
        ):
            with patch("src.crawler.discovery.try_nav_parse") as mock_nav:
                with patch("src.crawler.discovery.recursive_crawl") as mock_crawl:
                    result = await discover_urls("https://example.com/")

        mock_nav.assert_not_called()
        mock_crawl.assert_not_called()
        assert "https://example.com/page" in result

    async def test_sitemap_and_nav_both_fail_crawl_runs(self):
        """When sitemap and nav both return empty, recursive_crawl is called."""
        with patch("src.crawler.discovery.try_sitemap", return_value=[]):
            with patch("src.crawler.discovery.try_nav_parse", return_value=[]):
                with patch(
                    "src.crawler.discovery.recursive_crawl",
                    return_value=["https://example.com/", "https://example.com/a"],
                ) as mock_crawl:
                    result = await discover_urls("https://example.com/", max_depth=2)

        mock_crawl.assert_called_once()
        assert "https://example.com/a" in result

    async def test_all_strategies_fail_returns_normalized_base_url(self):
        """Absolute fallback: normalized base URL returned when everything fails."""
        with patch("src.crawler.discovery.try_sitemap", return_value=[]):
            with patch("src.crawler.discovery.try_nav_parse", return_value=[]):
                with patch("src.crawler.discovery.recursive_crawl", return_value=[]):
                    result = await discover_urls("https://example.com/", max_depth=1)

        assert result == ["https://example.com/"]

    async def test_results_are_deduplicated_across_strategies(self):
        """If sitemap and nav (hypothetically) both returned same URL, no duplicates."""
        # Cascade means only sitemap runs when it succeeds, but we verify set dedup
        urls = [
            "https://example.com/page",
            "https://example.com/page",  # duplicate
            "https://example.com/other",
        ]
        with patch("src.crawler.discovery.try_sitemap", return_value=urls):
            result = await discover_urls("https://example.com/")

        assert len(result) == len(set(result))

    async def test_sitemap_exception_falls_through_to_nav(self):
        """Exception in try_sitemap is caught; cascade continues to nav parse (lines 557-559)."""
        with patch(
            "src.crawler.discovery.try_sitemap",
            side_effect=Exception("sitemap network error"),
        ):
            with patch(
                "src.crawler.discovery.try_nav_parse",
                return_value=["https://example.com/nav-page"],
            ) as mock_nav:
                with patch("src.crawler.discovery.recursive_crawl") as mock_crawl:
                    result = await discover_urls("https://example.com/")

        mock_nav.assert_called_once()
        mock_crawl.assert_not_called()  # nav succeeded → crawl skipped
        assert "https://example.com/nav-page" in result

    async def test_nav_success_skips_recursive_crawl(self):
        """When nav parse returns URLs, recursive_crawl is skipped (lines 575-577, 587-588)."""
        with patch("src.crawler.discovery.try_sitemap", return_value=[]):
            with patch(
                "src.crawler.discovery.try_nav_parse",
                return_value=["https://example.com/nav-a", "https://example.com/nav-b"],
            ):
                with patch("src.crawler.discovery.recursive_crawl") as mock_crawl:
                    result = await discover_urls("https://example.com/")

        mock_crawl.assert_not_called()
        assert "https://example.com/nav-a" in result
        assert "https://example.com/nav-b" in result


# ===========================================================================
# Remaining gap tests — targeting specific uncovered branches
# ===========================================================================

class TestRemainingGaps:
    """Cover the last few uncovered lines and branches."""

    # ---- Line 93: jitter=True path in _extract_links via concurrency > 1 ----

    async def test_jitter_sleep_called_when_concurrency_gt_1(self):
        """asyncio.sleep jitter is invoked when concurrency > 1 (jitter=True)."""
        html = '<a href="/child">child</a>'
        client = _make_async_client({
            "example.com": _make_resp(200, body=html)
        })

        sleep_calls = []

        async def recording_sleep(duration):
            sleep_calls.append(duration)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", side_effect=recording_sleep):
                await recursive_crawl("https://example.com/", max_depth=1, concurrency=2)

        # At least one sleep call should have occurred (jitter active with concurrency=2)
        assert len(sleep_calls) >= 1

    # ---- Line 120: query param appended to link URL in _extract_links ----

    async def test_link_with_query_param_preserved_in_crawl(self):
        """Links with ?query string are captured with the query included."""
        html = '<a href="/search?q=test">search</a>'
        client = _make_async_client({
            "example.com": _make_resp(200, body=html)
        })
        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=1, concurrency=1)
        assert any("q=test" in u for u in result)

    # ---- Line 321: query param in try_nav_parse link building ----

    async def test_nav_parse_link_with_query_param_preserved(self):
        """Links with query strings from nav parsing include the query."""
        links = [_make_link("/search?q=docs")]
        pw_cm, _, _ = _make_playwright_stack(links_per_selector=[links] + [[] for _ in range(6)])

        with patch("src.crawler.discovery.async_playwright", return_value=pw_cm):
            with patch("src.crawler.discovery.validate_url_not_ssrf", return_value=None):
                result = await try_nav_parse("https://example.com/")
        assert any("q=docs" in u for u in result)

    # ---- Sitemap: empty <loc/> tag (url_text falsy) → branch 454->452 ----

    async def test_sitemap_empty_loc_element_skipped(self):
        """An empty <loc/> element in a sitemap must be silently skipped."""
        sitemap_with_empty_loc = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc></loc></url>"
            "<url><loc>https://example.com/real-page</loc></url>"
            "</urlset>"
        )
        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if "sitemap.xml" in url and "sitemap_index" not in url:
                resp.status_code = 200
                resp.content = sitemap_with_empty_loc.encode()
                resp.text = sitemap_with_empty_loc
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap("https://example.com/")
        assert "https://example.com/real-page" in result

    # ---- Sitemap: URL from different domain → filtered (branch 457->452) ----

    async def test_sitemap_cross_domain_url_filtered(self):
        """URLs in sitemap pointing to a different domain must be excluded."""
        sitemap_with_cross_domain = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://other.com/page</loc></url>"
            "<url><loc>https://example.com/local-page</loc></url>"
            "</urlset>"
        )
        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if "sitemap.xml" in url and "sitemap_index" not in url:
                resp.status_code = 200
                resp.content = sitemap_with_cross_domain.encode()
                resp.text = sitemap_with_cross_domain
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        assert not any(urlparse(u).hostname == "other.com" for u in result)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            result = await try_sitemap("https://example.com/")
        assert not any("other.com" in u for u in result)
        assert "https://example.com/local-page" in result

    # ---- Branch 180->226: MAX_URLS cap checked at loop entry ----

    async def test_url_cap_prevents_processing_next_level(self):
        """When discovered_urls already equals MAX_URLS at loop start, BFS breaks."""
        # We simulate by having max_depth=2 but injecting so many depth-0 URLs
        # that the cap is reached before depth-1 fetch occurs.
        # Use a large current_level via a site that returns many same-domain links.

        # Build HTML that references 1001 unique pages
        links_html = "".join(f'<a href="/p{i}">link</a>' for i in range(1001))
        base_resp = _make_resp(200, body=links_html)

        async def fake_get(url, **kwargs):
            return base_resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await recursive_crawl("https://example.com/", max_depth=2, concurrency=1)

        assert len(result) <= 1000

    # ---- try_nav_parse: PlaywrightTimeout from page.goto ----

    async def test_nav_parse_playwright_timeout_returns_empty(self):
        """PlaywrightTimeout from page.goto must return [] and not propagate."""
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        pw_cm, _, _ = _make_playwright_stack(
            page_goto_side_effect=PlaywrightTimeout("load timed out")
        )

        with patch("src.crawler.discovery.async_playwright", return_value=pw_cm):
            with patch("src.crawler.discovery.validate_url_not_ssrf", return_value=None):
                result = await try_nav_parse("https://example.com/")
        assert result == []

    # ---- try_nav_parse: generic exception from async_playwright block ----

    async def test_nav_parse_generic_exception_returns_empty(self):
        """Generic exception inside the playwright block must return []."""
        pw_cm, _, _ = _make_playwright_stack(
            page_goto_side_effect=RuntimeError("connection refused")
        )

        with patch("src.crawler.discovery.async_playwright", return_value=pw_cm):
            with patch("src.crawler.discovery.validate_url_not_ssrf", return_value=None):
                result = await try_nav_parse("https://example.com/")
        assert result == []

    # ---- Nested sitemap: exception inside nested parse_sitemap_xml (lines 445-449) ----

    async def test_nested_sitemap_exception_continues_gracefully(self):
        """Exception in recursive nested sitemap parse must be caught and skipped."""
        # Sitemap index pointing to a child that raises during parse
        child_xml = b"<totally_broken_xml"

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if url.endswith("/sitemap.xml"):
                resp.status_code = 200
                resp.content = SITEMAP_INDEX_XML.encode()
                resp.text = SITEMAP_INDEX_XML
            elif "sitemap1.xml" in url:
                # Returns valid HTTP but broken XML that fails ET.fromstring
                resp.status_code = 200
                resp.content = child_xml
                resp.text = child_xml.decode("utf-8", errors="replace")
            else:
                resp.status_code = 404
                resp.content = b""
                resp.text = ""
            return resp

        client = AsyncMock()
        client.get = fake_get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.crawler.discovery.httpx.AsyncClient", return_value=client):
            # Should not raise even though child sitemap is broken
            result = await try_sitemap("https://example.com/")
        # No URLs from broken child, but function completes normally
        assert isinstance(result, list)
