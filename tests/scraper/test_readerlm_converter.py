"""Tests for ReaderLMConverter (PR feat/readerlm-converter)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scraper.converters.readerlm_converter import ReaderLMConverter


# ---------------------------------------------------------------------------
# Protocol surface
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_supports_tables(self):
        assert ReaderLMConverter().supports_tables() is True

    def test_supports_code_blocks(self):
        assert ReaderLMConverter().supports_code_blocks() is True


# ---------------------------------------------------------------------------
# convert() — happy path
# ---------------------------------------------------------------------------


class TestConvertHappyPath:
    def _make_fake_response(self, content: str):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"message": {"content": content}}
        return resp

    def test_returns_markdown_string(self):
        expected = "# Hello\n\nWorld"
        fake_resp = self._make_fake_response(expected)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=fake_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = ReaderLMConverter().convert("<h1>Hello</h1><p>World</p>")

        assert result == expected

    def test_payload_contains_correct_model(self):
        fake_resp = self._make_fake_response("# ok")
        captured: list[dict] = []

        async def fake_post(url, **kwargs):
            captured.append(kwargs.get("json", {}))
            return fake_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = fake_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ReaderLMConverter(model="milkey/reader-lm-v2:latest").convert("<p>x</p>")

        assert captured[0]["model"] == "milkey/reader-lm-v2:latest"

    def test_num_ctx_capped_at_131072(self):
        """Very long HTML should not request more than 131 072 tokens."""
        fake_resp = self._make_fake_response("done")
        captured: list[dict] = []

        async def fake_post(url, **kwargs):
            captured.append(kwargs.get("json", {}))
            return fake_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = fake_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            big_html = "<p>" + "x" * 500_000 + "</p>"
            ReaderLMConverter().convert(big_html)

        assert captured[0]["options"]["num_ctx"] <= 131_072


# ---------------------------------------------------------------------------
# convert() — error handling
# ---------------------------------------------------------------------------


class TestConvertErrors:
    def test_http_error_propagates(self):
        import httpx as _httpx

        async def fake_post(url, **kwargs):
            raise _httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock(status_code=500)
            )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = fake_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(_httpx.HTTPStatusError):
                ReaderLMConverter().convert("<p>test</p>")


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_get_converter_readerlm(self):
        from src.scraper.converters import get_converter

        assert isinstance(get_converter("readerlm"), ReaderLMConverter)

    def test_get_converter_readerlm_v1_uses_v1_model(self):
        from src.scraper.converters import get_converter

        c = get_converter("readerlm-v1")
        assert isinstance(c, ReaderLMConverter)
        assert "reader-lm:" in c.model  # v1 model tag

    def test_available_converters_includes_both(self):
        from src.scraper.converters import available_converters

        names = available_converters()
        assert "readerlm" in names
        assert "readerlm-v1" in names

    def test_unknown_converter_raises(self):
        from src.scraper.converters import get_converter

        with pytest.raises(ValueError, match="Unknown converter"):
            get_converter("nonexistent-xyz")
