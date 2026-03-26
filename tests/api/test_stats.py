"""Tests for GET /api/stats endpoint."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _mock_job(status: str):
    j = MagicMock()
    j.status = status
    return j


def test_stats_returns_correct_counts(client):
    mock_jobs = {
        "j1": _mock_job("completed"),
        "j2": _mock_job("completed"),
        "j3": _mock_job("failed"),
        "j4": _mock_job("running"),
        "j5": _mock_job("cancelled"),
        "j6": _mock_job("pending"),
        "j7": _mock_job("paused"),
    }
    with patch("src.api.routes.job_manager._jobs", mock_jobs):
        resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_jobs"] == 7
    assert data["completed_jobs"] == 2
    assert data["failed_jobs"] == 1
    assert data["active_jobs"] == 2  # running + pending
    assert data["cancelled_jobs"] == 1
    assert data["paused_jobs"] == 1


def test_stats_empty_when_no_jobs(client):
    with patch("src.api.routes.job_manager._jobs", {}):
        resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_jobs"] == 0
    assert data["active_jobs"] == 0
    assert data["completed_jobs"] == 0
    assert data["paused_jobs"] == 0
