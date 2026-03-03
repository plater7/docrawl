"""Unit tests for semantic chunking helpers (PR 2.1) in src/scraper/markdown.py.

Covers: _mask_code_blocks, _chunk_by_headings.
"""

from src.scraper.markdown import (
    DEFAULT_CHUNK_SIZE,
    _chunk_by_headings,
    _mask_code_blocks,
)


class TestMaskCodeBlocks:
    """Tests for _mask_code_blocks()."""

    def test_replaces_code_block_content_with_spaces_of_same_length(self):
        """The masked string must have the same total length as the original."""
        original = "Before.\n```python\nx = 1\ny = 2\n```\nAfter."
        masked = _mask_code_blocks(original)
        assert len(masked) == len(original)

    def test_code_block_region_contains_only_spaces(self):
        """The region that was inside the fenced block should be all spaces."""
        code_block = "```python\nx = 1\n```"
        masked = _mask_code_blocks(code_block)
        assert masked.strip() == ""
        assert len(masked) == len(code_block)

    def test_preserves_text_outside_code_blocks(self):
        """Text before and after a fenced code block is left unchanged."""
        original = "Before text.\n```\ncode here\n```\nAfter text."
        masked = _mask_code_blocks(original)
        assert masked.startswith("Before text.")
        assert masked.endswith("After text.")

    def test_multiple_code_blocks_are_all_masked(self):
        """All fenced code blocks in the text are replaced, not just the first one."""
        original = "A.\n```\nblock one\n```\nB.\n```\nblock two\n```\nC."
        masked = _mask_code_blocks(original)
        # The fence markers are replaced by spaces too, so 'block one' and 'block two'
        # should no longer appear in the masked output
        assert "block one" not in masked
        assert "block two" not in masked

    def test_text_without_code_blocks_is_unchanged(self):
        """Text that has no fenced code blocks is returned as-is."""
        original = "# Title\n\nA paragraph.\n\nAnother paragraph."
        assert _mask_code_blocks(original) == original

    def test_empty_string_returns_empty_string(self):
        """An empty input produces an empty output."""
        assert _mask_code_blocks("") == ""


class TestChunkByHeadings:
    """Tests for _chunk_by_headings()."""

    def test_returns_none_for_text_with_fewer_than_two_headings(self):
        """Returns None when there is only one H1-H3 heading in the text."""
        text = "# Only One Heading\n\nSome content here without another heading."
        result = _chunk_by_headings(text, chunk_size=DEFAULT_CHUNK_SIZE)
        assert result is None

    def test_returns_none_for_text_with_no_headings(self):
        """Returns None when there are no headings at all."""
        text = "Just a paragraph.\n\nAnother paragraph."
        result = _chunk_by_headings(text, chunk_size=DEFAULT_CHUNK_SIZE)
        assert result is None

    def test_returns_one_chunk_per_h1_h3_section(self):
        """Returns a list with one chunk per top-level heading when there are ≥2."""
        text = (
            "# Section One\n\n" + "Content A. " * 20 + "\n\n"
            "# Section Two\n\n" + "Content B. " * 20 + "\n\n"
            "## Subsection\n\n" + "Content C. " * 20
        )
        result = _chunk_by_headings(text, chunk_size=DEFAULT_CHUNK_SIZE)
        assert result is not None
        assert len(result) == 3
        assert result[0].startswith("# Section One")
        assert result[1].startswith("# Section Two")
        assert result[2].startswith("## Subsection")

    def test_does_not_split_on_hash_inside_fenced_code_block(self):
        """A # character inside a fenced code block must not be treated as a heading."""
        # Build the trailing content separately so Python's * operator only
        # applies to this string and not the whole concatenated expression.
        trailing = "Some content after the second real heading.\n" * 5
        text = (
            "# Real Heading One\n\n"
            "```bash\n# This is a comment, not a heading\necho hello\n```\n\n"
            "# Real Heading Two\n\n" + trailing
        )
        result = _chunk_by_headings(text, chunk_size=DEFAULT_CHUNK_SIZE)
        assert result is not None
        # Only 2 real headings → 2 chunks (the comment # must not create a third)
        assert len(result) == 2

    def test_oversized_section_is_subdivided_into_multiple_chunks(self):
        """A section whose text exceeds chunk_size is further split into sub-chunks."""
        # Create a large section that clearly exceeds the chunk_size
        large_section_content = "Word content here. " * 500  # ~10 000 chars
        text = (
            "# First Heading\n\n"
            + large_section_content
            + "\n\n# Second Heading\n\nShort content here. " * 10
        )
        small_chunk = 500  # force the large section to be split
        result = _chunk_by_headings(text, chunk_size=small_chunk)
        assert result is not None
        # The large first section should produce more than one chunk
        assert len(result) > 2

    def test_returns_list_of_strings(self):
        """The return value is a list of strings when ≥2 headings are present."""
        text = (
            "# Alpha\n\n" + "Alpha content. " * 10 + "\n\n"
            "# Beta\n\n" + "Beta content. " * 10
        )
        result = _chunk_by_headings(text, chunk_size=DEFAULT_CHUNK_SIZE)
        assert result is not None
        assert all(isinstance(chunk, str) for chunk in result)
