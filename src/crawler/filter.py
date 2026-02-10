"""Deterministic URL filtering."""

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Extensions to exclude
EXCLUDED_EXTENSIONS = {
    ".pdf", ".zip", ".tar", ".gz", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".wav", ".avi", ".mov",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".exe", ".dmg", ".deb", ".rpm",
}

# Path patterns to exclude
EXCLUDED_PATTERNS = {
    "/blog/", "/changelog/", "/api-reference/",
    "/releases/", "/download/", "/assets/",
}


def filter_urls(urls: list[str], base_url: str) -> list[str]:
    """
    Apply deterministic filtering to URL list.

    - Only same domain/subpath
    - Exclude non-doc extensions
    - Exclude common non-doc patterns
    - Deduplicate
    """
    base_parsed = urlparse(base_url)
    base_domain = base_parsed.netloc
    base_path = base_parsed.path.rstrip("/")

    filtered: set[str] = set()

    for url in urls:
        parsed = urlparse(url)

        # Must be same domain
        if parsed.netloc != base_domain:
            continue

        # Must be under base path
        path = parsed.path.rstrip("/")
        if not path.startswith(base_path):
            continue

        # Check excluded extensions
        if any(path.lower().endswith(ext) for ext in EXCLUDED_EXTENSIONS):
            continue

        # Check excluded patterns
        if any(pattern in path.lower() for pattern in EXCLUDED_PATTERNS):
            continue

        # Normalize: remove fragment and query
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        filtered.add(normalized)

    logger.info(f"Filtered {len(urls)} URLs down to {len(filtered)}")
    return sorted(filtered)
