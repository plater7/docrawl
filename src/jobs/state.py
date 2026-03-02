"""Job state persistence for pause/resume (PR 3.1).

State file: {output_path}/.job_state.json
Contains: serialized JobRequest + URL lists (completed, failed, pending)

Design decisions:
- Atomic write (.tmp → os.replace) for crash safety
- resume-from-state creates a new job with only pending URLs
- Sites may change between pause and resume (404s go to failed)
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STATE_FILENAME = ".job_state.json"


@dataclass
class JobState:
    """Serializable snapshot of a paused job's progress."""

    job_id: str
    request: dict  # serialized JobRequest
    completed_urls: list[str]
    failed_urls: list[str]
    pending_urls: list[str]


def save_job_state(
    output_path: Path,
    job_id: str,
    request_dict: dict[str, Any],
    completed_urls: list[str],
    failed_urls: list[str],
    pending_urls: list[str],
) -> Path:
    """Atomically write job state to {output_path}/.job_state.json.

    Returns the path to the written state file.
    Raises on write error.
    """
    state = {
        "job_id": job_id,
        "request": request_dict,
        "completed_urls": completed_urls,
        "failed_urls": failed_urls,
        "pending_urls": pending_urls,
    }
    state_path = output_path / STATE_FILENAME
    tmp_path = state_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp_path, state_path)
    logger.info(
        f"Job state saved: {len(completed_urls)} done, {len(failed_urls)} failed, {len(pending_urls)} pending"
    )
    return state_path


def load_job_state(state_path: Path) -> JobState:
    """Load job state from a .job_state.json file.

    Raises ValueError if the file is corrupt or missing required fields.
    """
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to read state file {state_path}: {e}") from e

    required = {"job_id", "request", "completed_urls", "failed_urls", "pending_urls"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"State file missing fields: {missing}")

    return JobState(
        job_id=data["job_id"],
        request=data["request"],
        completed_urls=data["completed_urls"],
        failed_urls=data["failed_urls"],
        pending_urls=data["pending_urls"],
    )
