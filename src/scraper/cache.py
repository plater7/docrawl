"""Per-job page HTML cache with TTL and atomic writes (PR 2.4).

Cache layout: {output_path}/.cache/{url_hash}.json
Each entry: {"url": str, "html": str, "timestamp": float}

Design decisions:
- opt-in via JobRequest.use_cache (default False)
- TTL 24h default (CACHE_TTL env var)
- atomic write: .tmp → os.replace() for Windows compat
- blocked responses are never cached (checked by caller)
- corrupted cache files are silently removed
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TTL = int(os.environ.get("CACHE_TTL", str(24 * 3600)))  # 24 hours


class PageCache:
    """Simple disk-based HTML cache with TTL.

    Args:
        cache_dir: Directory where cache files are stored.
        ttl: Time-to-live in seconds. 0 disables TTL (entries never expire).
    """

    def __init__(self, cache_dir: Path, ttl: int = DEFAULT_TTL) -> None:
        self._dir = cache_dir
        self._ttl = ttl
        self._hits = 0
        self._misses = 0
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, url: str) -> Path:
        """Derive a stable cache file path from the URL."""
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        return self._dir / f"{url_hash}.json"

    def get(self, url: str) -> str | None:
        """Return cached HTML for url, or None if cache miss / expired."""
        path = self._path(url)
        if not path.exists():
            self._misses += 1
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ts = float(data.get("timestamp", 0))
            if self._ttl > 0 and (time.time() - ts) > self._ttl:
                path.unlink(missing_ok=True)
                self._misses += 1
                return None
            if data.get("url") != url:
                # Hash collision (extremely rare) — treat as miss
                self._misses += 1
                return None
            self._hits += 1
            return data.get("html")
        except Exception:
            # Corrupt cache entry — remove silently
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            self._misses += 1
            return None

    def put(self, url: str, html: str) -> None:
        """Store HTML in cache using atomic write (.tmp → rename)."""
        path = self._path(url)
        tmp_path = path.with_suffix(".tmp")
        try:
            data = json.dumps({"url": url, "html": html, "timestamp": time.time()})
            tmp_path.write_text(data, encoding="utf-8")
            os.replace(tmp_path, path)  # atomic on Windows and POSIX
        except Exception as e:
            logger.debug(f"Cache write failed for {url}: {e}")
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses
