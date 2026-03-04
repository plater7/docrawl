"""Extended tests for src/llm/cleanup.py.

Covers the branches and lines not reached by test_cleanup.py and
test_cleanup_heuristics.py:
- _has_latex: dollar-sign only match with multiple prices (not latex)
- _has_latex: single match but it's a price (returns False)
- _code_density: empty string returns 0.0
- classify_chunk: long text without noise or tables/latex returns "cleanup"
- classify_chunk: code density > 0.6 even with noise returns "skip"
- _cleanup_options: large content num_ctx > 2048
- needs_llm_cleanup: "heavy" level returns True
"""

from src.llm.cleanup import (
    _code_density,
    _has_latex,
    classify_chunk,
    needs_llm_cleanup,
    _cleanup_options,
    _estimate_tokens,
)


# ---------------------------------------------------------------------------
# TestCodeDensity
# ---------------------------------------------------------------------------


class TestCodeDensity:
    """Tests for _code_density()."""

    def test_empty_string_returns_zero(self):
        """Empty markdown has 0.0 code density."""
        assert _code_density("") == 0.0

    def test_no_code_blocks_returns_zero(self):
        """Pure prose without code fences returns 0.0."""
        text = "This is a documentation paragraph with no code."
        assert _code_density(text) == 0.0

    def test_all_code_returns_one(self):
        """Text entirely composed of a code block returns ~1.0."""
        text = "```\ncode here\n```"
        density = _code_density(text)
        assert density == 1.0

    def test_half_code_half_prose(self):
        """Mixed text returns density between 0 and 1."""
        code_block = "```\n" + "x = 1\n" * 10 + "```"
        prose = "A" * len(code_block)
        text = prose + code_block
        density = _code_density(text)
        assert 0.3 < density < 0.7


# ---------------------------------------------------------------------------
# TestHasLatexExtended
# ---------------------------------------------------------------------------


class TestHasLatexExtended:
    """Additional _has_latex() tests for edge cases."""

    def test_single_dollar_sign_match_with_price_returns_false(self):
        """When only dollar-sign pattern matches and there are prices, returns False."""
        # "$9.99" triggers _PRICE_RE — the one dollar match is a price not latex
        markdown = "Only $9.99 price here, no real math."
        assert _has_latex(markdown) is False

    def test_latex_command_without_dollar_signs_detected(self):
        """LaTeX \\command{ pattern is detected even without dollar signs."""
        markdown = r"See \frac{a}{b} for the formula."
        assert _has_latex(markdown) is True

    def test_begin_end_environment_detected(self):
        """\\begin{} and \\end{} are detected as LaTeX."""
        markdown = r"\begin{equation} x = 1 \end{equation}"
        assert _has_latex(markdown) is True

    def test_multiple_prices_no_latex_commands(self):
        """Multiple price patterns with no LaTeX commands returns False."""
        markdown = "Buy for $9.99 or upgrade for $29.99."
        assert _has_latex(markdown) is False

    def test_latex_inline_math_dollar_expr_not_price(self):
        r"""$x + y$ expression (not a price) is detected as LaTeX."""
        # Matches _LATEX_PATTERNS: $[^$\d][^$]*$ — starts with non-digit
        markdown = r"The sum is $x + y$ where both are positive."
        assert _has_latex(markdown) is True


# ---------------------------------------------------------------------------
# TestClassifyChunkExtended
# ---------------------------------------------------------------------------


class TestClassifyChunkExtended:
    """Additional classify_chunk() tests for uncovered branches."""

    def test_long_text_no_noise_no_tables_no_latex_returns_cleanup(self):
        """Long text (>= 2000 chars) without noise, tables, or latex returns 'cleanup'."""
        # Build text over 2000 chars that has no noise indicators or special content
        text = "This is documentation content. " * 70  # ~2100 chars
        assert len(text) >= 2000
        # No noise, no broken tables, no latex
        result = classify_chunk(text)
        assert result == "cleanup"

    def test_code_dense_with_noise_still_returns_skip(self):
        """Even if noise is present, code density > 0.6 wins and returns 'skip'."""
        # Build a large code block that dominates (> 60%)
        code_block = "```python\n" + ("x = 1  # comment\n" * 100) + "```"
        tiny_noise = "cookie"
        text = tiny_noise + code_block
        result = classify_chunk(text)
        assert result == "skip"

    def test_heavy_level_makes_needs_llm_cleanup_return_true(self):
        """needs_llm_cleanup returns True for 'heavy' classified chunks."""
        # Create a chunk that will be classified as 'heavy' (broken table + long)
        # The table rows must each be on their own line for the MULTILINE regex
        filler = "Documentation paragraph. " * 100  # > 2000 chars
        table = "\n| A | B |\n| v | w |"  # broken table (no separator), own lines
        text = filler + table
        assert classify_chunk(text) == "heavy"
        assert needs_llm_cleanup(text) is True

    def test_short_text_with_noise_needs_cleanup(self):
        """Short text with noise returns 'cleanup', not 'skip'."""
        # 'cookie' indicator in short text makes it need cleanup
        text = "Accept cookie policy. This is a brief doc section."
        assert len(text) < 2000
        result = classify_chunk(text)
        assert result == "cleanup"

    def test_cleanup_level_makes_needs_llm_cleanup_true(self):
        """needs_llm_cleanup returns True for 'cleanup' classified chunks."""
        # Long text without tables/latex → "cleanup"
        text = "Documentation sentence. " * 90  # > 2000 chars
        assert classify_chunk(text) == "cleanup"
        assert needs_llm_cleanup(text) is True


# ---------------------------------------------------------------------------
# TestCleanupOptionsExtended
# ---------------------------------------------------------------------------


class TestCleanupOptionsExtended:
    """Additional _cleanup_options() tests."""

    def test_num_ctx_exceeds_2048_for_large_content(self):
        """Large content produces num_ctx > 2048."""
        # 12000 chars → ~3000 tokens → num_ctx = max(2048, 3000+1024) = 4024
        markdown = "x" * 12000
        opts = _cleanup_options(markdown)
        assert opts["num_ctx"] > 2048

    def test_num_batch_is_set(self):
        """num_batch key is present in options."""
        opts = _cleanup_options("some text")
        assert "num_batch" in opts
        assert opts["num_batch"] == 1024

    def test_options_include_all_required_keys(self):
        """All required Ollama option keys are present."""
        opts = _cleanup_options("content")
        for key in ("num_ctx", "num_predict", "temperature", "num_batch"):
            assert key in opts


# ---------------------------------------------------------------------------
# TestEstimateTokensExtended
# ---------------------------------------------------------------------------


class TestEstimateTokensExtended:
    """Additional _estimate_tokens() tests for ratio branches."""

    def test_empty_string_returns_one(self):
        """Empty string returns max(1, ...) = 1."""
        assert _estimate_tokens("") == 1

    def test_mixed_code_uses_35_ratio(self):
        """Content with code density between 0.2 and 0.5 uses ratio 3.5."""
        # Build text with ~30% code (between 0.2 and 0.5 density)
        code_block = "```\n" + "y=1\n" * 30 + "```"  # ~120 chars
        prose = "A" * 280  # ~280 chars → total ~400, code ~30%
        text = prose + code_block
        density = sum(
            len(b) for b in __import__("re").findall(r"```[\s\S]*?```", text)
        ) / len(text)
        assert 0.2 < density < 0.5
        est = _estimate_tokens(text)
        # ratio 3.5 → len/3.5 ≈ 400/3.5 ≈ 114
        assert est == max(1, int(len(text) / 3.5))

    def test_prose_uses_40_ratio(self):
        """Pure prose (no code blocks) uses ratio 4.0."""
        text = "Hello world documentation. " * 20  # ~540 chars, no code
        est = _estimate_tokens(text)
        assert est == max(1, int(len(text) / 4.0))

    def test_code_heavy_uses_30_ratio(self):
        """Code-heavy content (density > 0.5) uses ratio 3.0."""
        code_block = "```python\n" + "x = 1\n" * 200 + "```"
        filler = "x"  # minimal prose
        text = filler + code_block
        est = _estimate_tokens(text)
        assert est == max(1, int(len(text) / 3.0))
