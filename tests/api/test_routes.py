"""Tests for API routes in src/api/routes.py."""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from src.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    """Return a synchronous TestClient for the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


_JOB_BODY = {
    "url": "https://example.com",
    "crawl_model": "m",
    "pipeline_model": "m",
    "reasoning_model": "m",
}

# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthReady:
    """Smoke tests for GET /api/health/ready."""

    def test_health_ready_returns_200(self, client: TestClient):
        """GET /api/health/ready must return HTTP 200 regardless of Ollama state."""
        response = client.get("/api/health/ready")
        assert response.status_code == 200

    def test_health_ready_response_has_ready_key(self, client: TestClient):
        """Response body must contain a 'ready' boolean key."""
        response = client.get("/api/health/ready")
        data = response.json()
        assert "ready" in data


# ---------------------------------------------------------------------------
# Concurrent job limit (429)
# ---------------------------------------------------------------------------


class TestCreateJobConcurrencyLimit:
    """Tests for the MAX_CONCURRENT_JOBS guard in POST /api/jobs."""

    def test_returns_429_when_job_limit_reached(self, client: TestClient):
        """POST /api/jobs returns 429 when active_job_count >= MAX_CONCURRENT_JOBS."""
        with patch("src.api.routes.job_manager.active_job_count", return_value=999):
            response = client.post("/api/jobs", json=_JOB_BODY)
        assert response.status_code == 429

    def test_429_response_has_detail(self, client: TestClient):
        """429 response includes a descriptive 'detail' field."""
        with patch("src.api.routes.job_manager.active_job_count", return_value=999):
            response = client.post("/api/jobs", json=_JOB_BODY)
        data = response.json()
        assert "detail" in data

    def test_job_creation_proceeds_when_under_limit(self, client: TestClient):
        """POST /api/jobs proceeds past the concurrency check when under the limit."""
        mock_job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        # Mock create_job to avoid actually spawning asyncio tasks
        async def _fake_create_job(request):
            from src.jobs.manager import Job

            return Job(id=mock_job_id, request=request, status="pending")

        with (
            patch("src.api.routes.job_manager.active_job_count", return_value=0),
            patch(
                "src.api.routes.job_manager.create_job",
                side_effect=_fake_create_job,
            ),
        ):
            response = client.post("/api/jobs", json=_JOB_BODY)

        # 200 means we passed the 429 guard; the mock prevents real job execution
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_job_id
        assert data["status"] == "pending"
