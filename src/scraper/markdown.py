"""HTML to Markdown conversion, pre-cleaning, and chunking."""

import re
import logging
from markdownify import markdownify as md

logger = logging.getLogger(__name__)

# Chunk size for LLM processing (in characters).
# 6000 chars ≈ 1500 tokens — fits safely in an 8192-token context window
# together with the system prompt and cleanup prompt overhead (~500 tokens).
# Fixes CONS-011 / issue #57: previous 16000-char chunks silently overflowed num_ctx.
DEFAULT_CHUNK_SIZE = 6000
CHUNK_OVERLAP = 200

# Regex patterns for noise in markdown (compiled for performance)
NOISE_PATTERNS = [
    re.compile(r"self\.__next_[a-zA-Z_]*", re.IGNORECASE),  # Next.js hydration
    re.compile(r"document\.querySelectorAll\([^)]*\)"),  # JS DOM manipulation
    re.compile(r"document\.getElementById\([^)]*\)"),
    re.compile(r"window\.addEventListener\([^)]*\)"),
    re.compile(r"data-page-mode\s*="),  # Framework attributes
    re.compile(r"suppressHydrationWarning"),
]

# Line-level noise patterns
NOISE_LINE_PATTERNS = [
    re.compile(r"^\s*On this page\s*$", re.IGNORECASE),
    re.compile(r"^\s*Edit this page\s*$", re.IGNORECASE),
    re.compile(r"^\s*Was this page helpful\??\s*$", re.IGNORECASE),
    re.compile(r"^\s*Last updated\s*(on\s+)?[\d/\-]+\s*$", re.IGNORECASE),
    re.compile(r"^\s*Skip to (main )?content\s*$", re.IGNORECASE),
    re.compile(r"^\s*Table of contents?\s*$", re.IGNORECASE),
    re.compile(r"^\s*Previous\s*$", re.IGNORECASE),
    re.compile(r"^\s*Next\s*$", re.IGNORECASE),
]


def _pre_clean_markdown(text: str) -> str:
    """Remove noise patterns from markdown before chunking."""
    # Remove lines matching noise patterns
    lines = text.split("\n")
    cleaned_lines: list[str] = []
    in_noise_block = False

    for line in lines:
        stripped = line.strip()

        # Skip CSS/JS blocks (lines between lone { and })
        if stripped == "{" and not in_noise_block:
            in_noise_block = True
            continue
        if in_noise_block:
            if stripped == "}" or stripped == "};":
                in_noise_block = False
            continue

        # Skip lines matching noise patterns
        if any(p.search(line) for p in NOISE_PATTERNS):
            continue

        # Skip noise lines
        if any(p.match(line) for p in NOISE_LINE_PATTERNS):
            continue

        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)

    # Collapse 3+ consecutive blank lines to 2
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def html_to_markdown(html: str) -> str:
    """Convert HTML to Markdown using markdownify."""
    return md(html, heading_style="ATX", strip=["script", "style", "nav", "footer"])


def chunk_markdown(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    native_token_count: int | None = None,
) -> list[str]:
    """Split markdown into chunks for LLM processing.

    Pre-cleans markdown, tries heading boundaries first, then paragraphs.
    Skips tiny fragments (< 50 chars).
    """
    # Pre-clean before chunking
    text = _pre_clean_markdown(text)

    # If server provided a token count and it fits in one chunk, skip splitting.
    # Rough heuristic: 1 token ≈ 4 chars, so multiply token count by 4 to compare.
    if native_token_count is not None and native_token_count * 4 <= chunk_size:
        return [text] if len(text) >= 50 else ([text] if text.strip() else [])

    if len(text) <= chunk_size:
        return [text] if len(text) >= 50 else ([text] if text.strip() else [])

    chunks: list[str] = []
    current_pos = 0

    while current_pos < len(text):
        end_pos = min(current_pos + chunk_size, len(text))

        if end_pos < len(text):
            # Try heading boundary first
            heading_pos = text.rfind("\n#", current_pos + chunk_size // 2, end_pos)
            if heading_pos > current_pos:
                end_pos = heading_pos + 1
            else:
                # Try paragraph boundary
                break_pos = text.rfind("\n\n", current_pos, end_pos)
                if break_pos > current_pos + chunk_size // 2:
                    end_pos = break_pos + 2
                else:
                    # Fall back to single newline
                    break_pos = text.rfind("\n", current_pos, end_pos)
                    if break_pos > current_pos + chunk_size // 2:
                        end_pos = break_pos + 1

        chunk = text[current_pos:end_pos].strip()
        if chunk and len(chunk) >= 50:  # Skip tiny fragments
            chunks.append(chunk)

        current_pos = end_pos - CHUNK_OVERLAP if end_pos < len(text) else end_pos

    logger.info(f"Split markdown into {len(chunks)} chunks (pre-cleaned)")
    return chunks if chunks else [text.strip()]
