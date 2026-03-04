"""Unit tests for the converter plugin registry (PR 3.4).

Source modules:
  src/scraper/converters/__init__.py
  src/scraper/converters/base.py
  src/scraper/converters/markdownify_converter.py
"""

import pytest

from src.scraper.converters import (
    available_converters,
    get_converter,
    register_converter,
)
from src.scraper.converters.markdownify_converter import MarkdownifyConverter


class TestGetConverter:
    """Tests for get_converter()."""

    def test_get_converter_none_returns_default_markdownify_converter(self):
        """get_converter(None) returns the default MarkdownifyConverter instance."""
        converter = get_converter(None)
        assert isinstance(converter, MarkdownifyConverter)

    def test_get_converter_by_explicit_name(self):
        """get_converter('markdownify') returns a MarkdownifyConverter instance."""
        converter = get_converter("markdownify")
        assert isinstance(converter, MarkdownifyConverter)

    def test_get_converter_unknown_raises_key_error(self):
        """get_converter() raises KeyError for an unregistered converter name."""
        with pytest.raises(KeyError, match="not found"):
            get_converter("unknown_converter_xyz")


class TestAvailableConverters:
    """Tests for available_converters()."""

    def test_returns_list_containing_markdownify(self):
        """available_converters() returns a list that includes 'markdownify'."""
        names = available_converters()
        assert isinstance(names, list)
        assert "markdownify" in names


class TestMarkdownifyConverter:
    """Tests for MarkdownifyConverter behaviour."""

    def test_convert_h1_produces_atx_heading(self):
        """convert('<h1>Hi</h1>') returns a string containing '# Hi'."""
        converter = MarkdownifyConverter()
        result = converter.convert("<h1>Hi</h1>")
        assert "# Hi" in result

    def test_supports_tables_returns_true(self):
        """MarkdownifyConverter.supports_tables() returns True."""
        assert MarkdownifyConverter().supports_tables() is True

    def test_supports_code_blocks_returns_true(self):
        """MarkdownifyConverter.supports_code_blocks() returns True."""
        assert MarkdownifyConverter().supports_code_blocks() is True

    def test_convert_returns_string(self):
        """convert() always returns a str regardless of input."""
        converter = MarkdownifyConverter()
        assert isinstance(converter.convert("<p>text</p>"), str)


class TestRegisterConverter:
    """Tests for register_converter()."""

    def test_register_valid_converter_makes_it_retrievable(self):
        """A registered converter can be retrieved by its name via get_converter()."""

        class MyConverter:
            def convert(self, html: str) -> str:
                return html

            def supports_tables(self) -> bool:
                return False

            def supports_code_blocks(self) -> bool:
                return False

        register_converter("myconv_test", MyConverter())
        result = get_converter("myconv_test")
        assert isinstance(result, MyConverter)

    def test_register_converter_raises_type_error_for_non_protocol_object(self):
        """register_converter() raises TypeError if the object does not satisfy
        the MarkdownConverter Protocol (missing convert/supports_tables/supports_code_blocks).
        """

        class NotAConverter:
            pass  # does not implement any protocol methods

        with pytest.raises(TypeError):
            register_converter("bad_converter", NotAConverter())  # type: ignore[arg-type]

    def test_registered_converter_appears_in_available_converters(self):
        """A newly registered converter's name is listed by available_converters()."""

        class AnotherConverter:
            def convert(self, html: str) -> str:
                return ""

            def supports_tables(self) -> bool:
                return False

            def supports_code_blocks(self) -> bool:
                return False

        name = "another_test_converter"
        register_converter(name, AnotherConverter())
        assert name in available_converters()
