"""HTML to Markdown conversion, pre-cleaning, and chunking."""

import re
import logging

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


def html_to_markdown(html: str, converter_name: str | None = None) -> str:
    """Convert HTML to Markdown using the converter registry (PR 3.4).

    converter_name: name of a registered converter (default: "markdownify").
    Backward compatible: when converter_name is None, uses the default converter
    whose output is identical to the original markdownify call.
    """
    from src.scraper.converters import get_converter

    converter = get_converter(converter_name)
    return converter.convert(html)


# Regex to find top-level headings (H1-H3) for semantic splitting (PR 2.1)
_HEADING_RE = re.compile(r"^(#{1,3})\s+", re.MULTILINE)
# Regex to find fenced code blocks for masking (PR 2.1)
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


def _mask_code_blocks(text: str) -> str:
    """Replace content inside fenced code blocks with spaces of equal length.

    This prevents # characters inside code blocks from being treated as
    heading boundaries during semantic chunking (PR 2.1).
    The returned string has the same character positions as the input.
    """

    def _blank(m: re.Match) -> str:
        # Keep the opening ``` and closing ``` fence markers; blank the content
        return " " * len(m.group(0))

    return _CODE_FENCE_RE.sub(_blank, text)


def _chunk_by_headings(text: str, chunk_size: int) -> list[str] | None:
    """Split markdown text at H1-H3 heading boundaries.

    Returns a list of sections, each starting with its heading.
    Returns None if fewer than 2 headings are found (fallback to size-based).
    Sections larger than chunk_size are further subdivided with _chunk_by_size().
    Code blocks are masked before scanning to avoid false heading matches.

    PR 2.1 — Semantic Chunking.
    """
    masked = _mask_code_blocks(text)
    heading_positions = [m.start() for m in _HEADING_RE.finditer(masked)]

    if len(heading_positions) < 2:
        return None

    sections: list[str] = []
    for idx, start in enumerate(heading_positions):
        end = (
            heading_positions[idx + 1]
            if idx + 1 < len(heading_positions)
            else len(text)
        )
        section = text[start:end].strip()
        if not section or len(section) < 50:
            continue
        if len(section) > chunk_size:
            # Subdivide oversized section
            sections.extend(_chunk_by_size(section, chunk_size))
        else:
            sections.append(section)

    return sections if sections else None


def _chunk_by_size(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    """Split text into chunks of at most chunk_size characters.

    Tries paragraph boundaries first, then single newlines, then hard-splits.
    Includes CHUNK_OVERLAP between consecutive chunks.
    This is the original chunking logic extracted from chunk_markdown() (PR 2.1).
    """
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
        if chunk and len(chunk) >= 50:
            chunks.append(chunk)

        current_pos = end_pos - CHUNK_OVERLAP if end_pos < len(text) else end_pos

    return chunks if chunks else [text.strip()]


def chunk_markdown(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    native_token_count: int | None = None,
) -> list[str]:
    """Split markdown into chunks for LLM processing.

    Pre-cleans markdown, then:
    1. Tries heading-based semantic splits (PR 2.1) — natural section boundaries.
    2. Falls back to size-based splitting if fewer than 2 headings are found.
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

    # PR 2.1: try semantic heading-based chunking first
    heading_chunks = _chunk_by_headings(text, chunk_size)
    if heading_chunks:
        logger.info(
            f"Split markdown into {len(heading_chunks)} semantic chunks (headings)"
        )
        return heading_chunks

    # Fallback: size-based chunking
    size_chunks = _chunk_by_size(text, chunk_size)
    logger.info(f"Split markdown into {len(size_chunks)} chunks (size-based)")
    return size_chunks if size_chunks else [text.strip()]
