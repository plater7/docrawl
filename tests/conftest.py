"""
Shared pytest fixtures and configuration for all tests.
"""

import pytest
import asyncio
from typing import Generator


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_urls():
    """Sample URLs for testing."""
    return [
        "https://example.com/",
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/guide/install",
        "https://example.com/api/reference",
    ]


@pytest.fixture
def sample_sitemap_xml():
    """Valid sitemap XML for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/</loc>
    <lastmod>2024-01-01</lastmod>
  </url>
  <url>
    <loc>https://example.com/page1</loc>
    <lastmod>2024-01-02</lastmod>
  </url>
  <url>
    <loc>https://example.com/page2</loc>
    <lastmod>2024-01-03</lastmod>
  </url>
</urlset>"""


@pytest.fixture
def invalid_sitemap_xml():
    """Invalid sitemap XML for testing error handling."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/</loc>
    <lastmod>2024-01-01</lastmod>
  <!-- Missing closing tags -->
"""


@pytest.fixture
def nested_sitemap_index_xml():
    """Sitemap index XML for testing nested sitemaps."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap1.xml</loc>
    <lastmod>2024-01-01</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap2.xml</loc>
    <lastmod>2024-01-02</lastmod>
  </sitemap>
</sitemapindex>"""
