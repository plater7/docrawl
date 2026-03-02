"""Unit tests for fetch_html_fast() (PR 1.3) in src/scraper/page.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.scraper.page import fetch_html_fast

# A real HTML string that markdownify will convert to ≥500 chars of markdown.
# Each paragraph sentence is distinct text that survives markdownify stripping,
# producing enough output to meet the 500-char quality threshold.
_LONG_HTML = (
    "<html><body>"
    + "".join(
        f"<p>This is paragraph number {i} with sufficient text to produce "
        f"meaningful markdown output and count toward the length threshold.</p>"
        for i in range(10)
    )
    + "</body></html>"
)
# A short HTML string whose markdown conversion will be <500 chars.
_SHORT_HTML = "<html><body><p>hi</p></body></html>"


def _make_response(
    status_code: int = 200,
    text: str = _LONG_HTML,
    content_type: str = "text/html; charset=utf-8",
) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.headers = {"content-type": content_type}
    return resp


class TestFetchHtmlFast:
    """Tests for fetch_html_fast() fast HTTP path."""

    async def test_returns_markdown_for_long_html_response(self):
        """Returns a non-empty markdown string when httpx returns ≥500 char HTML."""
        with patch("src.scraper.page.validate_url_not_ssrf"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__ = AsyncMock(
                    return_value=mock_client
                )
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=_make_response())

                result = await fetch_html_fast("https://docs.example.com/page")

        assert result is not None
        assert isinstance(result, str)
        assert len(result) >= 500

    async def test_returns_none_when_markdown_below_quality_threshold(self):
        """Returns None when the converted markdown is shorter than 500 chars."""
        with patch("src.scraper.page.validate_url_not_ssrf"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__ = AsyncMock(
                    return_value=mock_client
                )
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(
                    return_value=_make_response(text=_SHORT_HTML)
                )

                result = await fetch_html_fast("https://docs.example.com/short")

        assert result is None

    async def test_returns_none_on_httpx_request_error(self):
        """Returns None when httpx raises a RequestError (network failure)."""
        with patch("src.scraper.page.validate_url_not_ssrf"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__ = AsyncMock(
                    return_value=mock_client
                )
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(
                    side_effect=httpx.RequestError("connection refused")
                )

                result = await fetch_html_fast("https://docs.example.com/page")

        assert result is None

    async def test_returns_none_on_non_200_status_code(self):
        """Returns None when the server responds with a non-200 status code."""
        for status in (301, 403, 404, 500, 503):
            with patch("src.scraper.page.validate_url_not_ssrf"):
                with patch("httpx.AsyncClient") as mock_client_cls:
                    mock_client = AsyncMock()
                    mock_client_cls.return_value.__aenter__ = AsyncMock(
                        return_value=mock_client
                    )
                    mock_client_cls.return_value.__aexit__ = AsyncMock(
                        return_value=False
                    )
                    mock_client.get = AsyncMock(
                        return_value=_make_response(status_code=status, text=_LONG_HTML)
                    )

                    result = await fetch_html_fast(
                        f"https://docs.example.com/status-{status}"
                    )

            assert result is None, f"Expected None for HTTP {status}"

    async def test_returns_none_when_content_type_is_not_html(self):
        """Returns None when Content-Type does not contain 'text/html'."""
        with patch("src.scraper.page.validate_url_not_ssrf"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__ = AsyncMock(
                    return_value=mock_client
                )
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(
                    return_value=_make_response(
                        content_type="application/json", text=_LONG_HTML
                    )
                )

                result = await fetch_html_fast("https://docs.example.com/api.json")

        assert result is None
