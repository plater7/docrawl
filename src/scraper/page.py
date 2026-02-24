"""Page scraping with Playwright — includes DOM noise removal."""

import logging
import httpx
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)


async def fetch_markdown_native(url: str) -> tuple[str | None, int | None]:
    """Try to get native markdown via Accept: text/markdown content negotiation.

    Returns (markdown_content, token_count) or (None, None) if not available.
    """
    try:
        headers = {
            "Accept": "text/markdown, text/html;q=0.9, */*;q=0.8",
            "User-Agent": "Docrawl/1.0 (AI documentation crawler)",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=headers, timeout=15.0, follow_redirects=True
            )
            content_type = resp.headers.get("content-type", "")
            if "text/markdown" in content_type:
                token_count_str = resp.headers.get("x-markdown-tokens")
                token_count = int(token_count_str) if token_count_str else None
                return resp.text, token_count
    except Exception:
        pass
    return None, None


async def fetch_markdown_proxy(
    url: str, proxy_url: str = "https://markdown.new"
) -> tuple[str | None, None]:
    """Fetch markdown via a proxy service (markdown.new, r.jina.ai, etc).

    Returns (markdown_content, None) or (None, None) if unavailable.
    """
    try:
        proxy_target = f"{proxy_url.rstrip('/')}/{url}"
        headers = {"User-Agent": "Docrawl/1.0 (AI documentation crawler)"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                proxy_target, headers=headers, timeout=30.0, follow_redirects=True
            )
            if resp.status_code == 200 and len(resp.text) > 100:
                return resp.text, None
    except Exception:
        pass
    return None, None


# Selectors for noise elements to remove before extraction
NOISE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "nav",
    "footer",
    "header",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    ".sidebar",
    "#sidebar",
    ".navbar",
    "#navbar",
    ".table-of-contents",
    "#table-of-contents",
    ".breadcrumb",
    ".footer",
    ".header",
    ".cookie-banner",
    "[id*='mintlify']",
    ".prev-next-links",
    ".pagination-nav",
    ".edit-this-page",
    ".last-updated",
    ".theme-toggle",
    ".search-bar",
    "[data-search]",
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
                        logger.debug(
                            f"Extracted content via '{selector}' ({len(html)} chars)"
                        )
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
