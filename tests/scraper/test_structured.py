"""Unit tests for html_to_structured() (PR 3.2) in src/scraper/structured.py."""


from src.scraper.structured import ContentBlock, StructuredPage, html_to_structured

_URL = "https://docs.example.com/page"


def _blocks_of_type(page: StructuredPage, block_type: str) -> list[ContentBlock]:
    """Return all blocks of the given type from a StructuredPage."""
    return [b for b in page.blocks if b.type == block_type]


class TestHtmlToStructuredHeadings:
    """Tests for heading block extraction."""

    def test_h1_produces_heading_block_with_level_1(self):
        """<h1>Title</h1> produces a ContentBlock of type 'heading' with level=1."""
        page = html_to_structured(_URL, "<body><h1>Title</h1></body>")

        headings = _blocks_of_type(page, "heading")
        assert len(headings) == 1
        assert headings[0].content == "Title"
        assert headings[0].level == 1

    def test_h2_produces_heading_block_with_level_2(self):
        """<h2> maps to level=2 in the ContentBlock."""
        page = html_to_structured(_URL, "<body><h2>Section</h2></body>")

        headings = _blocks_of_type(page, "heading")
        assert any(h.level == 2 for h in headings)

    def test_h6_produces_heading_block_with_level_6(self):
        """<h6> maps to level=6 in the ContentBlock."""
        page = html_to_structured(_URL, "<body><h6>Deep</h6></body>")

        headings = _blocks_of_type(page, "heading")
        assert any(h.level == 6 for h in headings)


class TestHtmlToStructuredParagraphs:
    """Tests for paragraph block extraction."""

    def test_p_tag_produces_paragraph_block(self):
        """<p>text</p> produces a ContentBlock of type 'paragraph'."""
        page = html_to_structured(_URL, "<body><p>Hello, world!</p></body>")

        paragraphs = _blocks_of_type(page, "paragraph")
        assert len(paragraphs) >= 1
        assert any("Hello" in p.content for p in paragraphs)


class TestHtmlToStructuredCode:
    """Tests for code block extraction."""

    def test_pre_code_with_language_class_produces_code_block(self):
        """<pre><code class='language-python'>x=1</code></pre> produces a code block
        with language='python'."""
        html = '<body><pre><code class="language-python">x=1</code></pre></body>'
        page = html_to_structured(_URL, html)

        code_blocks = _blocks_of_type(page, "code")
        assert len(code_blocks) >= 1
        assert code_blocks[0].language == "python"
        assert "x=1" in code_blocks[0].content

    def test_pre_code_without_language_class_produces_code_block_with_no_language(self):
        """<pre><code>snippet</code></pre> produces a code block with language=None."""
        page = html_to_structured(_URL, "<body><pre><code>snippet</code></pre></body>")

        code_blocks = _blocks_of_type(page, "code")
        assert len(code_blocks) >= 1
        assert code_blocks[0].language is None


class TestHtmlToStructuredLists:
    """Tests for list block extraction."""

    def test_ul_produces_list_block(self):
        """<ul><li>a</li></ul> produces a ContentBlock of type 'list'."""
        page = html_to_structured(
            _URL, "<body><ul><li>item a</li><li>item b</li></ul></body>"
        )

        list_blocks = _blocks_of_type(page, "list")
        assert len(list_blocks) >= 1
        assert "item a" in list_blocks[0].content

    def test_ol_produces_list_block(self):
        """<ol><li>first</li></ol> also maps to type='list'."""
        page = html_to_structured(_URL, "<body><ol><li>first</li></ol></body>")

        list_blocks = _blocks_of_type(page, "list")
        assert len(list_blocks) >= 1


class TestHtmlToStructuredBlockquote:
    """Tests for blockquote block extraction."""

    def test_blockquote_produces_blockquote_block(self):
        """<blockquote>q</blockquote> produces a ContentBlock of type 'blockquote'."""
        page = html_to_structured(
            _URL, "<body><blockquote>Important note.</blockquote></body>"
        )

        blockquotes = _blocks_of_type(page, "blockquote")
        assert len(blockquotes) >= 1
        assert "Important note" in blockquotes[0].content


class TestHtmlToStructuredTitle:
    """Tests for page title extraction."""

    def test_title_tag_is_captured_in_structured_page_title(self):
        """<title>Page Title</title> is stored in StructuredPage.title."""
        html = "<html><head><title>Page Title</title></head><body><p>x</p></body></html>"
        page = html_to_structured(_URL, html)

        assert page.title == "Page Title"

    def test_missing_title_tag_results_in_none(self):
        """When there is no <title> element, StructuredPage.title is None."""
        page = html_to_structured(_URL, "<html><body><p>content</p></body></html>")

        assert page.title is None


class TestHtmlToStructuredEmptyElements:
    """Tests that empty or whitespace-only elements are excluded."""

    def test_empty_paragraph_is_not_added_as_block(self):
        """<p></p> or <p>   </p> should not produce a paragraph block."""
        page = html_to_structured(_URL, "<body><p></p><p>   </p></body>")

        paragraphs = _blocks_of_type(page, "paragraph")
        assert len(paragraphs) == 0

    def test_empty_heading_is_not_added_as_block(self):
        """<h1></h1> should not produce a heading block."""
        page = html_to_structured(_URL, "<body><h1></h1></body>")

        headings = _blocks_of_type(page, "heading")
        assert len(headings) == 0

    def test_url_stored_on_structured_page(self):
        """The url parameter is stored verbatim on the returned StructuredPage."""
        page = html_to_structured(_URL, "<p>content</p>")
        assert page.url == _URL
