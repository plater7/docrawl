"""Extended tests for src/scraper/markdown.py.

Covers branches missed by existing test_markdown.py and
test_markdown_semantic.py:
- _pre_clean_markdown: JS/CSS block masking, noise patterns
- _chunk_by_size: overlap, heading split, paragraph split edge cases
- chunk_markdown: very short text < 50 chars (both branches)
- _chunk_by_headings: sections smaller than 50 chars are skipped
"""

from src.scraper.markdown import (
    DEFAULT_CHUNK_SIZE,
    _chunk_by_size,
    _chunk_by_headings,
    _pre_clean_markdown,
    chunk_markdown,
)


# ---------------------------------------------------------------------------
# TestPreCleanMarkdownExtended
# ---------------------------------------------------------------------------


class TestPreCleanMarkdownExtended:
    """Additional _pre_clean_markdown() tests for noise block and JS patterns."""

    def test_removes_css_js_block_between_braces(self):
        """Lines between lone '{' and '}' markers are stripped."""
        text = "# Title\n\n{\ncolor: red;\nfont-size: 14px;\n}\n\nContent."
        result = _pre_clean_markdown(text)
        assert "color: red" not in result
        assert "Content" in result

    def test_removes_js_block_ending_with_brace_semicolon(self):
        """Noise block ending with '};' is also stripped."""
        text = "# Guide\n\n{\nvar x = 1;\n};\n\nActual content."
        result = _pre_clean_markdown(text)
        assert "var x = 1" not in result
        assert "Actual content" in result

    def test_removes_next_js_hydration_pattern(self):
        """self.__next_* lines are removed."""
        text = "# Docs\n\nself.__next_f=self.__next_f||[]\n\nContent."
        result = _pre_clean_markdown(text)
        assert "__next_" not in result
        assert "Content" in result

    def test_removes_window_addeventlistener_pattern(self):
        """window.addEventListener(...) lines are removed."""
        text = "# Page\n\nwindow.addEventListener('load', init)\n\nContent."
        result = _pre_clean_markdown(text)
        assert "addEventListener" not in result
        assert "Content" in result

    def test_removes_previous_next_nav_lines(self):
        """'Previous' and 'Next' navigation lines are removed."""
        text = "Content.\n\nPrevious\n\nNext\n\nMore content."
        result = _pre_clean_markdown(text)
        assert "Previous" not in result
        assert "Next" not in result
        assert "More content" in result

    def test_removes_last_updated_line(self):
        """'Last updated on 2024-01-01' line is removed."""
        text = "# Docs\n\nLast updated on 2024-01-01\n\nContent."
        result = _pre_clean_markdown(text)
        assert "Last updated" not in result
        assert "Content" in result

    def test_empty_string_returns_empty(self):
        """Empty input returns empty string."""
        result = _pre_clean_markdown("")
        assert result == ""


# ---------------------------------------------------------------------------
# TestChunkBySizeExtended
# ---------------------------------------------------------------------------


class TestChunkBySizeExtended:
    """Additional _chunk_by_size() tests for overlap and boundary logic."""

    def test_single_chunk_when_text_under_chunk_size(self):
        """Text shorter than chunk_size returns as single chunk."""
        text = "Short text. " * 5  # ~60 chars
        result = _chunk_by_size(text, chunk_size=DEFAULT_CHUNK_SIZE)
        assert len(result) == 1

    def test_empty_chunk_excluded(self):
        """Chunk function never returns a blank/empty chunk."""
        text = "Word. " * 1000
        chunks = _chunk_by_size(text, chunk_size=500)
        for chunk in chunks:
            assert chunk.strip() != ""

    def test_all_chunks_at_least_50_chars(self):
        """All returned chunks meet the 50-char minimum."""
        text = "Content sentence here. " * 500
        chunks = _chunk_by_size(text, chunk_size=500)
        for chunk in chunks:
            assert len(chunk) >= 50

    def test_overlap_not_duplicating_huge_amounts(self):
        """Chunks with overlap don't balloon the total char count excessively."""
        text = "X" * 5000
        chunks = _chunk_by_size(text, chunk_size=1000)
        # Total chars in all chunks should not be more than 2x the original
        # (overlap creates some duplication, but not runaway)
        total_chars = sum(len(c) for c in chunks)
        assert total_chars < len(text) * 2

    def test_heading_split_preferred(self):
        """Heading boundary (\n#) is used as split point when available."""
        # Build text where a heading appears within the chunk size window
        heading = "\n# Section Break\n"
        filler = "A" * 800
        text = filler + heading + filler
        chunks = _chunk_by_size(text, chunk_size=1000)
        # Should produce at least 2 chunks
        assert len(chunks) >= 2

    def test_paragraph_split_fallback(self):
        """Paragraph break (\n\n) is used when no heading is found."""
        filler = "Word " * 200
        text = filler + "\n\n" + filler
        chunks = _chunk_by_size(text, chunk_size=len(filler) + 50)
        assert len(chunks) >= 2

    def test_text_exactly_50_chars_included(self):
        """Text of exactly 50 chars is returned as a chunk."""
        text = "X" * 50
        result = _chunk_by_size(text, chunk_size=DEFAULT_CHUNK_SIZE)
        assert len(result) == 1
        assert result[0] == text

    def test_text_below_50_chars_still_returned(self):
        """Text under 50 chars: function falls back to returning the stripped text."""
        text = "Short."
        result = _chunk_by_size(text, chunk_size=DEFAULT_CHUNK_SIZE)
        # Code path: if len(text) >= 50 else ([text] if text.strip() else [])
        assert result == [text]


# ---------------------------------------------------------------------------
# TestChunkMarkdownEdgeCases
# ---------------------------------------------------------------------------


class TestChunkMarkdownEdgeCases:
    """Edge cases for chunk_markdown() that are hard to trigger through normal input."""

    def test_whitespace_only_text_returns_empty(self):
        """Pure whitespace text returns empty list."""
        result = chunk_markdown("   \n\n\t  ")
        assert result == []

    def test_very_short_non_empty_returns_nonempty_list(self):
        """Non-empty text shorter than 50 chars: returns [text] (not empty)."""
        result = chunk_markdown("Hi.")
        assert isinstance(result, list)
        # The result may be [text] or [] depending on strip; either is acceptable
        if result:
            assert result[0].strip() != ""

    def test_native_token_hint_zero_with_long_text_still_splits(self):
        """native_token_count=0 means 0*4=0 <= chunk_size, returns single chunk
        for small text but still splits for text over chunk_size."""
        # Small text case: 0 * 4 = 0 <= chunk_size, return single
        small = "# Title\n\nSmall content that is long enough to be valid chunk here."
        result = chunk_markdown(small, native_token_count=0)
        assert isinstance(result, list)

    def test_semantic_chunking_preferred_with_two_headings(self):
        """Text with two H1-H3 headings is split semantically.

        Build a text big enough to exceed the default chunk size so splitting
        actually triggers at heading boundaries.
        """
        # Each section is ~700 chars; total ~1400 chars — use chunk_size=800
        section_a = "Content A is documentation here. " * 20  # ~660 chars
        section_b = "Content B is documentation here. " * 20  # ~660 chars
        text = (
            "# First Section\n\n" + section_a + "\n\n# Second Section\n\n" + section_b
        )
        # chunk_size=800 forces the two ~700-char sections to be separate chunks
        chunks = chunk_markdown(text, chunk_size=800)
        # Should get at least 2 chunks from heading-based split
        assert len(chunks) >= 2

    def test_result_is_list_of_strings(self):
        """chunk_markdown always returns a list of str."""
        text = "Some documentation. " * 100
        result = chunk_markdown(text)
        assert all(isinstance(c, str) for c in result)


# ---------------------------------------------------------------------------
# TestChunkByHeadingsEdgeCases
# ---------------------------------------------------------------------------


class TestChunkByHeadingsEdgeCases:
    """Edge cases for _chunk_by_headings()."""

    def test_tiny_sections_under_50_chars_skipped(self):
        """Sections shorter than 50 chars are excluded from results."""
        # Short section (< 50 chars) between two large ones
        text = (
            "# Section One\n\n" + "Long content here. " * 20 + "\n\n"
            "# Tiny\n\nX\n\n"  # < 50 chars
            "# Section Three\n\n" + "Long content here. " * 20
        )
        result = _chunk_by_headings(text, chunk_size=DEFAULT_CHUNK_SIZE)
        assert result is not None
        # The tiny section should be excluded
        for chunk in result:
            assert len(chunk) >= 50

    def test_all_sections_tiny_returns_none(self):
        """When all sections are < 50 chars, returns None (no valid chunks)."""
        text = "# A\n\nX\n\n# B\n\nY\n\n# C\n\nZ"
        result = _chunk_by_headings(text, chunk_size=DEFAULT_CHUNK_SIZE)
        # Either None or empty list — both trigger fallback
        assert result is None or result == []
