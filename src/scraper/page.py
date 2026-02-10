"""Page scraping with Playwright."""

import logging
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)


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
            await page.goto(url, timeout=timeout, wait_until="networkidle")
            html = await page.inner_html("body")
            return html
        finally:
            await page.close()
