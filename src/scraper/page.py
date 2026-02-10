"""Page scraping with Playwright."""

import time
import logging
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)

SLOW_PAGE_THRESHOLD_S = 10.0


class PageScraper:
    """Scrapes pages using Playwright."""

    def __init__(self) -> None:
        self._browser: Browser | None = None

    async def start(self) -> None:
        """Start the browser."""
        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(headless=True)
        logger.info("Browser started")

    async def stop(self) -> None:
        """Stop the browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            logger.info("Browser stopped")

    async def get_html(self, url: str, timeout: int = 30000) -> str:
        """Navigate to URL and extract body HTML."""
        if not self._browser:
            raise RuntimeError("Browser not started")

        page = await self._browser.new_page()
        try:
            start = time.monotonic()
            await page.goto(url, timeout=timeout, wait_until="networkidle")
            load_time_s = time.monotonic() - start

            logger.info(f"Navigated to {url} in {load_time_s:.1f}s")
            if load_time_s > SLOW_PAGE_THRESHOLD_S:
                logger.warning(f"Slow page load: {url} took {load_time_s:.1f}s")

            html = await page.inner_html("body")
            logger.debug(f"Extracted HTML from {url}: {len(html)} chars")
            return html
        finally:
            await page.close()
