"""Page scraping with Playwright — includes DOM noise removal and page pool."""

import asyncio
import logging
import httpx
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from playwright.async_api import async_playwright, Browser, Page

from src.utils.security import validate_url_not_ssrf

logger = logging.getLogger(__name__)


async def fetch_html_fast(url: str) -> str | None:
    """Try to fetch and convert a page to markdown without Playwright (HTTP fast-path).

    Uses httpx for a plain HTTP GET, converts the HTML response with markdownify,
    and returns the markdown only if it meets a minimum quality threshold (≥500 chars).
    Returns None if the page is JS-rendered, too short, or any error occurs.

    PR 1.3 — inserting before Playwright in the fallback chain saves
    browser overhead for static or server-rendered documentation sites.
    """
    validate_url_not_ssrf(url)
    try:
        headers = {
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "User-Agent": "DocRawl/0.9.8 (documentation crawler)",
        }
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return None
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None

            from markdownify import markdownify as md_convert

            markdown = md_convert(
                resp.text,
                heading_style="ATX",
                strip=["script", "style", "nav", "footer"],
            )
            if len(markdown) >= 500:
                return markdown
    except Exception:
        pass
    return None


async def fetch_markdown_native(url: str) -> tuple[str | None, int | None]:
    """Try to get native markdown via Accept: text/markdown content negotiation.

    Returns (markdown_content, token_count) or (None, None) if not available.
    """
    validate_url_not_ssrf(url)
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
    validate_url_not_ssrf(url)
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


class PageScraper:  # pragma: no cover
    """Scrapes pages using Playwright with DOM pre-cleaning."""

    def __init__(self) -> None:
        self._browser: Browser | None = None
        self._playwright: object | None = None  # async_playwright context

    async def start(self) -> None:
        """Start the browser.

        Stores the playwright context so it can be properly stopped in stop(),
        preventing resource leaks if browser launch or subsequent operations fail.
        """
        playwright = await async_playwright().start()
        try:
            self._browser = await playwright.chromium.launch(headless=True)
        except Exception:
            await playwright.stop()
            raise
        self._playwright = playwright
        logger.info("Browser started")

    async def stop(self) -> None:
        """Stop the browser and the underlying playwright context."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            logger.info("Browser stopped")
        if self._playwright is not None:
            await self._playwright.stop()  # type: ignore[union-attr,attr-defined]
            self._playwright = None

    async def _remove_noise(
        self, page: Page, noise_selectors: list[str] | None = None
    ) -> None:
        """Remove noise elements from the DOM before extraction.

        Args:
            page: Playwright page to clean.
            noise_selectors: Additional CSS selectors to remove, prepended before
                the DocRawl defaults so user selectors are tried first.
        """
        selectors = list(noise_selectors or []) + NOISE_SELECTORS
        selector_list = ", ".join(selectors)
        removed = await page.evaluate(f"""() => {{
            const els = document.querySelectorAll(`{selector_list}`);
            let count = 0;
            els.forEach(el => {{ el.remove(); count++; }});
            return count;
        }}""")
        if removed:
            logger.debug(f"Removed {removed} noise elements from DOM")

    async def _extract_content(
        self, page: Page, content_selectors: list[str] | None = None
    ) -> str:
        """Extract main content HTML, trying specific selectors before body fallback.

        Args:
            page: Playwright page to extract from.
            content_selectors: Additional CSS selectors to try first, prepended before
                the DocRawl defaults so user selectors take priority.
        """
        selectors = list(content_selectors or []) + CONTENT_SELECTORS
        for selector in selectors:
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

        # readability-lxml fallback — extracts main content via Mozilla Readability algorithm
        try:
            from readability import Document
            from markdownify import markdownify as md_convert

            full_html = await page.content()
            doc = Document(full_html)
            summary_html = doc.summary()
            markdown = md_convert(summary_html, heading_style="ATX")
            if len(markdown) >= MIN_CONTENT_LENGTH:
                logger.debug(
                    f"Extracted content via readability-lxml ({len(markdown)} chars)"
                )
                return summary_html
        except Exception as e:
            logger.debug(f"readability-lxml fallback failed: {e}")

        # Fallback to body
        html = await page.inner_html("body")
        logger.debug(f"Fallback to body extraction ({len(html)} chars)")
        return html

    async def get_html(
        self,
        url: str,
        timeout: int = 30000,
        pool: "PagePool | None" = None,
        content_selectors: list[str] | None = None,
        noise_selectors: list[str] | None = None,
    ) -> str:
        """Navigate to URL, clean DOM, and extract content HTML.

        Args:
            url: Page URL to scrape.
            timeout: Navigation timeout in milliseconds.
            pool: If provided, borrows a page from the pool instead of creating one (PR 1.2).
            content_selectors: Custom content selectors to try before defaults
            noise_selectors: Custom noise selectors to remove before extraction
        """
        if not self._browser and pool is None:
            raise RuntimeError("Browser not started")

        # SSRF validation before Playwright navigates — closes CONS-002 / issue #51
        validate_url_not_ssrf(url)

        if pool is not None:
            async with pool.acquire() as page:
                await page.goto(url, timeout=timeout, wait_until="networkidle")
                await self._remove_noise(page, noise_selectors)
                return await self._extract_content(page, content_selectors)

        assert self._browser is not None  # guarded by RuntimeError above
        page = await self._browser.new_page()
        try:
            await page.goto(url, timeout=timeout, wait_until="networkidle")
            await self._remove_noise(page, noise_selectors)
            html = await self._extract_content(page, content_selectors)
            return html
        finally:
            await page.close()


class PagePool:  # pragma: no cover
    """Pool of reusable Playwright pages backed by an asyncio.Queue (PR 1.2).

    Avoids the overhead of creating/closing a new page per URL.
    Pages are reset (about:blank + clear cookies) before re-use.
    If a page is found to be closed/broken on acquire, it is replaced automatically.

    Usage::

        pool = PagePool(browser, size=5)
        await pool.initialize()
        async with pool.acquire() as page:
            await page.goto(url)
        await pool.close()
    """

    def __init__(self, browser: Browser, size: int = 5) -> None:
        self._browser = browser
        self._size = size
        self._queue: asyncio.Queue[Page] = asyncio.Queue(maxsize=size)

    async def initialize(self) -> None:
        """Pre-create all pages and fill the queue."""
        for _ in range(self._size):
            page = await self._browser.new_page()
            await self._queue.put(page)
        logger.info(f"PagePool initialized with {self._size} pages")

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[Page, None]:
        """Context manager: borrow a page, reset it, return it to the pool."""
        page = await self._queue.get()
        try:
            # Reset state between uses
            try:
                await page.goto("about:blank", timeout=5000)
                await page.context.clear_cookies()
            except Exception:
                # Page is broken — replace it
                try:
                    await page.close()
                except Exception:
                    pass
                page = await self._browser.new_page()

            yield page
        except Exception:
            # Page might be in bad state — replace it
            try:
                await page.close()
            except Exception:
                pass
            page = await self._browser.new_page()
            raise
        finally:
            await self._queue.put(page)

    async def close(self) -> None:
        """Close all pages in the pool."""
        while not self._queue.empty():
            try:
                page = self._queue.get_nowait()
                await page.close()
            except Exception:
                pass
        logger.info("PagePool closed")
