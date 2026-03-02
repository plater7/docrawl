"""Unit tests for PagePool (PR 1.2) in src/scraper/page.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scraper.page import PagePool


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
