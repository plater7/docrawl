"""URL discovery: sitemap, nav parsing, recursive crawl."""

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


async def discover_urls(base_url: str, max_depth: int = 5) -> list[str]:
    """
    Discover documentation URLs using cascade strategy.

    1. Try sitemap.xml
    2. If no sitemap, parse nav/sidebar
    3. Fallback to recursive crawl
    """
    urls: list[str] = []

    # Try sitemap first
    urls = await try_sitemap(base_url)
    if urls:
        logger.info(f"Found {len(urls)} URLs from sitemap")
        return urls

    # Try nav parsing
    urls = await try_nav_parse(base_url)
    if urls:
        logger.info(f"Found {len(urls)} URLs from nav")
        return urls

    # Fallback to recursive crawl
    urls = await recursive_crawl(base_url, max_depth)
    logger.info(f"Found {len(urls)} URLs from recursive crawl")
    return urls


async def try_sitemap(base_url: str) -> list[str]:
    """Try to parse sitemap.xml."""
    # TODO: Implement sitemap parsing
    return []


async def try_nav_parse(base_url: str) -> list[str]:
    """Parse navigation/sidebar links from the page."""
    # TODO: Implement nav parsing with Playwright
    return []


async def recursive_crawl(base_url: str, max_depth: int) -> list[str]:
    """Recursively crawl internal links."""
    # TODO: Implement recursive crawl
    return [base_url]
