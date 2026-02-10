"""LLM-based markdown cleanup."""

import asyncio
import logging

from src.llm.client import generate

logger = logging.getLogger(__name__)

CLEANUP_SYSTEM_PROMPT = """You are a documentation cleaner. Your job is to clean up markdown
converted from HTML documentation pages. Remove navigation residue, footers, ads, and fix formatting issues.
Keep all actual documentation content intact."""

CLEANUP_PROMPT_TEMPLATE = """Clean up this markdown documentation. Remove:
- Navigation menus and breadcrumbs
- Footer content (copyright, links)
- Sidebar residue
- Advertisements
- Broken formatting

Keep all actual documentation content, code examples, and important links.
Return only the cleaned markdown, no explanations.

Markdown to clean:
{markdown}"""

MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]  # seconds


async def cleanup_markdown(markdown: str, model: str) -> str:
    """
    Use LLM to clean up markdown content.

    Retries with exponential backoff on failure.
    Returns original content if all retries fail.
    """
    prompt = CLEANUP_PROMPT_TEMPLATE.format(markdown=markdown)

    for attempt in range(MAX_RETRIES):
        logger.info(f"Cleanup attempt {attempt + 1}/{MAX_RETRIES}, chunk of {len(markdown)} chars")
        try:
            cleaned = await generate(model, prompt, system=CLEANUP_SYSTEM_PROMPT)
            if cleaned.strip():
                return cleaned.strip()
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                backoff = RETRY_BACKOFF[attempt]
                logger.warning(f"Cleanup attempt {attempt + 1} failed: {e}, retrying in {backoff}s")
                await asyncio.sleep(backoff)
            else:
                logger.warning(f"Cleanup attempt {attempt + 1} failed: {e}, no more retries")

    logger.info("All cleanup attempts failed, using raw markdown as fallback")
    return markdown
