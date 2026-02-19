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
    "en": ["/en/", "/en-us/", "/en-gb/", "/en-au/", "/en-ca/", "/en-in/", "/english/"],
    "es": ["/es/", "/es-es/", "/es-mx/", "/es-ar/", "/es-cl/", "/es-co/", "/spanish/"],
    "fr": ["/fr/", "/fr-fr/", "/fr-ca/", "/french/"],
    "de": ["/de/", "/de-de/", "/de-at/", "/de-ch/", "/german/"],
    "ja": ["/ja/", "/jp/", "/japanese/"],
    "zh": ["/zh/", "/zh-cn/", "/zh-tw/", "/zh-hk/", "/chinese/"],
    "pt": ["/pt/", "/pt-br/", "/pt-pt/", "/portuguese/"],
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
        if not path.startswith(base_path):
            continue

        if any(path.lower().endswith(ext) for ext in EXCLUDED_EXTENSIONS):
            continue

        if any(pattern in path.lower() for pattern in EXCLUDED_PATTERNS):
            continue

        if not _matches_language(path, language, base_url):
            continue

        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        filtered.add(normalized)

    logger.info(f"Filtered {len(urls)} URLs down to {len(filtered)} (language: {language})")
    return sorted(filtered)


def _matches_language(path: str, language: str, base_url: str = "") -> bool:
    """
    Check if URL path matches the target language.
    
    Strategy:
    1. If path contains target language → include
    2. If path contains OTHER language → exclude  
    3. If path has NO language prefix → use base_url to determine fallback
    """
    if language == "all":
        return True
    
    path_lower = path.lower()
    
    # Check for target language
    lang_patterns = LANGUAGE_PATTERNS.get(language, [f"/{language}/"])
    for pattern in lang_patterns:
        if pattern in path_lower:
            return True
    
    # Check for other languages
    other_langs = set(LANGUAGE_PATTERNS.keys()) - {language}
    for other_lang in other_langs:
        for pattern in LANGUAGE_PATTERNS[other_lang]:
            if pattern in path_lower:
                return False
    
    # No language pattern found in URL
    # If base_url has a language, assume URLs without prefix are same as base → include
    # If base_url has no language and URL has no language → include (be permissive)
    # If base_url has language but this URL doesn't → exclude (different language)
    if base_url:
        base_parsed = urlparse(base_url)
        base_path = base_parsed.path.lower()
        
        base_has_language = any(
            pattern in base_path 
            for patterns in LANGUAGE_PATTERNS.values() 
            for pattern in patterns
        )
        
        # If base has language but this URL doesn't → exclude
        if base_has_language:
            return False
    
    return True
