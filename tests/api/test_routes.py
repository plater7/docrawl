"""
Integration tests for src/api/routes.py using FastAPI TestClient.

Tests cover:
- GET /api/health/ready → 200
- GET /api/models with mocked get_available_models → 200 + list
- POST /api/jobs with valid payload and mocked job_manager.create_job → 201
- POST /api/jobs with invalid URL → 422
- GET /api/jobs/{id}/status for existing job → 200
- GET /api/jobs/{id}/status for unknown job → 404
- POST /api/jobs/{id}/cancel for existing job → 200
- POST /api/jobs/{id}/cancel for unknown job → 404
"""

import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from src.main import app
from src.jobs.manager import Job
from src.api.models import JobRequest

# NOTE: The POST /api/jobs route does not set an explicit status_code,
# so FastAPI returns 200 (not 201) by default.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job(
    job_id: str = "test-job-id",
    status: str = "pending",
    pages_completed: int = 0,
    pages_total: int = 0,
    current_url: str | None = None,
) -> Job:
    """Build a fake Job instance for testing routes."""
    request = JobRequest(
        url="https://example.com",
        crawl_model="mistral:7b",
        pipeline_model="qwen3:14b",
        reasoning_model="deepseek-r1:32b",
    )
    job = Job(
        id=job_id,
        request=request,
        status=status,
        pages_completed=pages_completed,
        pages_total=pages_total,
        current_url=current_url,
    )
    return job


VALID_JOB_PAYLOAD = {
    "url": "https://example.com",
    "crawl_model": "mistral:7b",
    "pipeline_model": "qwen3:14b",
    "reasoning_model": "deepseek-r1:32b",
}


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthReady:
    """GET /api/health/ready"""

    def test_health_ready_returns_200(self):
        """Health check always returns HTTP 200."""
        # httpx is imported locally inside health_ready, so patch at the httpx module level
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}

        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=client_instance):
            with TestClient(app) as client:
                response = client.get("/api/health/ready")

        assert response.status_code == 200

    def test_health_ready_returns_json_with_ready_key(self):
        """Response body contains a 'ready' boolean key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}

        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=client_instance):
            with TestClient(app) as client:
                response = client.get("/api/health/ready")

        data = response.json()
        assert "ready" in data

    def test_health_ready_when_ollama_unreachable(self):
        """Health check returns 200 even when Ollama is unreachable."""
        client_instance = AsyncMock()
        client_instance.get.side_effect = httpx.ConnectError("refused")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=client_instance):
            with TestClient(app) as client:
                response = client.get("/api/health/ready")

        # Should still return 200 (not crash), just with ready=False
        assert response.status_code == 200
        assert response.json()["ready"] is False


# ---------------------------------------------------------------------------
# Models endpoint
# ---------------------------------------------------------------------------


class TestListModels:
    """GET /api/models"""

    def test_list_models_returns_200(self):
        """GET /api/models returns HTTP 200."""
        fake_models = [
            {"name": "mistral:7b", "size": None, "provider": "ollama", "is_free": True}
        ]

        async def fake_get_available_models(provider):
            return fake_models

        with patch(
            "src.api.routes.get_available_models", side_effect=fake_get_available_models
        ):
            with TestClient(app) as client:
                response = client.get("/api/models")

        assert response.status_code == 200

    def test_list_models_returns_list(self):
        """GET /api/models response body is a list."""
        fake_models = [
            {"name": "mistral:7b", "size": None, "provider": "ollama", "is_free": True},
            {"name": "llama3:8b", "size": None, "provider": "ollama", "is_free": True},
        ]

        async def fake_get_available_models(provider):
            return fake_models

        with patch(
            "src.api.routes.get_available_models", side_effect=fake_get_available_models
        ):
            with TestClient(app) as client:
                response = client.get("/api/models")

        data = response.json()
        assert isinstance(data, list)

    def test_list_models_empty_when_no_models(self):
        """GET /api/models returns empty list when no models available."""

        async def fake_get_available_models(provider):
            return []

        with patch(
            "src.api.routes.get_available_models", side_effect=fake_get_available_models
        ):
            with TestClient(app) as client:
                response = client.get("/api/models")

        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# Create job endpoint
# ---------------------------------------------------------------------------


class TestCreateJob:
    """POST /api/jobs"""

    def test_create_job_valid_payload_returns_200(self):
        """Valid job payload returns HTTP 200 (FastAPI default for POST returning a model)."""
        fake_job = _make_job(job_id="new-uuid-123", status="pending")

        async def fake_create_job(request):
            return fake_job

        with patch(
            "src.api.routes.job_manager.create_job", side_effect=fake_create_job
        ):
            with TestClient(app) as client:
                response = client.post("/api/jobs", json=VALID_JOB_PAYLOAD)

        assert response.status_code == 200

    def test_create_job_response_contains_job_id(self):
        """Job creation response contains the job's id."""
        fake_job = _make_job(job_id="abc-def-456", status="pending")

        async def fake_create_job(request):
            return fake_job

        with patch(
            "src.api.routes.job_manager.create_job", side_effect=fake_create_job
        ):
            with TestClient(app) as client:
                response = client.post("/api/jobs", json=VALID_JOB_PAYLOAD)

        data = response.json()
        assert data["id"] == "abc-def-456"
        assert data["status"] == "pending"

    def test_create_job_invalid_url_returns_422(self):
        """Invalid URL in job payload returns HTTP 422 (validation error)."""
        payload = {**VALID_JOB_PAYLOAD, "url": "not-a-valid-url"}
        with TestClient(app) as client:
            response = client.post("/api/jobs", json=payload)
        assert response.status_code == 422

    def test_create_job_missing_required_field_returns_422(self):
        """Missing required field returns HTTP 422."""
        payload = {
            "url": "https://example.com",
            # Missing crawl_model, pipeline_model, reasoning_model
        }
        with TestClient(app) as client:
            response = client.post("/api/jobs", json=payload)
        assert response.status_code == 422

    def test_create_job_empty_payload_returns_422(self):
        """Empty JSON payload returns HTTP 422."""
        with TestClient(app) as client:
            response = client.post("/api/jobs", json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Job status endpoint
# ---------------------------------------------------------------------------


class TestGetJobStatus:
    """GET /api/jobs/{id}/status"""

    def test_existing_job_returns_200(self):
        """Status for existing job returns HTTP 200."""
        fake_job = _make_job(job_id="existing-id", status="running")

        with patch("src.api.routes.job_manager.get_job", return_value=fake_job):
            with TestClient(app) as client:
                response = client.get("/api/jobs/existing-id/status")

        assert response.status_code == 200

    def test_existing_job_returns_correct_data(self):
        """Status response contains correct job fields."""
        fake_job = _make_job(
            job_id="job-123",
            status="running",
            pages_completed=10,
            pages_total=50,
            current_url="https://example.com/page10",
        )

        with patch("src.api.routes.job_manager.get_job", return_value=fake_job):
            with TestClient(app) as client:
                response = client.get("/api/jobs/job-123/status")

        data = response.json()
        assert data["id"] == "job-123"
        assert data["status"] == "running"
        assert data["pages_completed"] == 10
        assert data["pages_total"] == 50
        assert data["current_url"] == "https://example.com/page10"

    def test_unknown_job_returns_404(self):
        """Status for unknown job ID returns HTTP 404."""
        with patch("src.api.routes.job_manager.get_job", return_value=None):
            with TestClient(app) as client:
                response = client.get("/api/jobs/non-existent-id/status")

        assert response.status_code == 404

    def test_unknown_job_404_error_detail(self):
        """404 response for unknown job includes detail message."""
        with patch("src.api.routes.job_manager.get_job", return_value=None):
            with TestClient(app) as client:
                response = client.get("/api/jobs/ghost-id/status")

        assert "detail" in response.json()


# ---------------------------------------------------------------------------
# Cancel job endpoint
# ---------------------------------------------------------------------------


class TestCancelJob:
    """POST /api/jobs/{id}/cancel"""

    def test_cancel_existing_job_returns_200(self):
        """Cancelling an existing job returns HTTP 200."""
        fake_job = _make_job(job_id="cancel-me", status="cancelled")

        async def fake_cancel(job_id):
            return fake_job

        with patch("src.api.routes.job_manager.cancel_job", side_effect=fake_cancel):
            with TestClient(app) as client:
                response = client.post("/api/jobs/cancel-me/cancel")

        assert response.status_code == 200

    def test_cancel_existing_job_returns_correct_data(self):
        """Cancel response contains the updated job fields."""
        fake_job = _make_job(
            job_id="cancel-job-1",
            status="cancelled",
            pages_completed=7,
            pages_total=20,
        )

        async def fake_cancel(job_id):
            return fake_job

        with patch("src.api.routes.job_manager.cancel_job", side_effect=fake_cancel):
            with TestClient(app) as client:
                response = client.post("/api/jobs/cancel-job-1/cancel")

        data = response.json()
        assert data["id"] == "cancel-job-1"
        assert data["status"] == "cancelled"
        assert data["pages_completed"] == 7
        assert data["pages_total"] == 20

    def test_cancel_unknown_job_returns_404(self):
        """Cancelling a non-existent job returns HTTP 404."""

        async def fake_cancel(job_id):
            return None

        with patch("src.api.routes.job_manager.cancel_job", side_effect=fake_cancel):
            with TestClient(app) as client:
                response = client.post("/api/jobs/ghost-job/cancel")

        assert response.status_code == 404

    def test_cancel_unknown_job_404_error_detail(self):
        """404 response for unknown cancel includes detail message."""

        async def fake_cancel(job_id):
            return None

        with patch("src.api.routes.job_manager.cancel_job", side_effect=fake_cancel):
            with TestClient(app) as client:
                response = client.post("/api/jobs/no-such-job/cancel")

        assert "detail" in response.json()
