"""Blocked-response detection and content deduplication (PR 2.3)."""

import hashlib
import re

# 8 patterns for common blocked/bot-check responses.
# Threshold: >= 2 matches required to classify as blocked.
# This mitigates false positives in security documentation that mentions
# CAPTCHAs or Cloudflare as topics (those typically only match 1 pattern).
_BLOCKED_PATTERNS = [
    re.compile(r"checking your browser", re.IGNORECASE),
    re.compile(r"\bcaptcha\b", re.IGNORECASE),
    re.compile(r"\baccess denied\b", re.IGNORECASE),
    re.compile(r"\bcloudflare\b", re.IGNORECASE),
    re.compile(r"\bray id\b", re.IGNORECASE),
    re.compile(r"please enable javascript", re.IGNORECASE),
    re.compile(r"ddos protection", re.IGNORECASE),
    re.compile(r"just a moment", re.IGNORECASE),
]

_BLOCKED_THRESHOLD = 2


def is_blocked_response(content: str) -> bool:
    """Return True if content looks like a bot-check / blocked response.

    Uses a threshold of 2 out of 8 patterns to reduce false positives
    on documentation pages that *discuss* CAPTCHAs or Cloudflare.
    """
    if not content:
        return False
    matches = sum(1 for p in _BLOCKED_PATTERNS if p.search(content))
    return matches >= _BLOCKED_THRESHOLD


def content_hash(markdown: str) -> str:
    """Return an MD5 hex digest of the normalised markdown.

    Normalisation: collapse whitespace + lowercase before hashing.
    Used for per-job deduplication (~32 bytes per hash, ~32KB for 1000 URLs).
    """
    normalised = re.sub(r"\s+", " ", markdown.strip().lower())
    return hashlib.md5(normalised.encode("utf-8"), usedforsecurity=False).hexdigest()
