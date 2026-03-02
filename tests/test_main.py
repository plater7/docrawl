"""Tests for FastAPI lifespan in src/main.py (PR 1.2 — PagePool integration)."""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient


class TestLifespanPoolDisabled:
    """Lifespan with PAGE_POOL_SIZE=0 — no Playwright launched."""

    async def test_app_responds_with_pool_disabled(self, monkeypatch):
        """App starts and responds cleanly when pool is disabled."""
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")

        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health/ready")
            assert response.status_code in (200, 503)

    async def test_job_manager_has_no_pool_when_disabled(self, monkeypatch):
        """job_manager.page_pool stays None when PAGE_POOL_SIZE=0."""
        monkeypatch.setenv("PAGE_POOL_SIZE", "0")

        from src.api.routes import job_manager
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ):
            assert job_manager.page_pool is None


class TestLifespanPoolEnabled:
    """Lifespan with PAGE_POOL_SIZE>0 — Playwright mocked, tested via lifespan() directly."""

    def _make_mocks(self):
        mock_browser = AsyncMock()
        mock_browser.close = AsyncMock()

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright_instance.start = AsyncMock(
            return_value=mock_playwright_instance
        )
        mock_playwright_instance.stop = AsyncMock()

        mock_async_playwright = MagicMock(return_value=mock_playwright_instance)

        mock_pool = AsyncMock()
        mock_pool.initialize = AsyncMock()
        mock_pool.close = AsyncMock()

        return mock_pool, mock_browser, mock_playwright_instance, mock_async_playwright

    async def test_lifespan_initializes_pool(self, monkeypatch):
        """Pool is created, initialized, and assigned to job_manager on startup."""
        monkeypatch.setenv("PAGE_POOL_SIZE", "2")

        mock_pool, _, _, mock_async_playwright = self._make_mocks()

        from src.api.routes import job_manager
        from src.main import lifespan, app

        with (
            patch("playwright.async_api.async_playwright", mock_async_playwright),
            patch("src.main.PagePool", return_value=mock_pool),
        ):
            async with lifespan(app):
                assert job_manager.page_pool is mock_pool
                mock_pool.initialize.assert_awaited_once()

    async def test_lifespan_closes_pool_on_shutdown(self, monkeypatch):
        """Pool and browser are closed when lifespan exits."""
        monkeypatch.setenv("PAGE_POOL_SIZE", "2")

        mock_pool, mock_browser, mock_playwright_instance, mock_async_playwright = (
            self._make_mocks()
        )

        from src.main import lifespan, app

        with (
            patch("playwright.async_api.async_playwright", mock_async_playwright),
            patch("src.main.PagePool", return_value=mock_pool),
        ):
            async with lifespan(app):
                pass  # shutdown on exit

        mock_pool.close.assert_awaited_once()
        mock_browser.close.assert_awaited_once()
        mock_playwright_instance.stop.assert_awaited_once()
