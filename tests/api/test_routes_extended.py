"""Extended tests for src/api/routes.py.

Covers endpoints not yet tested:
- GET /api/providers
- GET /api/info
- POST /api/jobs/{id}/pause
- POST /api/jobs/{id}/resume
- POST /api/jobs/resume-from-state
- GET /api/jobs/{id}/events (404 branch)

All external I/O is mocked. No live browser, Ollama, or network calls.
"""

import os

# Disable Playwright page pool so lifespan doesn't require a browser binary.
os.environ.setdefault("PAGE_POOL_SIZE", "0")

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.models import JobRequest
from src.jobs.manager import Job
from src.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(**overrides) -> JobRequest:
    base = {
        "url": "https://example.com",
        "crawl_model": "mistral:7b",
        "pipeline_model": "qwen3:14b",
        "reasoning_model": "deepseek-r1:32b",
    }
    base.update(overrides)
    return JobRequest(**base)


def _make_job(
    job_id: str = "test-job-id",
    status: str = "pending",
    pages_completed: int = 0,
    pages_total: int = 0,
    current_url: str | None = None,
) -> Job:
    job = Job(
        id=job_id,
        request=_make_request(),
        status=status,
        pages_completed=pages_completed,
        pages_total=pages_total,
        current_url=current_url,
    )
    return job


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /api/providers
# ---------------------------------------------------------------------------


class TestListProviders:
    """GET /api/providers — list available providers."""

    def test_returns_200(self, client: TestClient):
        """GET /api/providers returns HTTP 200."""
        response = client.get("/api/providers")
        assert response.status_code == 200

    def test_response_has_providers_key(self, client: TestClient):
        """Response body contains a 'providers' key."""
        response = client.get("/api/providers")
        data = response.json()
        assert "providers" in data

    def test_providers_is_list(self, client: TestClient):
        """'providers' value is a list."""
        response = client.get("/api/providers")
        data = response.json()
        assert isinstance(data["providers"], list)

    def test_ollama_is_in_providers(self, client: TestClient):
        """'ollama' provider is always included."""
        response = client.get("/api/providers")
        provider_ids = [p["id"] for p in response.json()["providers"]]
        assert "ollama" in provider_ids

    def test_each_provider_has_required_fields(self, client: TestClient):
        """Each provider entry has id, name, configured, requires_api_key."""
        response = client.get("/api/providers")
        for provider in response.json()["providers"]:
            assert "id" in provider
            assert "name" in provider
            assert "configured" in provider
            assert "requires_api_key" in provider

    def test_ollama_is_configured_true(self, client: TestClient):
        """Ollama provider is always marked as configured."""
        response = client.get("/api/providers")
        ollama = next(p for p in response.json()["providers"] if p["id"] == "ollama")
        assert ollama["configured"] is True


# ---------------------------------------------------------------------------
# GET /api/info
# ---------------------------------------------------------------------------


class TestAppInfo:
    """GET /api/info — app metadata endpoint."""

    def test_returns_200(self, client: TestClient):
        """GET /api/info returns HTTP 200."""
        response = client.get("/api/info")
        assert response.status_code == 200

    def test_response_has_name_key(self, client: TestClient):
        """Response contains 'name' field."""
        response = client.get("/api/info")
        assert "name" in response.json()

    def test_name_is_docrawl(self, client: TestClient):
        """'name' is 'Docrawl'."""
        response = client.get("/api/info")
        assert response.json()["name"] == "Docrawl"

    def test_response_has_version_key(self, client: TestClient):
        """Response contains 'version' field."""
        response = client.get("/api/info")
        assert "version" in response.json()

    def test_response_has_repo_key(self, client: TestClient):
        """Response contains 'repo' field."""
        response = client.get("/api/info")
        assert "repo" in response.json()

    def test_response_has_models_used_key(self, client: TestClient):
        """Response contains 'models_used' field."""
        response = client.get("/api/info")
        assert "models_used" in response.json()

    def test_models_used_is_list(self, client: TestClient):
        """'models_used' is a list."""
        response = client.get("/api/info")
        assert isinstance(response.json()["models_used"], list)


# ---------------------------------------------------------------------------
# POST /api/jobs/{id}/pause
# ---------------------------------------------------------------------------


class TestPauseJob:
    """POST /api/jobs/{id}/pause — pause a running job."""

    def test_pause_running_job_returns_200(self, client: TestClient):
        """Pausing a running job returns HTTP 200."""
        fake_job = _make_job(job_id="pause-me", status="running")

        with patch("src.api.routes.job_manager.pause_job", return_value=fake_job):
            response = client.post("/api/jobs/pause-me/pause")

        assert response.status_code == 200

    def test_pause_job_returns_job_data(self, client: TestClient):
        """Pause response contains job id and status."""
        fake_job = _make_job(
            job_id="pause-job-1",
            status="paused",
            pages_completed=3,
            pages_total=10,
        )

        with patch("src.api.routes.job_manager.pause_job", return_value=fake_job):
            response = client.post("/api/jobs/pause-job-1/pause")

        data = response.json()
        assert data["id"] == "pause-job-1"
        assert data["status"] == "paused"
        assert data["pages_completed"] == 3
        assert data["pages_total"] == 10

    def test_pause_unknown_job_returns_404(self, client: TestClient):
        """Pausing a non-existent job returns HTTP 404."""
        with patch("src.api.routes.job_manager.pause_job", return_value=None):
            response = client.post("/api/jobs/ghost-job/pause")

        assert response.status_code == 404

    def test_pause_unknown_job_has_detail(self, client: TestClient):
        """404 response for unknown job includes 'detail'."""
        with patch("src.api.routes.job_manager.pause_job", return_value=None):
            response = client.post("/api/jobs/no-such-job/pause")

        assert "detail" in response.json()

    def test_pause_completed_job_returns_409(self, client: TestClient):
        """Pausing a completed job returns HTTP 409 conflict."""
        fake_job = _make_job(job_id="done-job", status="completed")

        with patch("src.api.routes.job_manager.pause_job", return_value=fake_job):
            response = client.post("/api/jobs/done-job/pause")

        assert response.status_code == 409

    def test_pause_failed_job_returns_409(self, client: TestClient):
        """Pausing a failed job returns HTTP 409 conflict."""
        fake_job = _make_job(job_id="failed-job", status="failed")

        with patch("src.api.routes.job_manager.pause_job", return_value=fake_job):
            response = client.post("/api/jobs/failed-job/pause")

        assert response.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/jobs/{id}/resume
# ---------------------------------------------------------------------------


class TestResumeJob:
    """POST /api/jobs/{id}/resume — resume a paused job."""

    def test_resume_paused_job_returns_200(self, client: TestClient):
        """Resuming a paused job returns HTTP 200."""
        fake_job = _make_job(job_id="resume-me", status="running")

        with patch("src.api.routes.job_manager.resume_job", return_value=fake_job):
            response = client.post("/api/jobs/resume-me/resume")

        assert response.status_code == 200

    def test_resume_job_returns_job_data(self, client: TestClient):
        """Resume response contains correct job id and status."""
        fake_job = _make_job(
            job_id="resume-job-1",
            status="running",
            pages_completed=5,
            pages_total=20,
        )

        with patch("src.api.routes.job_manager.resume_job", return_value=fake_job):
            response = client.post("/api/jobs/resume-job-1/resume")

        data = response.json()
        assert data["id"] == "resume-job-1"
        assert data["status"] == "running"

    def test_resume_unknown_job_returns_404(self, client: TestClient):
        """Resuming a non-existent job returns HTTP 404."""
        with patch("src.api.routes.job_manager.resume_job", return_value=None):
            response = client.post("/api/jobs/ghost-job/resume")

        assert response.status_code == 404

    def test_resume_completed_job_returns_409(self, client: TestClient):
        """Resuming a completed job returns HTTP 409 conflict."""
        fake_job = _make_job(job_id="done-job", status="completed")

        with patch("src.api.routes.job_manager.resume_job", return_value=fake_job):
            response = client.post("/api/jobs/done-job/resume")

        assert response.status_code == 409

    def test_resume_cancelled_job_returns_409(self, client: TestClient):
        """Resuming a cancelled job returns HTTP 409 conflict."""
        fake_job = _make_job(job_id="cancelled-job", status="cancelled")

        with patch("src.api.routes.job_manager.resume_job", return_value=fake_job):
            response = client.post("/api/jobs/cancelled-job/resume")

        assert response.status_code == 409


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}/events — 404 branch
# ---------------------------------------------------------------------------


class TestJobEvents:
    """GET /api/jobs/{id}/events — SSE stream."""

    def test_unknown_job_returns_404(self, client: TestClient):
        """Requesting event stream for unknown job returns HTTP 404."""
        with patch("src.api.routes.job_manager.get_job", return_value=None):
            response = client.get("/api/jobs/ghost-id/events")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/jobs/resume-from-state
# ---------------------------------------------------------------------------


class _FakePath:
    """A path stub that always reports as being under /data.

    Used to bypass the Pydantic ResumeFromStateRequest.validate_state_path
    validator on Windows where Path('/data').resolve() returns C:\\data\\...
    and the str().startswith('/data') check fails.
    """

    def __init__(self, s: str = "/data/test_state.json"):
        self._s = s

    def joinpath(self, *args) -> "_FakePath":
        return self

    def resolve(self) -> "_FakePath":
        return self

    def exists(self) -> bool:
        return False  # default; tests override via patch

    def __str__(self) -> str:
        return self._s

    def __truediv__(self, other) -> "_FakePath":
        return self

    @property
    def parent(self) -> "_FakePath":
        return self


class TestResumeFromState:
    """POST /api/jobs/resume-from-state — resume job from saved state file."""

    def _resume_body(self) -> dict:
        """Return a minimal valid body that passes the validator when Path is patched."""
        return {"state_file_path": "/data/test_state.json"}

    def _patch_models_path(self):
        """Return a context manager that makes the Pydantic validator pass.

        On Windows, Path('/data').resolve() returns C:\\data\\..., making
        str(resolved).startswith('/data') fail.  We replace src.api.models.Path
        with _FakePath so the validator produces a /data/... string and passes.
        """
        return patch("src.api.models.Path", _FakePath)

    def test_missing_state_file_returns_404(self, client: TestClient):
        """If the state file path does not exist on disk, returns 404."""
        body = self._resume_body()
        with (
            self._patch_models_path(),
            patch("src.api.routes.Path.exists", return_value=False),
        ):
            response = client.post("/api/jobs/resume-from-state", json=body)
        assert response.status_code == 404

    def test_invalid_state_file_returns_422(self, client: TestClient):
        """If the state file contains invalid JSON / bad structure, returns 422."""
        body = self._resume_body()
        with (
            self._patch_models_path(),
            patch("src.api.routes.Path.exists", return_value=True),
            patch(
                "src.jobs.state.load_job_state",
                side_effect=ValueError("bad state"),
            ),
        ):
            response = client.post("/api/jobs/resume-from-state", json=body)

        assert response.status_code == 422

    def test_empty_pending_urls_returns_409(self, client: TestClient):
        """State file with no pending URLs returns HTTP 409."""
        fake_state = MagicMock()
        fake_state.pending_urls = []
        fake_state.request = {
            "url": "https://example.com",
            "crawl_model": "m",
            "pipeline_model": "m",
            "reasoning_model": "m",
        }

        body = self._resume_body()
        with (
            self._patch_models_path(),
            patch("src.api.routes.Path.exists", return_value=True),
            patch("src.jobs.state.load_job_state", return_value=fake_state),
        ):
            response = client.post("/api/jobs/resume-from-state", json=body)

        assert response.status_code == 409

    def test_too_many_active_jobs_returns_429(self, client: TestClient):
        """When active job limit is reached, returns 429."""
        fake_state = MagicMock()
        fake_state.pending_urls = ["https://example.com/page1"]
        fake_state.request = {
            "url": "https://example.com",
            "crawl_model": "m",
            "pipeline_model": "m",
            "reasoning_model": "m",
        }

        body = self._resume_body()
        with (
            self._patch_models_path(),
            patch("src.api.routes.Path.exists", return_value=True),
            patch("src.jobs.state.load_job_state", return_value=fake_state),
            patch("src.api.routes.job_manager.active_job_count", return_value=999),
        ):
            response = client.post("/api/jobs/resume-from-state", json=body)

        assert response.status_code == 429

    def test_path_traversal_in_state_path_returns_422(self, client: TestClient):
        """State file path attempting directory traversal is rejected as 422.

        On Linux: the path resolves outside /data -> 422.
        On Windows: any absolute path like /data/... also fails -> 422.
        Either way the validator should reject it.
        """
        body = {"state_file_path": "../../etc/passwd"}
        response = client.post("/api/jobs/resume-from-state", json=body)
        assert response.status_code == 422

    def test_valid_state_creates_job(self, client: TestClient):
        """Valid state file with pending URLs triggers job creation and returns 200."""
        fake_state = MagicMock()
        fake_state.pending_urls = [
            "https://example.com/page1",
            "https://example.com/page2",
        ]
        fake_state.request = {
            "url": "https://example.com",
            "crawl_model": "m",
            "pipeline_model": "m",
            "reasoning_model": "m",
        }

        fake_job = _make_job(job_id="resume-new-id", status="pending")

        async def fake_create_resume_job(request, pending_urls):
            return fake_job

        body = self._resume_body()
        with (
            self._patch_models_path(),
            patch("src.api.routes.Path.exists", return_value=True),
            patch("src.jobs.state.load_job_state", return_value=fake_state),
            patch("src.api.routes.job_manager.active_job_count", return_value=0),
            patch(
                "src.api.routes.job_manager.create_resume_job",
                side_effect=fake_create_resume_job,
            ),
        ):
            response = client.post("/api/jobs/resume-from-state", json=body)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "resume-new-id"
        assert data["status"] == "pending"
        assert data["pages_total"] == 2


# ---------------------------------------------------------------------------
# GET /api/models?provider=... (provider-specific)
# ---------------------------------------------------------------------------


class TestListModelsWithProvider:
    """GET /api/models?provider=<name> — provider-specific model lists."""

    def test_models_with_ollama_provider_returns_200(self, client: TestClient):
        """GET /api/models?provider=ollama returns HTTP 200."""
        fake_models = [
            {"name": "mistral:7b", "size": None, "provider": "ollama", "is_free": True}
        ]

        async def fake_get(provider):
            return fake_models

        with patch("src.api.routes.get_available_models", side_effect=fake_get):
            response = client.get("/api/models?provider=ollama")

        assert response.status_code == 200

    def test_models_with_provider_returns_list(self, client: TestClient):
        """Response body is a list when provider parameter is given."""
        fake_models = [
            {"name": "m1", "size": None, "provider": "opencode", "is_free": True}
        ]

        async def fake_get(provider):
            return fake_models

        with patch("src.api.routes.get_available_models", side_effect=fake_get):
            response = client.get("/api/models?provider=opencode")

        assert isinstance(response.json(), list)

    def test_model_fields_are_correct(self, client: TestClient):
        """Response list items have name, size, provider, is_free fields."""
        fake_models = [
            {
                "name": "llama3:8b",
                "size": 5000,
                "provider": "ollama",
                "is_free": True,
            }
        ]

        async def fake_get(provider):
            return fake_models

        with patch("src.api.routes.get_available_models", side_effect=fake_get):
            response = client.get("/api/models")

        items = response.json()
        assert len(items) > 0
        item = items[0]
        assert "name" in item
        assert "provider" in item
        assert "is_free" in item
