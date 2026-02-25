"""LLM-based URL filtering."""

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


FILTER_OPTIONS: dict[str, Any] = {
    "num_ctx": 4096,
    "num_predict": 2048,
    "temperature": 0.0,
    "num_batch": 1024,
}


async def filter_urls_with_llm(urls: list[str], model: str) -> list[str]:
    """
    Use LLM to filter and order documentation URLs.

    Falls back to original list if LLM fails.
    """
    if not urls:
        return urls

    # Wrap URLs in XML delimiters to isolate user content from prompt — closes CONS-006 / issue #58
    urls_block = "<urls>\n" + "\n".join(urls) + "\n</urls>"
    prompt = FILTER_PROMPT_TEMPLATE.format(urls=urls_block)

    try:
        response = await generate(
            model, prompt, system=FILTER_SYSTEM_PROMPT, options=FILTER_OPTIONS
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
        logger.warning(f"LLM filtering failed, using original list: {e}")

    return urls
