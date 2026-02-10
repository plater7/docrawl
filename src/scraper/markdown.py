"""HTML to Markdown conversion and chunking."""

import logging
from markdownify import markdownify as md

logger = logging.getLogger(__name__)

# Default chunk size for LLM processing (in characters)
DEFAULT_CHUNK_SIZE = 8000
CHUNK_OVERLAP = 200


def html_to_markdown(html: str) -> str:
    """Convert HTML to Markdown using markdownify."""
    return md(html, heading_style="ATX", strip=["script", "style", "nav", "footer"])


def chunk_markdown(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    """
    Split markdown into chunks for LLM processing.

    Tries to split at paragraph boundaries.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    current_pos = 0

    while current_pos < len(text):
        end_pos = min(current_pos + chunk_size, len(text))

        # Try to find a good break point (paragraph)
        if end_pos < len(text):
            # Look for double newline (paragraph break)
            break_pos = text.rfind("\n\n", current_pos, end_pos)
            if break_pos > current_pos + chunk_size // 2:
                end_pos = break_pos + 2
            else:
                # Fall back to single newline
                break_pos = text.rfind("\n", current_pos, end_pos)
                if break_pos > current_pos + chunk_size // 2:
                    end_pos = break_pos + 1

        chunk = text[current_pos:end_pos].strip()
        if chunk:
            chunks.append(chunk)

        # Move position with overlap for context continuity
        current_pos = end_pos - CHUNK_OVERLAP if end_pos < len(text) else end_pos

    logger.info(f"Split markdown into {len(chunks)} chunks")
    return chunks
