"""Helpers that keep user-supplied paths inside the application data root.

CodeQL reported ``py/path-injection`` (CWE-22) twice because the previous
validation was not strong enough:

- ``str(Path("/data").joinpath(v.lstrip("/")).resolve()).startswith("/data")``
  compares an unresolved-prefix string: a sibling such as ``/data-backup``
  passes the check, and the raw value was never canonicalised;
- ``load_job_state()`` read whatever path it was handed, so any caller that
  skipped validation reopened the sink.

Every path that comes from a request now goes through :func:`resolve_under_root`,
which canonicalises with ``os.path.realpath`` (resolving ``..`` and symlinks)
and proves containment against the canonical root before the value is used.
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_ROOT = Path("/data")


def data_root() -> str:
    """Return the canonical data root used when no explicit root is given."""
    return os.path.realpath(str(DATA_ROOT))


def resolve_under_root(raw: str | Path, root: str | Path | None = None) -> Path:
    """Resolve *raw* and guarantee the result lives inside *root*.

    Relative paths are anchored at the root; absolute paths are used as given.
    ``ValueError`` is raised when the canonical result escapes the root, which
    covers ``..`` traversal, sibling-prefix names (``/data-backup``) and
    symlinks pointing outside the root.
    """
    base = os.path.realpath(str(root) if root is not None else data_root())
    raw_str = str(raw)
    if os.path.isabs(raw_str):
        candidate = os.path.realpath(raw_str)
    else:
        candidate = os.path.realpath(os.path.join(base, raw_str))

    # normcase keeps the comparison correct on case-insensitive filesystems.
    compare_candidate = os.path.normcase(candidate)
    compare_base = os.path.normcase(base)
    if compare_candidate != compare_base and not compare_candidate.startswith(
        compare_base + os.sep
    ):
        raise ValueError("path must be under the data root")
    return Path(candidate)
