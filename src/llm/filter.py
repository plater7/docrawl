"""LLM-based URL filtering."""

import asyncio
import json
import logging
from typing import Any

from src.llm.client import generate

logger = logging.getLogger(__name__)

FILTER_SYSTEM_PROMPT = """You are a documentation URL filter. Given a list of URLs from a documentation website,
filter out URLs that are not documentation content (e.g., blog posts, changelogs, API references if not requested).
Return only the filtered list of URLs in JSON format."""

FILTER_PROMPT_TEMPLATE = """Filter these documentation URLs, keeping only actual documentation pages.
Remove: blog posts, changelogs, release notes, download pages, asset files.
Keep: guides, tutorials, concepts, reference docs, getting started.

URLs:
{urls}

Return a JSON array of filtered URLs, ordered by suggested reading order (basics first, advanced later).
Only return the JSON array, no other text."""


def _filter_options(urls: list[str]) -> dict[str, Any]:
    """Build Ollama options scaled to the actual URL list size.

    Avoids silent truncation when sites have 100+ URLs — closes CONS-011 / issue #57.
    """
    # Each URL averages ~60 chars ≈ 15 tokens; add prompt overhead (~300 tokens)
    estimated_input_tokens = sum(len(u) for u in urls) // 4 + 300
    num_ctx = max(4096, estimated_input_tokens + 1024)
    return {
        "num_ctx": num_ctx,
        "num_predict": min(len(urls) * 20 + 256, 4096),  # output ≤ input URLs reprinted
        "temperature": 0.0,
        "num_batch": 1024,
    }


FILTER_MAX_RETRIES = 3


async def filter_urls_with_llm(urls: list[str], model: str) -> list[str]:
    """
    Use LLM to filter and order documentation URLs.

    Retries up to FILTER_MAX_RETRIES times with exponential backoff.
    Falls back to original list if all retries fail.
    """
    if not urls:
        return urls

    # Wrap URLs in XML delimiters to isolate user content from prompt — closes CONS-006 / issue #58
    urls_block = "<urls>\n" + "\n".join(urls) + "\n</urls>"
    prompt = FILTER_PROMPT_TEMPLATE.format(urls=urls_block)

    for attempt in range(FILTER_MAX_RETRIES):
        try:
            response = await generate(
                model, prompt, system=FILTER_SYSTEM_PROMPT, options=_filter_options(urls)
            )

            # Try to parse JSON from response
            # Handle potential markdown code blocks
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1])

            filtered = json.loads(response)
            if isinstance(filtered, list):
                # Validate all items are from original list
                valid = [url for url in filtered if url in urls]
                logger.info(f"LLM filtered {len(urls)} URLs to {len(valid)}")
                return valid

        except Exception as e:
            if attempt < FILTER_MAX_RETRIES - 1:
                wait = 2**attempt  # 1s, 2s, 4s
                logger.warning(
                    f"LLM filtering attempt {attempt + 1} failed, retrying in {wait}s: {e}"
                )
                await asyncio.sleep(wait)
            else:
                logger.warning(
                    f"LLM filtering failed after {FILTER_MAX_RETRIES} attempts, using original list: {e}"
                )

    return urls
