"""LLM-based markdown cleanup with smart skip and dynamic timeouts."""

import asyncio
import re
import logging
from typing import Any, Literal

from src.llm.client import generate

logger = logging.getLogger(__name__)

CLEANUP_SYSTEM_PROMPT = """You are a documentation cleaner. Clean up markdown from HTML docs.
Remove navigation residue, footers, ads, fix formatting. Keep all documentation content intact."""

CLEANUP_PROMPT_TEMPLATE = """Clean this markdown. Remove nav menus, breadcrumbs, footer, sidebar residue, ads, broken formatting.
Keep all documentation content, code examples, and links.
Return only cleaned markdown.

{markdown}"""

HEAVY_CLEANUP_PROMPT_TEMPLATE = """Clean this markdown. Remove nav menus, breadcrumbs, footer, sidebar residue, ads.
Additionally:
- Repair broken Markdown tables (add missing separator rows with ---)
- Fix LaTeX/math expressions: preserve \\frac{{}}{{}}, \\begin{{}}{{}}, $...$, etc.
- Restore correct table alignment and column structure.
Keep all documentation content, code examples, and links.
Return only cleaned markdown.

{markdown}"""

MAX_RETRIES = 3
# Exponential backoff: 1s, 2s, 4s (2**attempt)

# Dynamic timeout constants
BASE_TIMEOUT = 45  # seconds for small chunks
TIMEOUT_PER_KB = 10  # extra seconds per KB of content
MAX_TIMEOUT = 90  # cap

# Noise indicators for needs_llm_cleanup()
_NOISE_INDICATORS = [
    "cookie",
    "privacy policy",
    "terms of service",
    "subscribe",
    "toggle dark",
    "toggle light",
    "dark mode",
    "light mode",
    "skip to content",
    "table of contents",
    "on this page",
    "all rights reserved",
    "powered by",
]

_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")

# PR 2.2 — Expanded Heuristics
CleanupLevel = Literal["skip", "cleanup", "heavy"]

# Broken table heuristic: pipe-separated row without a separator row (---|---) nearby
_TABLE_ROW_RE = re.compile(r"^\|.+\|$", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|$", re.MULTILINE)

# LaTeX patterns (avoid false positives like $9.99)
_LATEX_PATTERNS = [
    re.compile(r"\\frac\{"),
    re.compile(r"\\begin\{"),
    re.compile(r"\\end\{"),
    re.compile(r"\\[a-zA-Z]+\{"),  # \command{
    re.compile(r"\$[^$\d][^$]*\$"),  # $expr$ but not $9.99
]
# Price-like patterns to subtract from LaTeX score
_PRICE_RE = re.compile(r"\$\d+[\d.,]*")


def _has_broken_tables(markdown: str) -> bool:
    """Return True if the markdown has table rows but no separator row."""
    table_rows = _TABLE_ROW_RE.findall(markdown)
    if len(table_rows) < 2:
        return False
    sep_rows = _TABLE_SEP_RE.findall(markdown)
    # If there are table rows but no separator at all, it's broken
    return len(sep_rows) == 0


def _has_latex(markdown: str) -> bool:
    """Return True if the markdown likely contains LaTeX math expressions.

    Mitigates false positives from price strings like $9.99 by requiring
    at least one unambiguous LaTeX command match.
    """
    latex_matches = sum(1 for p in _LATEX_PATTERNS if p.search(markdown))
    if latex_matches == 0:
        return False
    # If only dollar-sign matches and they look like prices, skip
    price_matches = len(_PRICE_RE.findall(markdown))
    if latex_matches == 1 and price_matches > 0:
        return False
    return True


def _code_density(markdown: str) -> float:
    """Return fraction of the markdown that is inside fenced code blocks."""
    if not markdown:
        return 0.0
    code_blocks = _CODE_BLOCK_RE.findall(markdown)
    code_chars = sum(len(b) for b in code_blocks)
    return code_chars / len(markdown)


def classify_chunk(markdown: str) -> CleanupLevel:
    """Classify a chunk by the level of LLM cleanup needed.

    Returns:
        "skip"    — chunk is already clean (mostly code, or short without noise)
        "cleanup" — standard LLM cleanup needed
        "heavy"   — cleanup + table repair + LaTeX fix needed (PR 2.2)
    """
    lower = markdown.lower()

    # Check for noise indicators — always needs at least cleanup
    has_noise = any(indicator in lower for indicator in _NOISE_INDICATORS)

    # Mostly-code chunks are clean
    if _code_density(markdown) > 0.6:
        return "skip"

    # Short clean text without noise
    if len(markdown) < 2000 and not has_noise:
        return "skip"

    # Heavy cleanup for complex content
    if _has_broken_tables(markdown) or _has_latex(markdown):
        return "heavy"

    if has_noise:
        return "cleanup"

    return "cleanup" if len(markdown) >= 2000 else "skip"


def needs_llm_cleanup(markdown: str) -> bool:
    """Check if a chunk needs LLM cleanup or is already clean.

    Backward-compatible wrapper around classify_chunk() (PR 2.2).
    Returns False only for "skip" level.
    """
    return classify_chunk(markdown) != "skip"


def _estimate_tokens(text: str) -> int:
    """Estimate token count using code-density-adjusted char/token ratios (PR 2.5).

    Ratios (chars per token):
    - code-heavy (density > 0.5): 3.0 — code tokens are shorter on average
    - mixed (density > 0.2):      3.5
    - prose:                       4.0

    This replaces the flat len(text) // 4 heuristic throughout cleanup and filter.
    """
    density = _code_density(text)
    if density > 0.5:
        ratio = 3.0
    elif density > 0.2:
        ratio = 3.5
    else:
        ratio = 4.0
    return max(1, int(len(text) / ratio))


def _cleanup_options(markdown: str) -> dict[str, Any]:
    """Calculate Ollama options optimized for cleanup tasks.

    num_ctx is sized to the actual content so Ollama never silently truncates
    the input — closes CONS-011 / issue #57.
    """
    estimated_input_tokens = _estimate_tokens(markdown)  # PR 2.5: adaptive ratio
    # Reserve ~512 tokens for system prompt + cleanup prompt overhead
    num_ctx = max(2048, estimated_input_tokens + 1024)
    return {
        "num_ctx": num_ctx,
        "num_predict": min(estimated_input_tokens + 512, 4096),
        "temperature": 0.1,
        "num_batch": 1024,
    }


def _calculate_timeout(content: str) -> int:
    """Calculate dynamic timeout based on chunk size and token estimate (PR 2.5)."""
    tokens = _estimate_tokens(content)
    timeout = int(BASE_TIMEOUT + (tokens / 250) * 10)
    return min(timeout, MAX_TIMEOUT)


async def cleanup_markdown(markdown: str, model: str) -> str:
    """Use LLM to clean up markdown content.

    Uses dynamic timeout based on chunk size. Retries with backoff.
    Selects standard or heavy prompt based on classify_chunk() (PR 2.2).
    Returns original content if all retries fail.
    """
    # Wrap content in XML delimiters to isolate scraped data from prompt — closes CONS-006 / issue #58
    wrapped = f"<document>\n{markdown}\n</document>"
    level = classify_chunk(markdown)
    template = HEAVY_CLEANUP_PROMPT_TEMPLATE if level == "heavy" else CLEANUP_PROMPT_TEMPLATE
    prompt = template.format(markdown=wrapped)
    timeout = _calculate_timeout(markdown)
    options = _cleanup_options(markdown)

    for attempt in range(MAX_RETRIES):
        try:
            cleaned = await generate(
                model,
                prompt,
                system=CLEANUP_SYSTEM_PROMPT,
                timeout=timeout,
                options=options,
            )
            if cleaned.strip():
                return cleaned.strip()
        except Exception as e:
            logger.warning(
                f"Cleanup attempt {attempt + 1} failed ({timeout}s timeout): {e}"
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)  # 1s, 2s, 4s

    logger.error("All cleanup attempts failed, returning original")
    return markdown
