"""Unit tests for PagePool (PR 1.2) and PageScraper resource cleanup in src/scraper/page.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scraper.page import PagePool, PageScraper


def _make_page(broken: bool = False) -> AsyncMock:
    """Return a mock Playwright Page."""
    page = AsyncMock()
    if broken:
        page.goto.side_effect = Exception("page broken")
    else:
        page.goto.return_value = None
    page.context = AsyncMock()
    page.context.clear_cookies = AsyncMock()
    page.close = AsyncMock()
    return page


def _make_browser(*pages: AsyncMock) -> AsyncMock:
    """Return a mock Browser whose new_page() cycles through the given pages."""
    browser = AsyncMock()
    browser.new_page = AsyncMock(side_effect=list(pages))
    return browser


class TestPagePoolInitialize:
    """Tests for PagePool.initialize()."""

    async def test_initialize_fills_queue_with_size_pages(self):
        """initialize() should create exactly `size` pages and put them in the queue."""
        pages = [_make_page() for _ in range(3)]
        browser = _make_browser(*pages)

        pool = PagePool(browser, size=3)
        await pool.initialize()

        assert browser.new_page.call_count == 3
        assert pool._queue.qsize() == 3

    async def test_initialize_respects_size_parameter(self):
        """initialize() should honour a custom size of 1."""
        page = _make_page()
        browser = _make_browser(page)

        pool = PagePool(browser, size=1)
        await pool.initialize()

        assert browser.new_page.call_count == 1
        assert pool._queue.qsize() == 1

    async def test_initialize_default_size_is_five(self):
        """PagePool default size is 5 and initialize() creates 5 pages."""
        pages = [_make_page() for _ in range(5)]
        browser = _make_browser(*pages)

        pool = PagePool(browser)  # default size=5
        await pool.initialize()

        assert browser.new_page.call_count == 5


class TestPagePoolAcquire:
    """Tests for PagePool.acquire() context manager."""

    async def test_acquire_yields_a_page(self):
        """acquire() should yield one of the pooled pages inside the context."""
        page = _make_page()
        browser = _make_browser(page)

        pool = PagePool(browser, size=1)
        await pool.initialize()

        async with pool.acquire() as borrowed:
            assert borrowed is not None
            # Pool should be empty while page is borrowed
            assert pool._queue.empty()

    async def test_acquire_returns_page_to_pool_after_context(self):
        """acquire() should put the page back in the queue after the context exits."""
        page = _make_page()
        # browser.new_page may be called again during reset; provide the same page
        browser = AsyncMock()
        browser.new_page = AsyncMock(return_value=page)

        pool = PagePool(browser, size=1)
        await pool.initialize()

        async with pool.acquire() as _:
            pass  # use the page

        # Page (or replacement) must be back in the pool
        assert pool._queue.qsize() == 1

    async def test_acquire_returns_page_to_pool_on_exception(self):
        """acquire() must return a page to the pool even when caller code raises."""
        page = _make_page()
        replacement = _make_page()
        browser = AsyncMock()
        # First call: initial new_page in initialize; second: replacement inside acquire
        browser.new_page = AsyncMock(side_effect=[page, replacement])

        pool = PagePool(browser, size=1)
        await pool.initialize()

        with pytest.raises(RuntimeError):
            async with pool.acquire() as _:
                raise RuntimeError("caller error")

        # A replacement page must be back in the pool
        assert pool._queue.qsize() == 1

    async def test_acquire_resets_page_state_before_yielding(self):
        """acquire() should navigate to about:blank and clear cookies before yielding."""
        page = _make_page()
        browser = _make_browser(page)

        pool = PagePool(browser, size=1)
        await pool.initialize()

        async with pool.acquire() as borrowed:
            borrowed.goto.assert_awaited_once_with("about:blank", timeout=5000)
            borrowed.context.clear_cookies.assert_awaited_once()

    async def test_acquire_replaces_broken_page(self):
        """When the reset (goto about:blank) fails, acquire() should create a replacement page."""
        broken = _make_page(broken=True)  # goto raises
        replacement = _make_page()
        browser = AsyncMock()
        browser.new_page = AsyncMock(side_effect=[broken, replacement])

        pool = PagePool(browser, size=1)
        await pool.initialize()

        async with pool.acquire() as borrowed:
            # The replacement should be yielded, not the broken page
            assert borrowed is replacement


class TestPagePoolClose:
    """Tests for PagePool.close()."""

    async def test_close_drains_queue_and_closes_all_pages(self):
        """close() should close every page that is currently in the queue."""
        pages = [_make_page() for _ in range(3)]
        browser = _make_browser(*pages)

        pool = PagePool(browser, size=3)
        await pool.initialize()
        await pool.close()

        for page in pages:
            page.close.assert_awaited_once()
        assert pool._queue.empty()

    async def test_close_handles_page_close_errors_gracefully(self):
        """close() should not raise if a page.close() call throws."""
        page = _make_page()
        page.close.side_effect = Exception("close failed")
        browser = _make_browser(page)

        pool = PagePool(browser, size=1)
        await pool.initialize()

        # Should not raise
        await pool.close()


class TestPageScraperResourceCleanup:
    """Tests verifying PageScraper stores and releases the playwright context (issue #63)."""

    async def test_start_stores_playwright_context(self):
        """start() must store the playwright instance so stop() can release it."""
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        with patch(
            "src.scraper.page.async_playwright",
            return_value=MagicMock(start=AsyncMock(return_value=mock_playwright)),
        ):
            scraper = PageScraper()
            await scraper.start()

            assert scraper._playwright is mock_playwright
            assert scraper._browser is mock_browser

    async def test_stop_calls_playwright_stop(self):
        """stop() must call playwright.stop() to release the underlying context."""
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        with patch(
            "src.scraper.page.async_playwright",
            return_value=MagicMock(start=AsyncMock(return_value=mock_playwright)),
        ):
            scraper = PageScraper()
            await scraper.start()
            await scraper.stop()

            mock_playwright.stop.assert_awaited_once()
            assert scraper._playwright is None
            assert scraper._browser is None

    async def test_start_stops_playwright_if_browser_launch_fails(self):
        """If chromium.launch() raises, start() must stop playwright before re-raising."""
        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch = AsyncMock(
            side_effect=RuntimeError("launch failed")
        )

        with patch(
            "src.scraper.page.async_playwright",
            return_value=MagicMock(start=AsyncMock(return_value=mock_playwright)),
        ):
            scraper = PageScraper()

            with pytest.raises(RuntimeError, match="launch failed"):
                await scraper.start()

            # Playwright context must have been cleaned up
            mock_playwright.stop.assert_awaited_once()
            # Scraper state must remain unset
            assert scraper._playwright is None
            assert scraper._browser is None

    async def test_stop_is_idempotent_when_not_started(self):
        """stop() should not raise when called before start()."""
        scraper = PageScraper()
        # Should not raise
        await scraper.stop()
