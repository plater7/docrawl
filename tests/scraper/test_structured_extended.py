"""Extended tests for src/scraper/structured.py (PR 3.2).

Covers branches not reached by test_structured.py:
- Table block extraction
- Pre tag without inner code element
- Fallback paragraph for unrecognised tags with long text
- Container tags (section, article, main, aside, nav, header)
- html_to_structured with main/article/role=main content areas
- Short fallback text (< 20 chars) is excluded
- Image with empty src is excluded
"""

import json
from pathlib import Path

from src.scraper.structured import (
    ContentBlock,
    StructuredPage,
    html_to_structured,
    save_structured,
)

_URL = "https://docs.example.com/page"


def _blocks_of_type(page: StructuredPage, block_type: str) -> list[ContentBlock]:
    return [b for b in page.blocks if b.type == block_type]


# ---------------------------------------------------------------------------
# TestTableExtraction
# ---------------------------------------------------------------------------


class TestTableExtraction:
    """Tests for table block extraction."""

    def test_table_produces_table_block(self):
        """A <table> element produces a block of type 'table'."""
        html = """<body>
            <table>
                <tr><th>Name</th><th>Age</th></tr>
                <tr><td>Alice</td><td>30</td></tr>
            </table>
        </body>"""
        page = html_to_structured(_URL, html)
        tables = _blocks_of_type(page, "table")
        assert len(tables) >= 1

    def test_table_content_is_valid_json(self):
        """Table block content is valid JSON representing rows."""
        html = """<body>
            <table>
                <tr><th>Name</th><th>Age</th></tr>
                <tr><td>Alice</td><td>30</td></tr>
            </table>
        </body>"""
        page = html_to_structured(_URL, html)
        tables = _blocks_of_type(page, "table")
        assert len(tables) >= 1
        rows = json.loads(tables[0].content)
        assert isinstance(rows, list)
        assert len(rows) == 2

    def test_table_cells_extracted_correctly(self):
        """Cell text is correctly extracted into the JSON rows."""
        html = """<body>
            <table>
                <tr><td>foo</td><td>bar</td></tr>
            </table>
        </body>"""
        page = html_to_structured(_URL, html)
        tables = _blocks_of_type(page, "table")
        rows = json.loads(tables[0].content)
        assert rows[0] == ["foo", "bar"]

    def test_empty_table_produces_no_block(self):
        """A <table> with no rows does not produce a table block."""
        html = "<body><table></table></body>"
        page = html_to_structured(_URL, html)
        tables = _blocks_of_type(page, "table")
        assert len(tables) == 0


# ---------------------------------------------------------------------------
# TestPreTagWithoutCode
# ---------------------------------------------------------------------------


class TestPreTagWithoutCode:
    """Tests for <pre> tags not wrapping a <code> element."""

    def test_pre_without_code_element_uses_text_directly(self):
        """<pre>text</pre> without inner <code> still produces a code block."""
        html = "<body><pre>raw preformatted text here</pre></body>"
        page = html_to_structured(_URL, html)
        code_blocks = _blocks_of_type(page, "code")
        assert len(code_blocks) >= 1
        assert "raw preformatted text" in code_blocks[0].content


# ---------------------------------------------------------------------------
# TestContainerTags
# ---------------------------------------------------------------------------


class TestContainerTags:
    """Tests for recursion into container tags."""

    def test_section_tag_recurses(self):
        """Content inside <section> is parsed into blocks."""
        html = "<body><section><p>Section content here.</p></section></body>"
        page = html_to_structured(_URL, html)
        paras = _blocks_of_type(page, "paragraph")
        assert any("Section content" in p.content for p in paras)

    def test_article_tag_recurses(self):
        """Content inside <article> is parsed into blocks."""
        html = "<body><article><p>Article content here.</p></article></body>"
        page = html_to_structured(_URL, html)
        paras = _blocks_of_type(page, "paragraph")
        assert any("Article content" in p.content for p in paras)

    def test_aside_tag_recurses(self):
        """Content inside <aside> is parsed into blocks."""
        html = "<body><aside><p>Sidebar information here.</p></aside></body>"
        page = html_to_structured(_URL, html)
        paras = _blocks_of_type(page, "paragraph")
        assert any("Sidebar information" in p.content for p in paras)

    def test_header_tag_recurses(self):
        """Content inside <header> is parsed into blocks."""
        html = "<body><header><h1>Page Header Title</h1></header></body>"
        page = html_to_structured(_URL, html)
        headings = _blocks_of_type(page, "heading")
        assert any("Page Header Title" in h.content for h in headings)


# ---------------------------------------------------------------------------
# TestContentAreaSelection
# ---------------------------------------------------------------------------


class TestContentAreaSelection:
    """Tests for main content area selection logic."""

    def test_main_tag_preferred_over_body(self):
        """Content inside <main> is used as the primary content area."""
        html = """<body>
            <div><p>Navigation text outside main.</p></div>
            <main><h1>Main Content Heading</h1></main>
        </body>"""
        page = html_to_structured(_URL, html)
        headings = _blocks_of_type(page, "heading")
        assert any("Main Content Heading" in h.content for h in headings)

    def test_article_preferred_when_no_main(self):
        """When no <main>, content inside <article> is used."""
        html = """<body>
            <article><h2>Article Heading Here</h2></article>
        </body>"""
        page = html_to_structured(_URL, html)
        headings = _blocks_of_type(page, "heading")
        assert any("Article Heading Here" in h.content for h in headings)

    def test_role_main_preferred_when_no_main_or_article(self):
        """When no <main> or <article>, div[role=main] is used."""
        html = """<body>
            <div role="main"><p>Role main content here.</p></div>
        </body>"""
        page = html_to_structured(_URL, html)
        paras = _blocks_of_type(page, "paragraph")
        assert any("Role main content" in p.content for p in paras)


# ---------------------------------------------------------------------------
# TestFallbackParagraph
# ---------------------------------------------------------------------------


class TestFallbackParagraph:
    """Tests for the unrecognised-tag fallback paragraph logic."""

    def test_unrecognised_tag_with_long_text_produces_paragraph(self):
        """An unrecognised tag with > 20 chars of text produces a paragraph block."""
        html = "<body><span>This is a sufficiently long text span that exceeds twenty characters.</span></body>"
        page = html_to_structured(_URL, html)
        paras = _blocks_of_type(page, "paragraph")
        assert len(paras) >= 1

    def test_unrecognised_tag_with_short_text_excluded(self):
        """An unrecognised tag with <= 20 chars of text is excluded (noise guard)."""
        # "Hi" is well under 20 chars
        html = "<body><span>Hi</span></body>"
        page = html_to_structured(_URL, html)
        # Should not produce a paragraph block for just "Hi"
        paras = _blocks_of_type(page, "paragraph")
        assert not any(p.content == "Hi" for p in paras)


# ---------------------------------------------------------------------------
# TestImageEdgeCases
# ---------------------------------------------------------------------------


class TestImageEdgeCases:
    """Tests for image extraction edge cases."""

    def test_image_with_empty_src_not_added(self):
        """<img src=''>  without src should not produce an image block."""
        html = '<body><img alt="no src here"></body>'
        page = html_to_structured(_URL, html)
        images = _blocks_of_type(page, "image")
        assert len(images) == 0

    def test_image_empty_alt_yields_none(self):
        """<img alt=''>  produces image block with alt=None."""
        html = '<body><img src="https://example.com/img.png" alt=""></body>'
        page = html_to_structured(_URL, html)
        images = _blocks_of_type(page, "image")
        assert len(images) >= 1
        assert images[0].alt is None


# ---------------------------------------------------------------------------
# TestSaveStructuredEdgeCases
# ---------------------------------------------------------------------------


class TestSaveStructuredEdgeCases:
    """Additional tests for save_structured() edge cases."""

    def test_save_multiple_blocks(self, tmp_path: Path):
        """save_structured() handles pages with many blocks."""
        blocks = [
            ContentBlock(type="heading", content=f"Heading {i}", level=2)
            for i in range(5)
        ]
        page = StructuredPage(url=_URL, title="Multi-block", blocks=blocks)
        out = tmp_path / "multi.json"
        save_structured(page, out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert len(data["blocks"]) == 5

    def test_save_block_with_all_fields(self, tmp_path: Path):
        """save_structured() correctly serialises a block with all optional fields."""
        block = ContentBlock(
            type="code",
            content="print('hello')",
            language="python",
            level=None,
            alt=None,
        )
        page = StructuredPage(url=_URL, title="Code page", blocks=[block])
        out = tmp_path / "code.json"
        save_structured(page, out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["blocks"][0]["language"] == "python"
        assert data["blocks"][0]["content"] == "print('hello')"

    def test_save_empty_blocks_list(self, tmp_path: Path):
        """save_structured() handles a page with no blocks."""
        page = StructuredPage(url=_URL, title="Empty", blocks=[])
        out = tmp_path / "empty.json"
        save_structured(page, out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["blocks"] == []
