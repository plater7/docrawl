"""Deterministic URL filtering."""

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

EXCLUDED_EXTENSIONS = {
    ".pdf", ".zip", ".tar", ".gz", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".wav", ".avi", ".mov",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".exe", ".dmg", ".deb", ".rpm",
}

EXCLUDED_PATTERNS = {
    "/blog/", "/changelog/", "/api-reference/",
    "/releases/", "/download/", "/assets/",
}

LANGUAGE_PATTERNS = {
    "en": ["/en/", "/en-us/", "/en-gb/", "/english/"],
    "es": ["/es/", "/es-es/", "/spanish/"],
    "fr": ["/fr/", "/fr-fr/", "/french/"],
    "de": ["/de/", "/de-de/", "/german/"],
    "ja": ["/ja/", "/jp/", "/japanese/"],
    "zh": ["/zh/", "/zh-cn/", "/zh-tw/", "/chinese/"],
    "pt": ["/pt/", "/pt-br/", "/portuguese/"],
    "ru": ["/ru/", "/russian/"],
    "ko": ["/ko/", "/kr/", "/korean/"],
}


def filter_urls(urls: list[str], base_url: str, language: str = "en") -> list[str]:
    """
    Apply deterministic filtering to URL list.

    - Only same domain/subpath
    - Exclude non-doc extensions
    - Exclude common non-doc patterns
    - Filter by language (default: English only)
    - Deduplicate
    """
    base_parsed = urlparse(base_url)
    base_domain = base_parsed.netloc
    base_path = base_parsed.path.rstrip("/")

    filtered: set[str] = set()

    for url in urls:
        parsed = urlparse(url)

        if parsed.netloc != base_domain:
            continue

        path = parsed.path.rstrip("/")
        if not (path == base_path or path.startswith(base_path + "/") or base_path == ""):
            continue

        if any(path.lower().endswith(ext) for ext in EXCLUDED_EXTENSIONS):
            continue

        if any(pattern in path.lower() for pattern in EXCLUDED_PATTERNS):
            continue

        if not _matches_language(path, language):
            continue

        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        filtered.add(normalized)

    logger.info(f"Filtered {len(urls)} URLs down to {len(filtered)} (language: {language})")
    return sorted(filtered)


def _matches_language(path: str, language: str) -> bool:
    """Check if URL path matches the target language."""
    if language == "all":
        return True
    
    path_lower = path.lower()
    
    lang_patterns = LANGUAGE_PATTERNS.get(language, [f"/{language}/"])
    for pattern in lang_patterns:
        if pattern in path_lower:
            return True
    
    other_langs = set(LANGUAGE_PATTERNS.keys()) - {language}
    for other_lang in other_langs:
        for pattern in LANGUAGE_PATTERNS[other_lang]:
            if pattern in path_lower:
                return False
    
    return True
