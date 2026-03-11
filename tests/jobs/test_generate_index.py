"""Unit tests for _generate_index (src/jobs/runner.py) — fix issue #70."""

from pathlib import Path

import pytest

from src.jobs.runner import _generate_index


class TestGenerateIndex:
    """Tests for the _generate_index helper function."""

    def test_links_use_slash_separator(self, tmp_path: Path) -> None:
        """Links in _index.md must use '/' not '_' as path separator.

        Regression test for issue #70: URL https://docs.example.com/guide/install
        must produce a link like [install](guide/install.md), not
        [install](guide_install.md).
        """
        urls = ["https://docs.example.com/guide/install"]
        _generate_index(urls, tmp_path)

        content = (tmp_path / "_index.md").read_text(encoding="utf-8")
        assert "[install](guide/install.md)" in content
        assert "guide_install" not in content

    def test_deeply_nested_path_uses_slashes(self, tmp_path: Path) -> None:
        """Deeply nested paths must preserve all slash separators."""
        urls = ["https://docs.example.com/api/v2/reference/endpoints"]
        _generate_index(urls, tmp_path)

        content = (tmp_path / "_index.md").read_text(encoding="utf-8")
        assert "[endpoints](api/v2/reference/endpoints.md)" in content

    def test_root_url_produces_index_link(self, tmp_path: Path) -> None:
        """A root-only URL (no path) must produce 'index' as the rel_path."""
        urls = ["https://docs.example.com/"]
        _generate_index(urls, tmp_path)

        content = (tmp_path / "_index.md").read_text(encoding="utf-8")
        assert "[Home](index.md)" in content

    def test_multiple_urls_each_produce_correct_link(self, tmp_path: Path) -> None:
        """All URLs in a mixed list must produce correct slash-separated links."""
        urls = [
            "https://docs.example.com/guide/install",
            "https://docs.example.com/api/reference",
            "https://docs.example.com/",
        ]
        _generate_index(urls, tmp_path)

        content = (tmp_path / "_index.md").read_text(encoding="utf-8")
        assert "[install](guide/install.md)" in content
        assert "[reference](api/reference.md)" in content
        assert "[Home](index.md)" in content

    def test_index_file_written_to_output_path(self, tmp_path: Path) -> None:
        """_index.md must be written at the root of output_path."""
        _generate_index(["https://docs.example.com/page"], tmp_path)

        index_path = tmp_path / "_index.md"
        assert index_path.exists()

    def test_index_file_has_header(self, tmp_path: Path) -> None:
        """Generated _index.md must start with the Documentation Index header."""
        _generate_index(["https://docs.example.com/page"], tmp_path)

        content = (tmp_path / "_index.md").read_text(encoding="utf-8")
        assert content.startswith("# Documentation Index")

    def test_empty_url_list_produces_header_only(self, tmp_path: Path) -> None:
        """An empty URL list must still produce a valid _index.md with the header."""
        _generate_index([], tmp_path)

        content = (tmp_path / "_index.md").read_text(encoding="utf-8")
        assert "# Documentation Index" in content

    @pytest.mark.parametrize(
        ("url", "expected_link"),
        [
            (
                "https://docs.example.com/guide/install",
                "[install](guide/install.md)",
            ),
            (
                "https://docs.example.com/concepts/architecture/overview",
                "[overview](concepts/architecture/overview.md)",
            ),
            (
                "https://docs.example.com/quickstart",
                "[quickstart](quickstart.md)",
            ),
        ],
    )
    def test_parametrized_url_to_link(
        self, tmp_path: Path, url: str, expected_link: str
    ) -> None:
        """Parametrized coverage of URL -> markdown link conversion."""
        _generate_index([url], tmp_path)
        content = (tmp_path / "_index.md").read_text(encoding="utf-8")
        assert expected_link in content
