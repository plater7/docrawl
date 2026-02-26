"""
Targeted unit tests for src/crawler/filter.py (filter_urls and _matches_language).

Focuses on scenarios from the CONS-009 coverage gap:
- Same domain only (cross-domain URLs excluded)
- Base path filtering (URLs not under base path excluded)
- Extension exclusion (.pdf, .zip, .png, etc.)
- Pattern exclusion (/blog/, /changelog/, /api-reference/)
- Deduplication
- Language filtering edge cases:
  - language="en" keeps /en/ paths, excludes /es/ paths
  - language="all" keeps everything
  - No language prefix included when base has no language
  - No language prefix excluded when base has language prefix
- Sorted output
"""


from src.crawler.filter import filter_urls, _matches_language


class TestSameDomainFiltering:
    """Cross-domain URLs must be excluded."""

    def test_cross_domain_excluded(self):
        """URLs on a different domain are dropped."""
        urls = [
            "https://docs.example.com/guide",
            "https://evil.com/injected",
            "https://docs.example.com/api",
        ]
        result = filter_urls(urls, "https://docs.example.com/")
        assert "https://evil.com/injected" not in result
        assert len(result) == 2

    def test_subdomain_treated_as_different_domain(self):
        """docs.example.com and api.example.com are different domains."""
        urls = [
            "https://docs.example.com/page",
            "https://api.example.com/page",
        ]
        result = filter_urls(urls, "https://docs.example.com/")
        assert len(result) == 1
        assert "https://docs.example.com/page" in result

    def test_same_domain_included(self):
        """All same-domain URLs are kept (before other filters)."""
        urls = [
            "https://docs.example.com/intro",
            "https://docs.example.com/install",
            "https://docs.example.com/guide",
        ]
        result = filter_urls(urls, "https://docs.example.com/")
        assert len(result) == 3


class TestBasePathFiltering:
    """URLs outside the base path must be excluded."""

    def test_url_outside_base_path_excluded(self):
        """URL outside base path is dropped."""
        urls = [
            "https://example.com/docs/guide",
            "https://example.com/marketing/pricing",
        ]
        result = filter_urls(urls, "https://example.com/docs/")
        assert len(result) == 1
        assert "https://example.com/docs/guide" in result

    def test_url_matching_base_path_included(self):
        """URLs that start with the base path are kept."""
        urls = [
            "https://example.com/docs/",
            "https://example.com/docs/intro",
            "https://example.com/docs/advanced/config",
        ]
        result = filter_urls(urls, "https://example.com/docs/")
        assert len(result) == 3

    def test_root_base_path_includes_all_same_domain(self):
        """Base path '/' means include all same-domain URLs."""
        urls = [
            "https://example.com/anything",
            "https://example.com/else/nested",
        ]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 2


class TestExtensionExclusion:
    """Non-doc file extensions must be excluded."""

    def test_pdf_excluded(self):
        """PDF files are excluded."""
        urls = ["https://example.com/manual.pdf", "https://example.com/page"]
        result = filter_urls(urls, "https://example.com/")
        assert "https://example.com/manual.pdf" not in result
        assert "https://example.com/page" in result

    def test_zip_excluded(self):
        """ZIP archives are excluded."""
        urls = ["https://example.com/release.zip", "https://example.com/page"]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1

    def test_png_excluded(self):
        """PNG images are excluded."""
        urls = ["https://example.com/logo.png", "https://example.com/page"]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1

    def test_mp4_excluded(self):
        """MP4 videos are excluded."""
        urls = ["https://example.com/demo.mp4", "https://example.com/page"]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1

    def test_svg_excluded(self):
        """SVG files are excluded."""
        urls = ["https://example.com/icon.svg", "https://example.com/page"]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1

    def test_docx_excluded(self):
        """DOCX files are excluded."""
        urls = ["https://example.com/spec.docx", "https://example.com/page"]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1

    def test_extension_check_case_insensitive(self):
        """.PDF uppercase is also excluded."""
        urls = ["https://example.com/doc.PDF", "https://example.com/page"]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1


class TestPatternExclusion:
    """Common non-doc URL patterns must be excluded."""

    def test_blog_excluded(self):
        """Paths containing /blog/ are excluded."""
        urls = [
            "https://example.com/blog/new-release",
            "https://example.com/docs/guide",
        ]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1
        assert "https://example.com/docs/guide" in result

    def test_changelog_excluded(self):
        """Paths containing /changelog/ are excluded."""
        urls = [
            "https://example.com/changelog/v2.0",
            "https://example.com/docs/guide",
        ]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1

    def test_api_reference_excluded(self):
        """Paths containing /api-reference/ are excluded."""
        urls = [
            "https://example.com/api-reference/endpoint",
            "https://example.com/docs/guide",
        ]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1

    def test_releases_excluded(self):
        """Paths containing /releases/ are excluded."""
        urls = [
            "https://example.com/releases/v3.0",
            "https://example.com/docs/guide",
        ]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1

    def test_download_excluded(self):
        """Paths containing /download/ are excluded."""
        urls = [
            "https://example.com/download/sdk",
            "https://example.com/docs/guide",
        ]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1

    def test_assets_excluded(self):
        """Paths containing /assets/ are excluded."""
        urls = [
            "https://example.com/assets/script.js",
            "https://example.com/docs/guide",
        ]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1


class TestDeduplication:
    """Duplicate URLs (after normalisation) should appear only once."""

    def test_exact_duplicates_deduplicated(self):
        """Exact same URL appears only once."""
        urls = [
            "https://example.com/page",
            "https://example.com/page",
            "https://example.com/page",
        ]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1

    def test_trailing_slash_variants_deduplicated(self):
        """URL with and without trailing slash normalise to the same entry."""
        urls = [
            "https://example.com/guide/",
            "https://example.com/guide",
        ]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 1

    def test_multiple_unique_urls_not_deduplicated(self):
        """Different URLs are all kept."""
        urls = [
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
        ]
        result = filter_urls(urls, "https://example.com/")
        assert len(result) == 3


class TestLanguageFilteringEnglish:
    """language='en' keeps /en/ paths and excludes /es/ paths."""

    def test_en_path_included(self):
        """/en/ URL is kept when language='en'."""
        urls = ["https://example.com/en/guide"]
        result = filter_urls(urls, "https://example.com/", language="en")
        assert "https://example.com/en/guide" in result

    def test_es_path_excluded(self):
        """/es/ URL is dropped when language='en'."""
        urls = ["https://example.com/es/guia", "https://example.com/en/guide"]
        result = filter_urls(urls, "https://example.com/", language="en")
        assert "https://example.com/es/guia" not in result
        assert "https://example.com/en/guide" in result

    def test_no_language_prefix_included_when_base_has_no_language(self):
        """URL with no language prefix is included if base URL also has no language."""
        urls = ["https://example.com/docs/page"]
        result = filter_urls(urls, "https://example.com/", language="en")
        assert "https://example.com/docs/page" in result

    def test_no_language_prefix_excluded_when_base_has_language_prefix(self):
        """URL without language prefix is excluded when base URL has a language prefix."""
        urls = ["https://example.com/docs/page"]
        # Base URL has /en/ prefix — non-prefixed URLs should be excluded
        result = filter_urls(urls, "https://example.com/en/", language="en")
        assert "https://example.com/docs/page" not in result

    def test_en_us_variant_included(self):
        """/en-us/ is treated as English."""
        urls = ["https://example.com/en-us/guide"]
        result = filter_urls(urls, "https://example.com/", language="en")
        assert "https://example.com/en-us/guide" in result

    def test_other_language_excluded(self):
        """French, German, Japanese URLs excluded when language='en'."""
        urls = [
            "https://example.com/fr/guide",
            "https://example.com/de/guide",
            "https://example.com/ja/guide",
            "https://example.com/en/guide",
        ]
        result = filter_urls(urls, "https://example.com/", language="en")
        assert len(result) == 1
        assert "https://example.com/en/guide" in result


class TestLanguageFilteringAll:
    """language='all' keeps every URL regardless of language."""

    def test_all_languages_kept(self):
        """All language variants are kept when language='all'."""
        urls = [
            "https://example.com/en/guide",
            "https://example.com/es/guia",
            "https://example.com/fr/guide",
            "https://example.com/zh/guide",
            "https://example.com/docs/page",
        ]
        result = filter_urls(urls, "https://example.com/", language="all")
        assert len(result) == 5

    def test_empty_list_with_all(self):
        """Empty input returns empty with language='all'."""
        result = filter_urls([], "https://example.com/", language="all")
        assert result == []


class TestMatchesLanguageDirectly:
    """Direct tests for _matches_language helper."""

    def test_en_path_matches_en(self):
        assert _matches_language("/en/guide", "en") is True

    def test_es_path_does_not_match_en(self):
        assert _matches_language("/es/guia", "en") is False

    def test_all_language_always_matches(self):
        assert _matches_language("/de/guide", "all") is True
        assert _matches_language("/anything", "all") is True

    def test_no_lang_prefix_no_base_url_included(self):
        """No language in path, no base_url → permissive include."""
        assert _matches_language("/docs/page", "en") is True

    def test_no_lang_prefix_base_with_lang_excluded(self):
        """No language in path, base has /en/ → excluded."""
        assert _matches_language("/docs/page", "en", "https://example.com/en/") is False

    def test_no_lang_prefix_base_without_lang_included(self):
        """No language in path, base has no language → included."""
        assert _matches_language("/docs/page", "en", "https://example.com/") is True


class TestSortedOutput:
    """Results must be returned in sorted order."""

    def test_results_are_sorted(self):
        """Output is alphabetically sorted."""
        urls = [
            "https://example.com/z-page",
            "https://example.com/a-page",
            "https://example.com/m-page",
        ]
        result = filter_urls(urls, "https://example.com/")
        assert result == sorted(result)

    def test_empty_returns_empty_sorted(self):
        """Empty input produces empty sorted output."""
        result = filter_urls([], "https://example.com/")
        assert result == []
