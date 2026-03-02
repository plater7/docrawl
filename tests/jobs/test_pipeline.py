"""Unit tests for pipeline mode (src/jobs/runner.py) — PR 3.3."""

from src.jobs.runner import ScrapedPage, _PIPELINE_SENTINEL


class TestScrapedPage:
    """Tests for the ScrapedPage dataclass."""

    def test_can_be_constructed_with_all_fields(self):
        """ScrapedPage should accept all expected fields."""
        page = ScrapedPage(
            index=0,
            url="https://example.com/page",
            markdown="# Title\n\nContent.",
            raw_html="<h1>Title</h1><p>Content.</p>",
            native_token_count=42,
            fetch_method="playwright",
            load_time=1.23,
        )
        assert page.index == 0
        assert page.url == "https://example.com/page"
        assert page.markdown == "# Title\n\nContent."
        assert page.raw_html == "<h1>Title</h1><p>Content.</p>"
        assert page.native_token_count == 42
        assert page.fetch_method == "playwright"
        assert page.load_time == 1.23

    def test_raw_html_can_be_none(self):
        """raw_html is Optional — should accept None for non-Playwright paths."""
        page = ScrapedPage(
            index=1,
            url="https://example.com/fast",
            markdown="Fast content.",
            raw_html=None,
            native_token_count=None,
            fetch_method="http_fast",
            load_time=0.5,
        )
        assert page.raw_html is None
        assert page.native_token_count is None

    def test_fetch_method_reflects_path_used(self):
        """fetch_method field should store whichever fetch strategy was used."""
        for method in ("playwright", "http_fast", "proxy", "native", "cache"):
            page = ScrapedPage(
                index=0, url="u", markdown="m", raw_html=None,
                native_token_count=None, fetch_method=method, load_time=0.1,
            )
            assert page.fetch_method == method


class TestPipelineSentinel:
    """Tests for the pipeline SENTINEL value."""

    def test_sentinel_is_none(self):
        """_PIPELINE_SENTINEL must be None (falsy) so queue.get() can detect end."""
        assert _PIPELINE_SENTINEL is None

    def test_sentinel_identity_check(self):
        """Consumer loop uses `is _PIPELINE_SENTINEL` — must work with None."""
        item = None
        assert item is _PIPELINE_SENTINEL
