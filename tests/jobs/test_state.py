"""Unit tests for job state persistence (PR 3.1) in src/jobs/state.py."""

import json
from pathlib import Path

import pytest

from src.jobs.state import STATE_FILENAME, JobState, load_job_state, save_job_state

_JOB_ID = "test-job-id-abc123"
_REQUEST_DICT = {
    "url": "https://docs.example.com",
    "crawl_model": "mistral:7b",
    "pipeline_model": "qwen3:14b",
    "reasoning_model": "deepseek-r1:32b",
}
_COMPLETED = ["https://docs.example.com/page1", "https://docs.example.com/page2"]
_FAILED = ["https://docs.example.com/broken"]
_PENDING = ["https://docs.example.com/page3", "https://docs.example.com/page4"]


class TestSaveJobState:
    """Tests for save_job_state()."""

    def test_writes_job_state_json_file(self, tmp_path: Path):
        """save_job_state() creates a .job_state.json file inside output_path."""
        save_job_state(tmp_path, _JOB_ID, _REQUEST_DICT, _COMPLETED, _FAILED, _PENDING)

        state_file = tmp_path / STATE_FILENAME
        assert state_file.exists()

    def test_written_file_contains_correct_fields(self, tmp_path: Path):
        """The state file has the expected top-level fields with correct values."""
        save_job_state(tmp_path, _JOB_ID, _REQUEST_DICT, _COMPLETED, _FAILED, _PENDING)

        data = json.loads((tmp_path / STATE_FILENAME).read_text(encoding="utf-8"))

        assert data["job_id"] == _JOB_ID
        assert data["request"] == _REQUEST_DICT
        assert data["completed_urls"] == _COMPLETED
        assert data["failed_urls"] == _FAILED
        assert data["pending_urls"] == _PENDING

    def test_returns_path_to_state_file(self, tmp_path: Path):
        """save_job_state() returns the Path of the written state file."""
        result = save_job_state(
            tmp_path, _JOB_ID, _REQUEST_DICT, _COMPLETED, _FAILED, _PENDING
        )

        assert isinstance(result, Path)
        assert result == tmp_path / STATE_FILENAME

    def test_atomic_write_tmp_file_is_gone_after_save(self, tmp_path: Path):
        """The intermediate .tmp file must not exist after save_job_state() completes."""
        save_job_state(tmp_path, _JOB_ID, _REQUEST_DICT, _COMPLETED, _FAILED, _PENDING)

        expected_tmp = (tmp_path / STATE_FILENAME).with_suffix(".tmp")
        assert not expected_tmp.exists()


class TestLoadJobState:
    """Tests for load_job_state()."""

    def test_round_trip_returns_same_data(self, tmp_path: Path):
        """save then load returns a JobState with all the original values."""
        state_path = save_job_state(
            tmp_path, _JOB_ID, _REQUEST_DICT, _COMPLETED, _FAILED, _PENDING
        )
        loaded = load_job_state(state_path)

        assert isinstance(loaded, JobState)
        assert loaded.job_id == _JOB_ID
        assert loaded.request == _REQUEST_DICT
        assert loaded.completed_urls == _COMPLETED
        assert loaded.failed_urls == _FAILED
        assert loaded.pending_urls == _PENDING

    def test_raises_value_error_on_corrupt_json(self, tmp_path: Path):
        """load_job_state() raises ValueError when the file contains invalid JSON."""
        bad_file = tmp_path / STATE_FILENAME
        bad_file.write_text("{ this is not valid json }", encoding="utf-8")

        with pytest.raises(ValueError, match="Failed to read state file"):
            load_job_state(bad_file)

    def test_raises_value_error_on_missing_required_fields(self, tmp_path: Path):
        """load_job_state() raises ValueError when the JSON is missing required fields."""
        incomplete = {"job_id": _JOB_ID}  # missing request, completed_urls, etc.
        bad_file = tmp_path / STATE_FILENAME
        bad_file.write_text(json.dumps(incomplete), encoding="utf-8")

        with pytest.raises(ValueError, match="missing fields"):
            load_job_state(bad_file)

    def test_raises_value_error_when_file_does_not_exist(self, tmp_path: Path):
        """load_job_state() raises ValueError when the state file is absent."""
        missing = tmp_path / STATE_FILENAME

        with pytest.raises(ValueError, match="Failed to read state file"):
            load_job_state(missing)

    def test_empty_url_lists_round_trip_correctly(self, tmp_path: Path):
        """Empty lists for completed/failed/pending are preserved after round-trip."""
        state_path = save_job_state(
            tmp_path, _JOB_ID, _REQUEST_DICT,
            completed_urls=[], failed_urls=[], pending_urls=[]
        )
        loaded = load_job_state(state_path)

        assert loaded.completed_urls == []
        assert loaded.failed_urls == []
        assert loaded.pending_urls == []
