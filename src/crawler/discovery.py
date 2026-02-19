"""URL discovery: sitemap, nav parsing, recursive crawl."""

import asyncio
import gzip
import logging
import re
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
    Normalize URL for deduplication with safety checks.

    Normalization rules:
    - Remove fragment (#section)
    - Remove trailing slash (except for root path)
    - Lowercase scheme and domain
    - Preserve query params
    - Handle unicode and special characters
    - Enforce max URL length (2000 chars)

    Examples:
        https://example.com/path/ -> https://example.com/path
        https://example.com/path#section -> https://example.com/path
        https://EXAMPLE.com/Path -> https://example.com/Path (domain lowercase, path preserved)

    Raises:
        ValueError: If URL is invalid or exceeds max length
    """
    MAX_URL_LENGTH = 2000  # Reasonable limit to prevent DoS

    # Safety check: URL length
    if len(url) > MAX_URL_LENGTH:
        logger.warning(f"URL exceeds max length ({MAX_URL_LENGTH}): {url[:100]}...")
        url = url[:MAX_URL_LENGTH]

    try:
        parsed = urlparse(url)

        # Validate scheme
        if parsed.scheme not in ['http', 'https', '']:
            logger.debug(f"Skipping non-HTTP URL: {url}")
            return url  # Return as-is for caller to filter

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
    except Exception as e:
        logger.warning(f"Failed to normalize URL: {url} - {e}")
        return url  # Return as-is, let caller handle


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
    - Heartbeat logging every 10 URLs
    - Per-URL error handling (failures don't stop crawl)
    """
    if max_depth < 1:
        return [base_url]

    visited = set()
    to_visit = deque([(base_url, 0)])  # (url, depth)
    discovered_urls = []
    base_domain = urlparse(base_url).netloc

    MAX_URLS = 1000  # Safety cap
    RATE_LIMIT_DELAY = 0.5  # seconds between requests
    HEARTBEAT_INTERVAL = 10  # Log every N URLs

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

            # Heartbeat logging
            if len(discovered_urls) % HEARTBEAT_INTERVAL == 0:
                msg = f"Crawl progress: {len(discovered_urls)} URLs discovered, {len(to_visit)} queued"
                logger.info(msg)
                print(f"[DISCOVERY] {msg}", flush=True)

            logger.debug(f"Crawling [{depth}/{max_depth}]: {current_url}")

            # Stop if max depth reached
            if depth >= max_depth:
                continue

            # Fetch and parse links (per-URL error handling)
            try:
                await asyncio.sleep(RATE_LIMIT_DELAY)  # Rate limiting
                response = await client.get(current_url)

                if response.status_code == 404:
                    logger.debug(f"Skipping 404: {current_url}")
                    continue
                elif response.status_code != 200:
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
                logger.debug(f"Timeout crawling {current_url}")
                continue
            except Exception as e:
                logger.debug(f"Failed to crawl {current_url}: {e}")
                continue

    if len(discovered_urls) >= MAX_URLS:
        logger.warning(f"Hit URL cap ({MAX_URLS}). Crawl may be incomplete.")

    logger.info(f"Recursive crawl complete: {len(discovered_urls)} URLs found")
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
    - Timeout (10s page load, reduced from 15s)
    - Max 100 URLs cap
    """
    discovered_urls = set()
    base_domain = urlparse(base_url).netloc
    MAX_NAV_URLS = 100

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

    msg = f"Trying nav parsing on {base_url}"
    logger.info(msg)
    print(f"[DISCOVERY] {msg}", flush=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            logger.debug("Loading page for nav parsing...")
            await page.goto(base_url, wait_until='domcontentloaded', timeout=10000)

            # Try each selector with limit
            for selector in NAV_SELECTORS:
                if len(discovered_urls) >= MAX_NAV_URLS:
                    logger.info(f"Hit nav URL cap ({MAX_NAV_URLS}), stopping")
                    break

                try:
                    links = await page.query_selector_all(selector)
                    logger.debug(f"Selector '{selector}' found {len(links)} links")

                    for link in links:
                        if len(discovered_urls) >= MAX_NAV_URLS:
                            break

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
        msg = f"Nav parsing timeout after 10s on {base_url}"
        logger.warning(msg)
        print(f"[DISCOVERY] {msg}", flush=True)
        return []
    except Exception as e:
        msg = f"Nav parsing failed for {base_url}: {e}"
        logger.error(msg)
        print(f"[DISCOVERY] {msg}", flush=True)
        return []

    result = list(discovered_urls)[:MAX_NAV_URLS]
    msg = f"Nav parsing found {len(result)} URLs"
    logger.info(msg)
    print(f"[DISCOVERY] {msg}", flush=True)
    return result


_LOCALE_SEGMENT_RE = re.compile(r'^[a-z]{2}(-[a-z]{2,4})?$', re.IGNORECASE)


def _path_keywords(base_path: str) -> list[str]:
    """Extract product keywords from base path, stripping locale segments.

    '/es-mx/intune'       → ['intune']
    '/en-us/azure/vms'    → ['azure', 'vms']
    '/'                   → []
    """
    return [
        s.lower() for s in base_path.split('/')
        if s and not _LOCALE_SEGMENT_RE.match(s)
    ]


async def try_sitemap(base_url: str, filter_by_path: bool = True) -> list[str]:
    """
    Try to parse sitemap.xml and robots.txt.

    Discovery order (stops at first success):
    1. {base_url}/sitemap.xml  — path-specific, highest priority
    2. /sitemap.xml            — root standard
    3. /sitemap_index.xml      — root index
    4. Sitemap: directives from robots.txt

    For sitemap index files:
    - Sub-sitemaps are filtered by product keywords before downloading (fix #1)
    - Recursion is limited to 1 level deep (fix #3)

    Args:
        base_url: Base URL of the site
        filter_by_path: If True, filter URLs to only include those under the base URL's path

    Returns:
        List of URLs found in sitemaps

    Edge cases handled:
    - Path-specific sitemap tried before global index
    - Sub-sitemap keyword filtering to avoid downloading unrelated products
    - Max 1 level of sitemap index recursion
    - Gzipped sitemaps (.xml.gz)
    - Invalid XML handling
    - 404s and network errors
    """
    base_domain = urlparse(base_url).netloc
    base_path = urlparse(base_url).path.rstrip('/') if urlparse(base_url).path else ""
    if base_path == "":
        base_path = "/"

    keywords = _path_keywords(base_path)

    msg = f"Trying sitemap on {base_url}"
    logger.info(msg)
    print(f"[DISCOVERY] {msg}", flush=True)

    async def parse_sitemap_xml(url: str, client: httpx.AsyncClient, depth: int = 0) -> set[str]:
        """Parse a sitemap XML file. Max 1 level of sitemap index recursion."""
        MAX_INDEX_DEPTH = 1
        urls: set[str] = set()

        try:
            response = await client.get(url, timeout=10.0)

            if response.status_code == 404:
                logger.debug(f"Sitemap not found (404): {url}")
                return urls
            elif response.status_code != 200:
                logger.debug(f"Non-200 status {response.status_code} for sitemap: {url}")
                return urls

            content = response.content

            if url.endswith('.gz'):
                try:
                    content = gzip.decompress(content)
                except Exception as e:
                    logger.warning(f"✗ Failed to decompress gzipped sitemap: {url} - {e}")
                    return urls

            try:
                root = ET.fromstring(content)
            except ET.ParseError as e:
                logger.warning(f"✗ Invalid XML in sitemap: {url} - {e}")
                print(f"[DISCOVERY] ✗ Invalid XML in sitemap: {url}", flush=True)
                return urls

            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            # Handle sitemap index — only within depth limit
            if depth < MAX_INDEX_DEPTH:
                all_sub = [
                    elem.text for elem in root.findall('.//ns:sitemap/ns:loc', namespace)
                    if elem.text
                ]
                if all_sub:
                    # Filter sub-sitemaps by product keywords before downloading (#1)
                    if filter_by_path and keywords and base_path != "/":
                        relevant = [u for u in all_sub if any(kw in u.lower() for kw in keywords)]
                        skipped = len(all_sub) - len(relevant)
                        if relevant:
                            msg = (f"Sitemap index: {len(relevant)}/{len(all_sub)} sub-sitemaps "
                                   f"match {keywords} (skipped {skipped})")
                            logger.info(msg)
                            print(f"[DISCOVERY] {msg}", flush=True)
                        else:
                            # No keyword match — download all to avoid missing content
                            relevant = all_sub
                            msg = f"Sitemap index: no keyword match, downloading all {len(all_sub)} sub-sitemaps"
                            logger.warning(msg)
                            print(f"[DISCOVERY] {msg}", flush=True)
                    else:
                        relevant = all_sub

                    for nested_url in relevant:
                        try:
                            nested_urls = await parse_sitemap_xml(nested_url, client, depth + 1)
                            urls.update(nested_urls)
                        except Exception as e:
                            logger.debug(f"Failed to parse nested sitemap {nested_url}: {e}")
            else:
                # Depth limit reached — skip further nesting (#3)
                deep_count = len(root.findall('.//ns:sitemap/ns:loc', namespace))
                if deep_count:
                    logger.debug(f"Depth limit reached, skipping {deep_count} nested index entries in {url}")

            # Extract URLs from regular sitemap
            for url_elem in root.findall('.//ns:url/ns:loc', namespace):
                url_text = url_elem.text
                if url_text:
                    parsed = urlparse(url_text)
                    if parsed.netloc == base_domain:
                        url_path = parsed.path.rstrip('/') if parsed.path else "/"
                        if filter_by_path and base_path != "/":
                            if not (url_path == base_path or url_path.startswith(base_path + "/")):
                                logger.debug(f"Skipping URL not under base path {base_path}: {url_text}")
                                continue
                        urls.add(normalize_url(url_text))

        except httpx.TimeoutException:
            logger.debug(f"Timeout fetching sitemap: {url}")
        except Exception as e:
            logger.warning(f"✗ Failed to parse sitemap {url}: {e}")

        return urls

    async with httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "DocRawl/1.0 (Documentation Crawler)"}
    ) as client:

        # Build candidate list in priority order (#2: path-specific first)
        candidates: list[str] = []

        if base_path != "/":
            # Highest priority: sitemap at the crawl path itself
            candidates.append(base_url.rstrip('/') + '/sitemap.xml')

        # Standard root locations
        candidates.append(urljoin(base_url, '/sitemap.xml'))
        candidates.append(urljoin(base_url, '/sitemap_index.xml'))

        # robots.txt sitemap directives (appended last — often the global index)
        try:
            robots_url = urljoin(base_url, '/robots.txt')
            response = await client.get(robots_url, timeout=5.0)
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        candidates.append(sitemap_url)
        except Exception:
            pass

        # Try candidates in priority order, stop at first success
        seen: set[str] = set()
        for sitemap_url in candidates:
            if sitemap_url in seen:
                continue
            seen.add(sitemap_url)

            logger.debug(f"Trying sitemap candidate: {sitemap_url}")
            urls = await parse_sitemap_xml(sitemap_url, client)
            if urls:
                msg = f"Sitemap found {len(urls)} URLs [{sitemap_url}]"
                logger.info(msg)
                print(f"[DISCOVERY] {msg}", flush=True)
                return sorted(list(urls))

    msg = "Sitemap parsing found no URLs"
    logger.info(msg)
    print(f"[DISCOVERY] {msg}", flush=True)
    return []


async def discover_urls(base_url: str, max_depth: int = 5, filter_by_path: bool = True) -> list[str]:
    """
    Discover URLs using cascade strategy — stops at first success:
    1. Try sitemap (fast, authoritative)
    2. Try nav parsing (only if sitemap failed)
    3. Try recursive crawl (only if both above failed)

    Args:
        base_url: Base URL to discover
        max_depth: Maximum depth for recursive crawl
        filter_by_path: If True, filter sitemap URLs to only include those under base URL's path

    Returns deduplicated, normalized URLs. Never returns empty list.
    """
    all_urls = set()

    msg = f"=== Starting URL discovery for {base_url} (max_depth={max_depth}) ==="
    logger.info(msg)
    print(f"[DISCOVERY] {msg}", flush=True)

    # Strategy 1: Sitemap (fast, authoritative)
    msg = "Strategy 1/3: Trying sitemap discovery..."
    logger.info(msg)
    print(f"[DISCOVERY] {msg}", flush=True)

    SITEMAP_TIMEOUT = 360.0

    try:
        sitemap_urls = await asyncio.wait_for(
            try_sitemap(base_url, filter_by_path),
            timeout=SITEMAP_TIMEOUT,
        )
        if sitemap_urls:
            all_urls.update(sitemap_urls)
            msg = f"✓ Sitemap success: {len(sitemap_urls)} URLs found"
            logger.info(msg)
            print(f"[DISCOVERY] {msg}", flush=True)
        else:
            msg = "✗ Sitemap: No URLs found"
            logger.info(msg)
            print(f"[DISCOVERY] {msg}", flush=True)
    except asyncio.TimeoutError:
        msg = f"✗ Sitemap timed out after {SITEMAP_TIMEOUT:.0f}s, falling through to nav parsing"
        logger.warning(msg)
        print(f"[DISCOVERY] {msg}", flush=True)
    except Exception as e:
        msg = f"✗ Sitemap failed with exception: {e}"
        logger.error(msg)
        print(f"[DISCOVERY] {msg}", flush=True)

    # Cascade: stop at first successful strategy
    if all_urls:
        msg = f"Strategy 2/3: Skipping nav parsing (sitemap found {len(all_urls)} URLs)"
        logger.info(msg)
        print(f"[DISCOVERY] {msg}", flush=True)
        msg = f"Strategy 3/3: Skipping recursive crawl (sitemap succeeded)"
        logger.info(msg)
        print(f"[DISCOVERY] {msg}", flush=True)
    else:
        # Strategy 2: Nav parsing (only if sitemap failed)
        msg = "Strategy 2/3: Trying nav parsing..."
        logger.info(msg)
        print(f"[DISCOVERY] {msg}", flush=True)

        try:
            nav_urls = await try_nav_parse(base_url)
            if nav_urls:
                all_urls.update(nav_urls)
                msg = f"✓ Nav parsing success: {len(nav_urls)} URLs found"
                logger.info(msg)
                print(f"[DISCOVERY] {msg}", flush=True)
            else:
                msg = "✗ Nav parsing: No URLs found"
                logger.info(msg)
                print(f"[DISCOVERY] {msg}", flush=True)
        except Exception as e:
            msg = f"✗ Nav parsing failed with exception: {e}"
            logger.error(msg)
            print(f"[DISCOVERY] {msg}", flush=True)

        # Strategy 3: Recursive crawl (only if sitemap and nav both failed)
        if all_urls:
            msg = f"Strategy 3/3: Skipping recursive crawl (nav parsing found {len(all_urls)} URLs)"
            logger.info(msg)
            print(f"[DISCOVERY] {msg}", flush=True)
        else:
            msg = "Strategy 3/3: Falling back to recursive crawl (comprehensive)"
            logger.info(msg)
            print(f"[DISCOVERY] {msg}", flush=True)

            try:
                crawl_urls = await recursive_crawl(base_url, max_depth)
                if crawl_urls:
                    all_urls.update(crawl_urls)
                    msg = f"✓ Recursive crawl success: {len(crawl_urls)} URLs found"
                    logger.info(msg)
                    print(f"[DISCOVERY] {msg}", flush=True)
                else:
                    msg = "✗ Recursive crawl returned no URLs (unexpected)"
                    logger.warning(msg)
                    print(f"[DISCOVERY] {msg}", flush=True)
            except Exception as e:
                msg = f"✗ Recursive crawl failed with exception: {e}"
                logger.error(msg)
                print(f"[DISCOVERY] {msg}", flush=True)

    # Deduplicate and sort
    final_urls = sorted(list(all_urls))

    # Absolute minimum fallback: return base URL if nothing else worked
    if not final_urls:
        msg = "⚠ All strategies failed! Returning base URL as minimum fallback"
        logger.warning(msg)
        print(f"[DISCOVERY] {msg}", flush=True)
        final_urls = [normalize_url(base_url)]

    msg = f"=== Discovery complete: {len(final_urls)} total unique URLs ==="
    logger.info(msg)
    print(f"[DISCOVERY] {msg}", flush=True)
    return final_urls
