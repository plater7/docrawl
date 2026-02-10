"""LLM-based URL filtering."""

import json
import logging

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


async def filter_urls_with_llm(urls: list[str], model: str) -> list[str]:
    """
    Use LLM to filter and order documentation URLs.

    Falls back to original list if LLM fails.
    """
    if not urls:
        return urls

    logger.info(f"Sending {len(urls)} URLs to LLM for filtering")
    prompt = FILTER_PROMPT_TEMPLATE.format(urls="\n".join(urls))

    try:
        response = await generate(model, prompt, system=FILTER_SYSTEM_PROMPT)
        logger.debug(f"LLM filter raw response: {response}")

        # Try to parse JSON from response
        # Handle potential markdown code blocks
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])

        filtered = json.loads(response)
        if isinstance(filtered, list):
            # Validate all items are from original list
            original_set = set(urls)
            valid = [url for url in filtered if url in original_set]
            invalid = [url for url in filtered if url not in original_set]
            if invalid:
                logger.warning(f"LLM returned {len(invalid)} URLs not in original list, discarded")
            logger.info(f"LLM filtered {len(urls)} URLs to {len(valid)}")
            return valid

    except Exception as e:
        logger.warning(f"LLM filtering failed, using original list: {e}")

    return urls
