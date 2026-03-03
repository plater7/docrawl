"""Unit tests for PageCache (PR 2.4) in src/scraper/cache.py."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch


from src.scraper.cache import PageCache

_URL = "https://docs.example.com/getting-started"
_HTML = "<h1>Getting Started</h1><p>Install the package.</p>"


def _url_hash(url: str) -> str:
    """Replicate the internal _path() hash for test assertions."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


class TestPageCacheGet:
    """Tests for PageCache.get()."""

    def test_returns_none_on_cache_miss(self, tmp_path: Path):
        """get() returns None when no cache file exists for the URL."""
        cache = PageCache(cache_dir=tmp_path / "cache", ttl=3600)
        result = cache.get(_URL)
        assert result is None

    def test_returns_cached_html_on_hit(self, tmp_path: Path):
        """get() returns the previously stored HTML when the entry is valid."""
        cache_dir = tmp_path / "cache"
        cache = PageCache(cache_dir=cache_dir, ttl=3600)

        cache.put(_URL, _HTML)
        result = cache.get(_URL)

        assert result == _HTML

    def test_returns_none_and_deletes_file_when_ttl_expired(self, tmp_path: Path):
        """get() returns None and removes the cache file when the TTL has elapsed."""
        cache_dir = tmp_path / "cache"
        cache = PageCache(cache_dir=cache_dir, ttl=60)

        cache.put(_URL, _HTML)

        # Advance simulated time past the TTL
        with patch("src.scraper.cache.time.time", return_value=9_999_999_999.0):
            result = cache.get(_URL)

        cache_file = cache_dir / f"{_url_hash(_URL)}.json"
        assert result is None
        assert not cache_file.exists()

    def test_returns_none_and_removes_file_for_corrupt_json(self, tmp_path: Path):
        """get() returns None and deletes a corrupt cache file silently."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(parents=True)
        cache = PageCache(cache_dir=cache_dir, ttl=3600)

        # Write a corrupt JSON file at the expected path
        cache_file = cache_dir / f"{_url_hash(_URL)}.json"
        cache_file.write_text("not valid json", encoding="utf-8")

        result = cache.get(_URL)

        assert result is None
        assert not cache_file.exists()

    def test_returns_none_for_url_collision(self, tmp_path: Path):
        """get() returns None when the stored URL does not match the requested URL.

        This simulates a hash collision by writing a cache entry for a different
        URL at the path that the target URL would map to.
        """
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(parents=True)
        cache = PageCache(cache_dir=cache_dir, ttl=3600)

        # Write an entry under the target URL's hash but with a different URL
        target_url = _URL
        different_url = "https://docs.example.com/other-page"
        cache_file = cache_dir / f"{_url_hash(target_url)}.json"
        data = json.dumps(
            {"url": different_url, "html": _HTML, "timestamp": 1_000_000.0}
        )
        cache_file.write_text(data, encoding="utf-8")

        result = cache.get(target_url)

        assert result is None


class TestPageCachePut:
    """Tests for PageCache.put()."""

    def test_put_stores_and_get_retrieves_correctly(self, tmp_path: Path):
        """put() followed by get() returns the original HTML string."""
        cache = PageCache(cache_dir=tmp_path / "cache", ttl=3600)
        html = "<p>Hello, world!</p>"

        cache.put(_URL, html)
        assert cache.get(_URL) == html

    def test_put_writes_json_file_with_correct_fields(self, tmp_path: Path):
        """put() creates a JSON file containing url, html, and timestamp fields."""
        cache_dir = tmp_path / "cache"
        cache = PageCache(cache_dir=cache_dir, ttl=3600)
        cache.put(_URL, _HTML)

        cache_file = cache_dir / f"{_url_hash(_URL)}.json"
        assert cache_file.exists()

        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert data["url"] == _URL
        assert data["html"] == _HTML
        assert "timestamp" in data


class TestPageCacheCounters:
    """Tests for hits and misses counters."""

    def test_misses_counter_increments_on_cache_miss(self, tmp_path: Path):
        """misses counter increments each time get() finds no valid entry."""
        cache = PageCache(cache_dir=tmp_path / "cache", ttl=3600)

        cache.get(_URL)
        cache.get(_URL)

        assert cache.misses == 2
        assert cache.hits == 0

    def test_hits_counter_increments_on_cache_hit(self, tmp_path: Path):
        """hits counter increments each time get() returns a cached value."""
        cache = PageCache(cache_dir=tmp_path / "cache", ttl=3600)
        cache.put(_URL, _HTML)

        cache.get(_URL)
        cache.get(_URL)

        assert cache.hits == 2
        assert cache.misses == 0

    def test_hit_and_miss_counters_tracked_independently(self, tmp_path: Path):
        """hits and misses counters are independent and accumulate correctly."""
        cache = PageCache(cache_dir=tmp_path / "cache", ttl=3600)
        other_url = "https://docs.example.com/other"

        cache.get(other_url)  # miss
        cache.put(_URL, _HTML)
        cache.get(_URL)  # hit

        assert cache.hits == 1
        assert cache.misses == 1
