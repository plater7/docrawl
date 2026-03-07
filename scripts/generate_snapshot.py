#!/usr/bin/env python3
"""Generate SNAPSHOT.md from the current codebase.

Walks src/ dynamically — no hardcoded paths. Run before AI-assisted
development sessions or let the GitHub Action call it on push to main.

Usage:
    python scripts/generate_snapshot.py              # writes SNAPSHOT.md
    python scripts/generate_snapshot.py -o /dev/stdout  # preview to terminal
    python scripts/generate_snapshot.py --check      # exit 1 if snapshot is stale
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent  # repo root
SRC_DIR = ROOT / "src"
OUTPUT_DEFAULT = ROOT / "SNAPSHOT.md"

# Files outside src/ to include (relative to repo root).
# Add entries here if you want requirements.txt, Dockerfile, etc.
EXTRA_FILES: list[str] = [
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "pyproject.toml",
]

# Patterns to always skip
SKIP_PATTERNS: list[str] = [
    "__pycache__",
    ".pyc",
    "node_modules",
    ".egg-info",
]

# Max lines per file before truncation warning
MAX_LINES = 500


# ── Helpers ──────────────────────────────────────────────────────────────────


def _should_skip(path: Path) -> bool:
    """Return True if the file should be excluded."""
    parts = str(path)
    return any(pat in parts for pat in SKIP_PATTERNS)


def _detect_version() -> str:
    """Try to read API_VERSION from src/main.py."""
    main_py = SRC_DIR / "main.py"
    if main_py.exists():
        text = main_py.read_text(encoding="utf-8")
        match = re.search(r'API_VERSION\s*=\s*["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)
    return "unknown"


def _build_tree(base: Path, prefix: str = "") -> list[str]:
    """Build an ASCII directory tree (2 levels deep)."""
    lines: list[str] = []
    if not base.is_dir():
        return lines

    entries = sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name))
    dirs = [e for e in entries if e.is_dir() and not _should_skip(e)]
    files = [e for e in entries if e.is_file() and not _should_skip(e)]

    items = dirs + files
    for i, item in enumerate(items):
        connector = "└── " if i == len(items) - 1 else "├── "
        lines.append(f"{prefix}{connector}{item.name}")

        if item.is_dir():
            ext = "    " if i == len(items) - 1 else "│   "
            # One level deeper
            sub_entries = sorted(item.iterdir(), key=lambda p: (p.is_file(), p.name))
            sub_items = [e for e in sub_entries if not _should_skip(e)]
            for j, sub in enumerate(sub_items):
                sub_conn = "└── " if j == len(sub_items) - 1 else "├── "
                suffix = "/" if sub.is_dir() else ""
                lines.append(f"{prefix}{ext}{sub_conn}{sub.name}{suffix}")

    return lines


def _lang_for_ext(ext: str) -> str:
    """Map file extension to markdown code fence language."""
    mapping = {
        ".py": "python",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".toml": "toml",
        ".txt": "",
        ".cfg": "ini",
        ".sh": "bash",
        ".js": "javascript",
        ".ts": "typescript",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".md": "markdown",
    }
    return mapping.get(ext, "")


# ── Generator ────────────────────────────────────────────────────────────────


def generate_snapshot() -> str:
    """Return the full SNAPSHOT.md content as a string."""
    version = _detect_version()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    parts: list[str] = []

    # Header
    parts.append(f"# DocRawl Code Snapshot — v{version}\n")
    parts.append(f"> Auto-generated on {now} by `scripts/generate_snapshot.py`.")
    parts.append("> Use as reference for AI-assisted development sessions.\n")

    # Project structure
    parts.append("## Project Structure\n")
    parts.append("```")
    parts.append("src/")
    tree = _build_tree(SRC_DIR)
    parts.extend(tree)
    parts.append("```\n")

    # Collect Python files in src/ (sorted for stable output)
    py_files = sorted(SRC_DIR.rglob("*.py"))
    py_files = [f for f in py_files if not _should_skip(f)]

    # Also include non-py files in src/ that matter (html, css, js)
    other_src = sorted(
        f
        for f in SRC_DIR.rglob("*")
        if f.is_file()
        and f.suffix in {".html", ".js", ".css", ".json"}
        and not _should_skip(f)
    )

    all_src_files = py_files + other_src

    # Render each source file
    for filepath in all_src_files:
        rel = filepath.relative_to(ROOT)
        lang = _lang_for_ext(filepath.suffix)

        parts.append("---\n")
        parts.append(f"## `{rel}`\n")

        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception as e:
            parts.append(f"*Could not read file: {e}*\n")
            continue

        lines = content.splitlines()
        if len(lines) > MAX_LINES:
            parts.append(
                f"*File truncated: showing first {MAX_LINES} of {len(lines)} lines.*\n"
            )
            content = "\n".join(lines[:MAX_LINES]) + "\n# ... truncated ..."

        parts.append(f"```{lang}")
        parts.append(content.rstrip())
        parts.append("```\n")

    # Extra files (requirements.txt, Dockerfile, etc.)
    for extra in EXTRA_FILES:
        filepath = ROOT / extra
        if not filepath.exists():
            continue

        lang = _lang_for_ext(filepath.suffix)
        parts.append("---\n")
        parts.append(f"## `{extra}`\n")

        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception as e:
            parts.append(f"*Could not read file: {e}*\n")
            continue

        parts.append(f"```{lang}")
        parts.append(content.rstrip())
        parts.append("```\n")

    return "\n".join(parts) + "\n"


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate SNAPSHOT.md from the current codebase."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=str(OUTPUT_DEFAULT),
        help=f"Output path (default: {OUTPUT_DEFAULT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if snapshot is up-to-date (exit 1 if stale).",
    )
    args = parser.parse_args()

    snapshot = generate_snapshot()

    if args.check:
        output_path = Path(args.output)
        if not output_path.exists():
            print("SNAPSHOT.md does not exist — stale.", file=sys.stderr)
            sys.exit(1)

        existing = output_path.read_text(encoding="utf-8")
        # Compare ignoring the timestamp line
        def _strip_timestamp(text: str) -> str:
            return re.sub(r"> Auto-generated on .+ by", "> Auto-generated on <TS> by", text)

        if hashlib.sha256(_strip_timestamp(existing).encode()).hexdigest() != \
           hashlib.sha256(_strip_timestamp(snapshot).encode()).hexdigest():
            print("SNAPSHOT.md is stale — regenerate with: python scripts/generate_snapshot.py", file=sys.stderr)
            sys.exit(1)

        print("SNAPSHOT.md is up-to-date.")
        sys.exit(0)

    # Write
    if args.output == "/dev/stdout":
        sys.stdout.write(snapshot)
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(snapshot, encoding="utf-8")
        print(f"Generated {output_path} ({len(snapshot)} chars)")


if __name__ == "__main__":
    main()
