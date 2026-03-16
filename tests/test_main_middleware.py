"""Tests for middleware, exception handlers, and serve_ui in src/main.py."""

import json
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware
# ---------------------------------------------------------------------------


class TestSecurityHeadersMiddleware:
    """SecurityHeadersMiddleware injects security headers on every response."""

    async def test_x_content_type_options_header(self, monkeypatch):
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health/ready")

        assert response.headers.get("x-content-type-options") == "nosniff"

    async def test_x_frame_options_header(self, monkeypatch):
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health/ready")

        assert response.headers.get("x-frame-options") == "DENY"

    async def test_referrer_policy_header(self, monkeypatch):
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health/ready")

        assert (
            response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        )

    async def test_content_security_policy_header(self, monkeypatch):
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health/ready")

        csp = response.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp

    async def test_x_api_version_header(self, monkeypatch):
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        from src.main import app, API_VERSION

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health/ready")

        assert response.headers.get("x-api-version") == API_VERSION

    async def test_security_headers_on_404_route(self, monkeypatch):
        """Security headers are present even on 404 responses."""
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/jobs/nonexistent-id/status")

        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"


# ---------------------------------------------------------------------------
# ApiKeyMiddleware
# ---------------------------------------------------------------------------


class TestApiKeyMiddleware:
    """ApiKeyMiddleware enforces X-Api-Key when API_KEY env var is set."""

    async def test_missing_key_returns_401(self, monkeypatch):
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        import src.main as main_module

        monkeypatch.setattr(main_module, "_API_KEY", "secret-key")

        async with AsyncClient(
            transport=ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            response = await client.get("/api/jobs/some-id/status")

        assert response.status_code == 401

    async def test_wrong_key_returns_401(self, monkeypatch):
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        import src.main as main_module

        monkeypatch.setattr(main_module, "_API_KEY", "secret-key")

        async with AsyncClient(
            transport=ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/jobs/some-id/status", headers={"X-Api-Key": "wrong-key"}
            )

        assert response.status_code == 401

    async def test_correct_key_passes_through(self, monkeypatch):
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        import src.main as main_module

        monkeypatch.setattr(main_module, "_API_KEY", "secret-key")

        async with AsyncClient(
            transport=ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/health/ready", headers={"X-Api-Key": "secret-key"}
            )

        assert response.status_code != 401

    async def test_root_path_exempt(self, monkeypatch):
        """GET / is exempt from API key enforcement."""
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        import src.main as main_module

        monkeypatch.setattr(main_module, "_API_KEY", "secret-key")

        async with AsyncClient(
            transport=ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            response = await client.get("/")

        assert response.status_code != 401

    async def test_health_ready_exempt(self, monkeypatch):
        """/api/health/ready is exempt from API key enforcement."""
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        import src.main as main_module

        monkeypatch.setattr(main_module, "_API_KEY", "secret-key")

        async with AsyncClient(
            transport=ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health/ready")

        assert response.status_code != 401

    async def test_empty_api_key_allows_all_requests(self, monkeypatch):
        """When _API_KEY is empty all requests pass through regardless of headers."""
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        import src.main as main_module

        monkeypatch.setattr(main_module, "_API_KEY", "")

        async with AsyncClient(
            transport=ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            response = await client.get("/api/jobs/some-id/status")

        assert response.status_code != 401

    async def test_401_response_body_has_detail(self, monkeypatch):
        """401 response body contains a 'detail' field."""
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        import src.main as main_module

        monkeypatch.setattr(main_module, "_API_KEY", "secret-key")

        async with AsyncClient(
            transport=ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            response = await client.get("/api/jobs/some-id/status")

        assert response.status_code == 401
        assert "detail" in response.json()


# ---------------------------------------------------------------------------
# rate_limit_handler
# ---------------------------------------------------------------------------


class TestRateLimitHandler:
    """rate_limit_handler returns 429 with detail key for RateLimitExceeded."""

    async def test_rate_limit_handler_returns_429(self):
        from src.main import rate_limit_handler

        exc = MagicMock()
        exc.detail = "1 per 1 second"
        mock_request = MagicMock(spec=Request)

        response = await rate_limit_handler(mock_request, exc)

        assert response.status_code == 429

    async def test_rate_limit_handler_body_has_detail(self):
        from src.main import rate_limit_handler

        exc = MagicMock()
        exc.detail = "5 per minute"
        mock_request = MagicMock(spec=Request)

        response = await rate_limit_handler(mock_request, exc)

        body = json.loads(response.body)
        assert "detail" in body

    async def test_rate_limit_handler_detail_reflects_exception(self):
        """The detail field in the response reflects the exception's detail."""
        from src.main import rate_limit_handler

        exc = MagicMock()
        exc.detail = "10 per hour"
        mock_request = MagicMock(spec=Request)

        response = await rate_limit_handler(mock_request, exc)

        body = json.loads(response.body)
        assert str(exc.detail) in body["detail"]


# ---------------------------------------------------------------------------
# _global_exception_handler
# ---------------------------------------------------------------------------


class TestGlobalExceptionHandler:
    """_global_exception_handler returns 500 with sanitized error body."""

    async def test_returns_500(self):
        from src.main import _global_exception_handler

        exc = RuntimeError("Something went wrong internally")
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        response = await _global_exception_handler(mock_request, exc)

        assert response.status_code == 500

    async def test_body_has_error_key(self):
        from src.main import _global_exception_handler

        exc = ValueError("Internal detail")
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        response = await _global_exception_handler(mock_request, exc)

        body = json.loads(response.body)
        assert "error" in body

    async def test_body_is_sanitized(self):
        """Internal exception message must not appear in the response body."""
        from src.main import _global_exception_handler

        secret_detail = "db-password=supersecret"
        exc = RuntimeError(secret_detail)
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        response = await _global_exception_handler(mock_request, exc)

        body = json.loads(response.body)
        assert secret_detail not in body.get("error", "")
        assert body["error"] == "Internal server error"



# ---------------------------------------------------------------------------
# serve_ui
# ---------------------------------------------------------------------------


class TestServeUi:
    """GET / returns the UI index.html via FileResponse."""

    async def test_returns_200(self, monkeypatch):
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/")

        assert response.status_code == 200

    async def test_content_type_is_html(self, monkeypatch):
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/")

        assert "text/html" in response.headers.get("content-type", "")

    async def test_response_has_security_headers(self, monkeypatch):
        """Security headers are present even on the root UI response."""
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/")

        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
