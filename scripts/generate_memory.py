#!/usr/bin/env python3
"""Generate docs/Memory.md from the current codebase.

Extracts metadata (version, modules, dependencies, workflows, ADRs) and
combines it with static narrative sections to produce a Claude Code-compatible
memory file. Dynamic sections update automatically; static sections require
manual edits to this script when architecture changes significantly.

Usage:
    python scripts/generate_memory.py                # writes docs/Memory.md
    python scripts/generate_memory.py -o /dev/stdout  # preview to terminal
    python scripts/generate_memory.py --check        # exit 1 if Memory.md is stale
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# -- Configuration ----------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
OUTPUT_DEFAULT = ROOT / "docs" / "Memory.md"


# -- Helpers ----------------------------------------------------------------


def _detect_version() -> str:
    """Read API_VERSION from src/main.py."""
    main_py = SRC_DIR / "main.py"
    if main_py.exists():
        text = main_py.read_text(encoding="utf-8")
        match = re.search(r'API_VERSION\s*=\s*["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)
    return "unknown"


def _extract_module_map() -> str:
    """Scan src/ and build module structure with docstrings."""
    if not SRC_DIR.is_dir():
        return "(src/ directory not found)"

    lines = []
    # Get top-level files first
    top_files = sorted(f for f in SRC_DIR.iterdir() if f.is_file() and f.suffix == ".py")
    for f in top_files:
        doc = _get_module_docstring(f)
        desc = f" - {doc}" if doc else ""
        lines.append(f"src/{f.name}{desc}")

    # Then subdirectories
    subdirs = sorted(d for d in SRC_DIR.iterdir() if d.is_dir() and d.name != "__pycache__")
    for subdir in subdirs:
        py_files = sorted(subdir.glob("*.py"))
        if not py_files:
            continue
        file_names = []
        for f in py_files:
            if f.name == "__init__.py":
                continue
            doc = _get_module_docstring(f)
            desc = f" ({doc})" if doc else ""
            file_names.append(f"{f.name}{desc}")
        # Check for sub-subdirectories (e.g., src/scraper/converters/)
        sub_subdirs = sorted(d for d in subdir.iterdir() if d.is_dir() and d.name != "__pycache__")
        for ssd in sub_subdirs:
            ssd_files = sorted(ssd.glob("*.py"))
            ssd_names = [f.name for f in ssd_files if f.name != "__init__.py"]
            if ssd_names:
                file_names.append(f"{ssd.name}/" + ", ".join(ssd_names))
        if file_names:
            lines.append(f"src/{subdir.name}/: " + ", ".join(file_names))

    return "\n".join(lines)


def _get_module_docstring(path: Path) -> str | None:
    """Extract the module-level docstring from a Python file."""
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        doc = ast.get_docstring(tree)
        if doc:
            # Return first line only, strip trailing period
            first_line = doc.strip().split("\n")[0].rstrip(".")
            return first_line if len(first_line) < 100 else first_line[:97] + "..."
        return None
    except (SyntaxError, UnicodeDecodeError):
        return None


def _read_dependencies() -> str:
    """Read requirements.txt and format as dependency list."""
    req_file = ROOT / "requirements.txt"
    if not req_file.exists():
        return "(requirements.txt not found)"

    deps = []
    for line in req_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            deps.append(line)
    return ", ".join(deps)


def _list_workflows() -> str:
    """List GitHub Actions workflows."""
    wf_dir = ROOT / ".github" / "workflows"
    if not wf_dir.is_dir():
        return "(no workflows found)"

    lines = []
    for f in sorted(wf_dir.glob("*.yml")):
        # Try to extract the workflow name from the file
        name = f.stem
        try:
            text = f.read_text(encoding="utf-8")
            for txt_line in text.splitlines():
                if txt_line.startswith("name:"):
                    name = txt_line.split(":", 1)[1].strip().strip('"').strip("'")
                    break
        except (UnicodeDecodeError, OSError):
            pass
        lines.append(f"- {f.name} - {name}")
    return "\n".join(lines)


def _list_adrs() -> str:
    """List Architecture Decision Records."""
    adr_dir = ROOT / "docs" / "adr"
    if not adr_dir.is_dir():
        return "(no ADRs found)"

    lines = []
    for f in sorted(adr_dir.glob("ADR-*.md")):
        # Extract title from first heading
        title = f.stem
        try:
            text = f.read_text(encoding="utf-8")
            for txt_line in text.splitlines():
                if txt_line.startswith("# "):
                    title = txt_line[2:].strip()
                    break
        except (UnicodeDecodeError, OSError):
            pass
        lines.append(f"- {title}")
    return "\n".join(lines)


def _extract_coverage_threshold() -> str:
    """Read coverage threshold from pytest.ini."""
    pytest_ini = ROOT / "pytest.ini"
    if not pytest_ini.exists():
        return "unknown"

    text = pytest_ini.read_text(encoding="utf-8")
    match = re.search(r"--cov-fail-under[=\s](\d+)", text)
    if match:
        return f"{match.group(1)}%"
    return "unknown"


def _extract_known_limitations() -> str:
    """Extract known limitations from PROJECT_STATUS.md."""
    status_file = ROOT / "docs" / "PROJECT_STATUS.md"
    if not status_file.exists():
        return "(see docs/PROJECT_STATUS.md)"

    text = status_file.read_text(encoding="utf-8")
    # Find the Known Limitations section
    in_section = False
    lines = []
    for line in text.splitlines():
        if "## Known Limitations" in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("|") and "Issue" not in line and "---" not in line:
            # Parse table row: | issue | severity | notes |
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 1:
                lines.append(f"- {parts[0]}")
    return "\n".join(lines) if lines else "(none documented)"


def _count_source_files() -> tuple[int, int]:
    """Count Python files and total lines in src/."""
    if not SRC_DIR.is_dir():
        return 0, 0
    file_count = 0
    line_count = 0
    for f in SRC_DIR.rglob("*.py"):
        if "__pycache__" in str(f):
            continue
        file_count += 1
        try:
            line_count += len(f.read_text(encoding="utf-8").splitlines())
        except (UnicodeDecodeError, OSError):
            pass
    return file_count, line_count


# -- Static sections --------------------------------------------------------
# These require human judgment and change infrequently.
# Edit these strings when architecture changes significantly.

STATIC_PURPOSE = """Purpose & context
Santiago is building DocRawl ({version}, github.com/plater7/docrawl), a self-hosted web scraping tool that converts documentation websites into clean Markdown (or structured JSON) files using an LLM pipeline. The project follows a "simplicity wins" philosophy with backward compatibility and graceful failure handling as core principles. Santiago works as a software architect and uses an issue-driven, PR-based development workflow with conventional commits, feature branches, and GitHub CLI."""

STATIC_ARCHITECTURE = """Architecture overview
Stack: FastAPI + Playwright + markdownify + httpx + SSE (sse-starlette), Docker on port 8002
Pipeline: URL Discovery (3 strategies) -> URL Filtering (deterministic + robots.txt + LLM) -> Scraping (5-level fallback chain) -> LLM Cleanup (3-tier classification) -> Output (markdown chunks or structured JSON)
LLM providers: Ollama (default, local), OpenRouter (OPENROUTER_API_KEY), OpenCode (OPENCODE_API_KEY), LM Studio (local, optional Bearer token). Model routing by namespace prefix auto-detection. Three model roles: crawl_model, pipeline_model, reasoning_model. Model list caching (60s TTL)
URL discovery cascade: 1) sitemap.xml parsing 2) nav parsing via Playwright 3) recursive BFS crawl (parallel per-depth, 1000 URL cap)
Scraping 5-level fallback: 1) PageCache (24h TTL, opt-in) 2) Native Markdown (content negotiation) 3) Markdown proxy 4) HTTP fast-path (httpx + markdownify) 5) Playwright full render (PagePool)
LLM cleanup 3-tier: skip (code >60% or short <2000 chars), cleanup (noise detected), heavy (broken tables/LaTeX)
Security: SSRF validation, Pydantic input validation, rate limiting, API key auth, CSP headers, XML input wrapping, defusedxml"""

STATIC_DESIGN_DECISIONS = """Key design decisions
- Simplicity wins: features fail gracefully, backward compatible, opt-in with sensible defaults
- HTML pre-cleaning before markdownify dramatically reduces chunk count and LLM processing time
- 5-level fallback chain: lighter approaches first, escalate only on failure
- PagePool reuse: ~40% scraping time reduction vs. open/close per URL
- 3-tier cleanup classification: ~30% reduction in LLM calls
- Dynamic timeouts (BASE_TIMEOUT + per-KB scaling) prevent premature failures and indefinite hangs
- Atomic file writes (.tmp then os.replace) for crash-safe state persistence
- Checkpoint pause/resume: JobState persisted to .job_state.json, resume creates new job with pending URLs"""

STATIC_CONVENTIONS = """Conventions & patterns
- Issue-driven development: GitHub issues -> feature branches -> PRs with conventional commits
- Uses Claude Code CLI for planning and implementation
- Testing approach: real documentation sites at ascending difficulty (httpx -> FastAPI -> Stripe -> Cloudflare)
- Runtime: Docker, Playwright, Ollama, asyncio
- Dev tools: Claude Code CLI, GitHub CLI, ruff (linting), pre-commit
- Governance: Nebula for automation/monitoring, Claude Code for implementation, Notion for project planning"""


# -- Generator --------------------------------------------------------------


def generate() -> str:
    """Build the complete Memory.md content."""
    version = _detect_version()
    file_count, line_count = _count_source_files()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sections = []

    # Header
    sections.append(f"<!-- Auto-generated by scripts/generate_memory.py \u2014 {now} -->")
    sections.append(f"<!-- Do not edit manually. Edit the script or static sections instead. -->")

    # Purpose (static with version interpolation)
    sections.append(STATIC_PURPOSE.format(version=version))

    # Technical reference (dynamic)
    sections.append(f"""DocRawl technical reference

Version: {version} | {file_count} Python files | ~{line_count} lines in src/""")

    # Module structure (dynamic)
    sections.append(f"""Module structure
{_extract_module_map()}""")

    # Architecture (static)
    sections.append(STATIC_ARCHITECTURE)

    # Design decisions (static)
    sections.append(STATIC_DESIGN_DECISIONS)

    # CI/CD (dynamic)
    wf_count = len(list((ROOT / ".github" / "workflows").glob("*.yml"))) if (ROOT / ".github" / "workflows").is_dir() else 0
    sections.append(f"""CI/CD ({wf_count} GitHub Actions workflows)
{_list_workflows()}
All actions use pinned SHA versions. Concurrency groups prevent duplicate runs.""")

    # Testing (dynamic)
    sections.append(f"""Testing
Coverage threshold: {_extract_coverage_threshold()}
Target: 65%""")

    # Dependencies (dynamic)
    sections.append(f"""Dependencies
{_read_dependencies()}""")

    # ADRs (dynamic)
    sections.append(f"""Architecture Decision Records
{_list_adrs()}""")

    # Known limitations (dynamic from PROJECT_STATUS.md)
    sections.append(f"""Known limitations
{_extract_known_limitations()}""")

    # Conventions (static)
    sections.append(STATIC_CONVENTIONS)

    return "\n\n".join(sections) + "\n"


# -- CLI --------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate docs/Memory.md")
    parser.add_argument("-o", "--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if docs/Memory.md is stale (for CI)",
    )
    args = parser.parse_args()

    content = generate()

    if args.check:
        if not args.output.exists():
            print(f"STALE: {args.output} does not exist", file=sys.stderr)
            sys.exit(1)
        existing = args.output.read_text(encoding="utf-8")
        # Strip the timestamp line for comparison (first two lines are comments with timestamp)
        def strip_timestamp(text: str) -> str:
            lines = text.splitlines()
            return "\n".join(line for line in lines if not line.startswith("<!-- Auto-generated"))
        if hashlib.sha256(strip_timestamp(existing).encode()).hexdigest() != hashlib.sha256(strip_timestamp(content).encode()).hexdigest():
            print(f"STALE: {args.output} needs regeneration", file=sys.stderr)
            sys.exit(1)
        print(f"OK: {args.output} is up to date")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"Wrote {args.output} ({len(content):,} bytes)")


if __name__ == "__main__":
    main()
