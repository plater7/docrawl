"""URL discovery: sitemap, nav parsing, recursive crawl."""

import asyncio
import gzip
import logging
import xml.etree.ElementTree as ET
from collections import deque
from io import BytesIO
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalize URL for deduplication.

    Normalization rules:
    - Remove fragment (#section)
    - Remove trailing slash (except for root path)
    - Lowercase scheme and domain
    - Preserve query params

    Examples:
        https://example.com/path/ -> https://example.com/path
        https://example.com/path#section -> https://example.com/path
        https://EXAMPLE.com/Path -> https://example.com/Path (domain lowercase, path preserved)
    """
    parsed = urlparse(url)

    # Normalize path: remove trailing slash except for root
    path = parsed.path.rstrip('/') if parsed.path != '/' else '/'

    # Lowercase scheme and domain, preserve path case
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        parsed.params,
        parsed.query,
        ''  # Remove fragment
    ))


async def recursive_crawl(base_url: str, max_depth: int) -> list[str]:
    """
    Recursively crawl internal links up to max_depth using BFS.

    Args:
        base_url: Starting URL
        max_depth: Maximum depth to crawl (1 = only direct links from base_url)

    Returns:
        List of discovered URLs (deduplicated, normalized)

    Edge cases handled:
    - Deduplication via normalized URLs
    - Same-domain filtering
    - Fragment removal
    - Trailing slash normalization
    - Rate limiting (0.5s between requests)
    - Total URL cap (1000 URLs max to prevent explosion)
    - Timeout handling (10s per request)
    """
    if max_depth < 1:
        return [base_url]

    visited = set()
    to_visit = deque([(base_url, 0)])  # (url, depth)
    discovered_urls = []
    base_domain = urlparse(base_url).netloc

    MAX_URLS = 1000  # Safety cap
    RATE_LIMIT_DELAY = 0.5  # seconds between requests

    async with httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "DocRawl/1.0 (Documentation Crawler)"}
    ) as client:
        while to_visit and len(discovered_urls) < MAX_URLS:
            current_url, depth = to_visit.popleft()

            # Normalize URL for deduplication
            normalized = normalize_url(current_url)
            if normalized in visited:
                continue

            visited.add(normalized)
            discovered_urls.append(normalized)

            logger.info(f"Crawling [{depth}/{max_depth}]: {current_url}")

            # Stop if max depth reached
            if depth >= max_depth:
                continue

            # Fetch and parse links
            try:
                await asyncio.sleep(RATE_LIMIT_DELAY)  # Rate limiting
                response = await client.get(current_url)

                if response.status_code != 200:
                    logger.warning(f"Non-200 status {response.status_code} for {current_url}")
                    continue

                # Only parse HTML content
                content_type = response.headers.get('content-type', '')
                if 'text/html' not in content_type:
                    logger.debug(f"Skipping non-HTML content: {content_type}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract all links
                for link in soup.find_all('a', href=True):
                    href = link['href']

                    # Skip common non-content links
                    if any(skip in href.lower() for skip in ['#', 'javascript:', 'mailto:', 'tel:']):
                        continue

                    absolute_url = urljoin(current_url, href)
                    parsed = urlparse(absolute_url)

                    # Filter: same domain, http/https only
                    if (parsed.netloc == base_domain and
                        parsed.scheme in ['http', 'https']):

                        # Remove fragment, keep query params
                        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if parsed.query:
                            clean_url += f"?{parsed.query}"

                        normalized_link = normalize_url(clean_url)
                        if normalized_link not in visited:
                            to_visit.append((clean_url, depth + 1))

            except httpx.TimeoutException:
                logger.warning(f"Timeout crawling {current_url}")
                continue
            except Exception as e:
                logger.warning(f"Failed to crawl {current_url}: {e}")
                continue

    if len(discovered_urls) >= MAX_URLS:
        logger.warning(f"Hit URL cap ({MAX_URLS}). Crawl may be incomplete.")

    logger.info(f"Discovery complete: {len(discovered_urls)} URLs found")
    return discovered_urls


async def try_nav_parse(base_url: str) -> list[str]:
    """
    Parse navigation/sidebar links from the page using Playwright.

    Useful for JS-rendered navigation that httpx can't see.

    Args:
        base_url: URL to parse navigation from

    Returns:
        List of URLs found in navigation elements

    Edge cases handled:
    - Multiple nav selectors (nav, aside, sidebar, etc.)
    - External link filtering
    - Deduplication
    - Timeout (15s page load)
    """
    discovered_urls = set()
    base_domain = urlparse(base_url).netloc

    # Common navigation selectors
    NAV_SELECTORS = [
        'nav a',
        'aside a',
        '.sidebar a',
        '.navigation a',
        '[role="navigation"] a',
        '.toc a',  # Table of contents
        '.menu a',
    ]

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(base_url, wait_until='domcontentloaded', timeout=15000)

            # Try each selector
            for selector in NAV_SELECTORS:
                try:
                    links = await page.query_selector_all(selector)

                    for link in links:
                        href = await link.get_attribute('href')
                        if not href:
                            continue

                        # Skip anchors and non-http links
                        if href.startswith('#') or href.startswith('javascript:'):
                            continue

                        absolute_url = urljoin(base_url, href)
                        parsed = urlparse(absolute_url)

                        # Same domain only
                        if parsed.netloc == base_domain and parsed.scheme in ['http', 'https']:
                            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                            if parsed.query:
                                clean_url += f"?{parsed.query}"
                            discovered_urls.add(normalize_url(clean_url))

                except Exception as e:
                    logger.debug(f"Selector '{selector}' failed: {e}")
                    continue

            await browser.close()

    except PlaywrightTimeout:
        logger.warning(f"Timeout loading {base_url} for nav parsing")
        return []
    except Exception as e:
        logger.warning(f"Nav parsing failed for {base_url}: {e}")
        return []

    result = list(discovered_urls)
    logger.info(f"Nav parsing found {len(result)} URLs")
    return result


async def try_sitemap(base_url: str) -> list[str]:
    """
    Try to parse sitemap.xml and robots.txt.

    Discovery order:
    1. /sitemap.xml
    2. /sitemap_index.xml
    3. Parse robots.txt for Sitemap: directive

    Args:
        base_url: Base URL of the site

    Returns:
        List of URLs found in sitemaps

    Edge cases handled:
    - Gzipped sitemaps (.xml.gz)
    - Sitemap index files (nested sitemaps)
    - Multiple sitemaps in robots.txt
    - Invalid XML handling
    """
    discovered_urls = set()
    base_domain = urlparse(base_url).netloc

    async def parse_sitemap_xml(url: str, client: httpx.AsyncClient) -> set[str]:
        """Parse a sitemap XML file."""
        urls = set()

        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                return urls

            content = response.content

            # Handle gzipped sitemaps
            if url.endswith('.gz'):
                try:
                    content = gzip.decompress(content)
                except Exception:
                    logger.warning(f"Failed to decompress gzipped sitemap: {url}")
                    return urls

            # Parse XML
            root = ET.fromstring(content)

            # Handle sitemap index (nested sitemaps)
            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            # Check if this is a sitemap index
            for sitemap_elem in root.findall('.//ns:sitemap/ns:loc', namespace):
                nested_url = sitemap_elem.text
                if nested_url:
                    nested_urls = await parse_sitemap_xml(nested_url, client)
                    urls.update(nested_urls)

            # Extract URLs from regular sitemap
            for url_elem in root.findall('.//ns:url/ns:loc', namespace):
                url_text = url_elem.text
                if url_text:
                    parsed = urlparse(url_text)
                    # Filter same domain
                    if parsed.netloc == base_domain:
                        urls.add(normalize_url(url_text))

        except ET.ParseError:
            logger.warning(f"Invalid XML in sitemap: {url}")
        except Exception as e:
            logger.warning(f"Failed to parse sitemap {url}: {e}")

        return urls

    async with httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "DocRawl/1.0 (Documentation Crawler)"}
    ) as client:

        # Try standard sitemap locations
        sitemap_urls = [
            urljoin(base_url, '/sitemap.xml'),
            urljoin(base_url, '/sitemap_index.xml'),
        ]

        # Try to get sitemap URLs from robots.txt
        try:
            robots_url = urljoin(base_url, '/robots.txt')
            response = await client.get(robots_url, timeout=5.0)
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        sitemap_urls.append(sitemap_url)
        except Exception:
            pass  # robots.txt is optional

        # Parse all discovered sitemaps
        for sitemap_url in sitemap_urls:
            urls = await parse_sitemap_xml(sitemap_url, client)
            discovered_urls.update(urls)

    result = list(discovered_urls)
    logger.info(f"Sitemap parsing found {len(result)} URLs")
    return result


async def discover_urls(base_url: str, max_depth: int = 5) -> list[str]:
    """
    Discover URLs using cascade strategy:
    1. Try sitemap
    2. Try nav parsing
    3. Fall back to recursive crawl

    Returns deduplicated, normalized URLs.
    """
    all_urls = set()

    # Strategy 1: Sitemap (fast, authoritative)
    logger.info("Trying sitemap discovery...")
    sitemap_urls = await try_sitemap(base_url)
    if sitemap_urls:
        all_urls.update(sitemap_urls)
        logger.info(f"Sitemap discovery: {len(sitemap_urls)} URLs")

    # Strategy 2: Nav parsing (good for JS-heavy sites)
    logger.info("Trying nav parsing...")
    nav_urls = await try_nav_parse(base_url)
    if nav_urls:
        all_urls.update(nav_urls)
        logger.info(f"Nav parsing: {len(nav_urls)} URLs")

    # Strategy 3: Recursive crawl (comprehensive fallback)
    logger.info(f"Starting recursive crawl (max_depth={max_depth})...")
    crawl_urls = await recursive_crawl(base_url, max_depth)
    all_urls.update(crawl_urls)
    logger.info(f"Recursive crawl: {len(crawl_urls)} URLs")

    # Deduplicate and sort
    final_urls = sorted(list(all_urls))

    logger.info(f"Total discovered URLs: {len(final_urls)}")
    return final_urls
