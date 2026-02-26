"""LLM-based markdown cleanup with smart skip and dynamic timeouts."""

import asyncio
import re
import logging
from typing import Any

from src.llm.client import generate

logger = logging.getLogger(__name__)

CLEANUP_SYSTEM_PROMPT = """You are a documentation cleaner. Clean up markdown from HTML docs.
Remove navigation residue, footers, ads, fix formatting. Keep all documentation content intact."""

CLEANUP_PROMPT_TEMPLATE = """Clean this markdown. Remove nav menus, breadcrumbs, footer, sidebar residue, ads, broken formatting.
Keep all documentation content, code examples, and links.
Return only cleaned markdown.

{markdown}"""

MAX_RETRIES = 2
RETRY_BACKOFF = [1, 3]  # seconds

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


def needs_llm_cleanup(markdown: str) -> bool:
    """Check if a chunk needs LLM cleanup or is already clean.

    Returns False for chunks that are mostly code or short clean text.
    """
    lower = markdown.lower()

    # Check for noise indicators
    has_noise = any(indicator in lower for indicator in _NOISE_INDICATORS)
    if has_noise:
        return True

    # Check code block density — mostly code chunks are clean
    code_blocks = _CODE_BLOCK_RE.findall(markdown)
    code_chars = sum(len(b) for b in code_blocks)
    if code_chars > len(markdown) * 0.6:
        return False

    # Short clean text doesn't need LLM
    if len(markdown) < 2000:
        return False

    return True


def _cleanup_options(markdown: str) -> dict[str, Any]:
    """Calculate Ollama options optimized for cleanup tasks.

    num_ctx is sized to the actual content so Ollama never silently truncates
    the input — closes CONS-011 / issue #57.
    """
    # Rough estimate: 1 token ≈ 4 chars for English/markdown
    estimated_input_tokens = len(markdown) // 4
    # Reserve ~512 tokens for system prompt + cleanup prompt overhead
    num_ctx = max(2048, estimated_input_tokens + 1024)
    return {
        "num_ctx": num_ctx,
        "num_predict": min(estimated_input_tokens + 512, 4096),
        "temperature": 0.1,
        "num_batch": 1024,
    }


def _calculate_timeout(content: str) -> int:
    """Calculate dynamic timeout based on chunk size."""
    content_kb = len(content) / 1024
    timeout = int(BASE_TIMEOUT + content_kb * TIMEOUT_PER_KB)
    return min(timeout, MAX_TIMEOUT)


async def cleanup_markdown(markdown: str, model: str) -> str:
    """Use LLM to clean up markdown content.

    Uses dynamic timeout based on chunk size. Retries with backoff.
    Returns original content if all retries fail.
    """
    prompt = CLEANUP_PROMPT_TEMPLATE.format(markdown=markdown)
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
                await asyncio.sleep(RETRY_BACKOFF[attempt])

    logger.error("All cleanup attempts failed, returning original")
    return markdown
