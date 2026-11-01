"""Unit tests for src/utils/safe_paths.py — data-root containment (CWE-22)."""

from pathlib import Path

import pytest

from src.utils.safe_paths import DATA_ROOT, data_root, resolve_under_root


class TestResolveUnderRoot:
    """resolve_under_root() must never return a path outside the root."""

    def test_relative_path_anchored_at_root(self, tmp_path):
        """A relative path is resolved against the root."""
        assert resolve_under_root("jobs/abc/.job_state.json", tmp_path) == (
            tmp_path / "jobs" / "abc" / ".job_state.json"
        )

    def test_absolute_path_inside_root_is_kept(self, tmp_path):
        """An absolute path inside the root is returned unchanged."""
        target = tmp_path / "output" / "docs"
        assert resolve_under_root(target, tmp_path) == target

    def test_root_itself_is_allowed(self, tmp_path):
        """The root itself is inside the root."""
        assert resolve_under_root(tmp_path, tmp_path) == tmp_path

    @pytest.mark.parametrize(
        "raw",
        [
            "../outside.json",
            "jobs/../../outside.json",
            "../../../../etc/passwd",
        ],
    )
    def test_traversal_rejected(self, tmp_path, raw):
        """Relative traversal that escapes the root raises ValueError."""
        with pytest.raises(ValueError, match="under the data root"):
            resolve_under_root(raw, tmp_path)

    def test_sibling_prefix_rejected(self, tmp_path):
        """A sibling sharing the root prefix (data-backup) is not inside it."""
        sibling = tmp_path.parent / (tmp_path.name + "-backup") / "state.json"
        with pytest.raises(ValueError, match="under the data root"):
            resolve_under_root(sibling, tmp_path)

    def test_absolute_outside_root_rejected(self, tmp_path):
        """An absolute path outside the root raises ValueError."""
        with pytest.raises(ValueError, match="under the data root"):
            resolve_under_root("/etc/passwd", tmp_path)

    def test_symlink_escape_rejected(self, tmp_path):
        """A symlink pointing outside the root must not be followed."""
        outside = tmp_path.parent / (tmp_path.name + "-outside")
        outside.mkdir()
        link = tmp_path / "escape"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported on this platform")

        with pytest.raises(ValueError, match="under the data root"):
            resolve_under_root("escape/state.json", tmp_path)

    def test_returns_path_instance(self, tmp_path):
        """The return value is a Path (callers pass it straight to file APIs)."""
        result = resolve_under_root("output", tmp_path)
        assert isinstance(result, Path)


class TestDataRoot:
    """The default root matches the container mount point."""

    def test_default_root_is_data(self):
        """Without an explicit root the container's /data is used."""
        assert Path(data_root()).name == DATA_ROOT.name
