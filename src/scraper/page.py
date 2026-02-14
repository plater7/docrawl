"""Page scraping with Playwright — includes DOM noise removal."""

import logging
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)

# Selectors for noise elements to remove before extraction
NOISE_SELECTORS = [
    "script", "style", "noscript", "iframe",
    "nav", "footer", "header",
    "[role='navigation']", "[role='banner']", "[role='contentinfo']",
    ".sidebar", "#sidebar",
    ".navbar", "#navbar",
    ".table-of-contents", "#table-of-contents",
    ".breadcrumb", ".footer", ".header",
    ".cookie-banner",
    "[id*='mintlify']",
    ".prev-next-links", ".pagination-nav",
    ".edit-this-page", ".last-updated",
    ".theme-toggle", ".search-bar", "[data-search]",
]

# Selectors to try for main content extraction (in priority order)
CONTENT_SELECTORS = [
    "main",
    "article",
    "[role='main']",
    "#content",
    ".content",
    ".markdown-body",
    ".docs-content",
    ".documentation",
    "#main-content",
]

MIN_CONTENT_LENGTH = 200


class PageScraper:
    """Scrapes pages using Playwright with DOM pre-cleaning."""

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

    async def _remove_noise(self, page: Page) -> None:
        """Remove noise elements from the DOM before extraction."""
        selector_list = ", ".join(NOISE_SELECTORS)
        removed = await page.evaluate(f"""() => {{
            const els = document.querySelectorAll(`{selector_list}`);
            let count = 0;
            els.forEach(el => {{ el.remove(); count++; }});
            return count;
        }}""")
        if removed:
            logger.debug(f"Removed {removed} noise elements from DOM")

    async def _extract_content(self, page: Page) -> str:
        """Extract main content HTML, trying specific selectors before body fallback."""
        for selector in CONTENT_SELECTORS:
            try:
                el = await page.query_selector(selector)
                if el:
                    html = await el.inner_html()
                    if len(html) >= MIN_CONTENT_LENGTH:
                        logger.debug(f"Extracted content via '{selector}' ({len(html)} chars)")
                        return html
            except Exception:
                continue

        # Fallback to body
        html = await page.inner_html("body")
        logger.debug(f"Fallback to body extraction ({len(html)} chars)")
        return html

    async def get_html(self, url: str, timeout: int = 30000) -> str:
        """Navigate to URL, clean DOM, and extract content HTML."""
        if not self._browser:
            raise RuntimeError("Browser not started")

        page = await self._browser.new_page()
        try:
            await page.goto(url, timeout=timeout, wait_until="networkidle")
            await self._remove_noise(page)
            html = await self._extract_content(page)
            return html
        finally:
            await page.close()
