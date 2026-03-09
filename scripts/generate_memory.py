#!/usr/bin/env python3
"""Generate docs/MEMORY.md from the current codebase metadata.

Extracts project metadata (version, architecture, dependencies, CI/CD,
decisions, conventions) and renders a Memory file for Claude Code CLI.
Designed to run automatically via GitHub Actions on merge to main.

Usage:
    python scripts/generate_memory.py              # writes docs/MEMORY.md
    python scripts/generate_memory.py -o /dev/stdout  # preview to terminal
    python scripts/generate_memory.py --check       # exit 1 if memory is stale
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# -- Configuration --

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
OUTPUT_DEFAULT = ROOT / "docs" / "MEMORY.md"


# -- Helpers --


def _detect_version() -> str:
    """Read API_VERSION from src/main.py."""
    main_py = SRC_DIR / "main.py"
    if main_py.exists():
        text = main_py.read_text(encoding="utf-8")
        match = re.search(r'API_VERSION\s*=\s*["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)
    return "unknown"


def _build_module_map() -> list[str]:
    """Walk src/ and extract module names with their docstrings."""
    lines: list[str] = []
    for py in sorted(SRC_DIR.rglob("*.py")):
        if "__pycache__" in str(py):
            continue
        rel = py.relative_to(SRC_DIR)
        docstring = ""
        try:
            content = py.read_text(encoding="utf-8")
            match = re.search(r'^"""(.+?)"""', content, re.DOTALL)
            if match:
                first_line = match.group(1).strip().split("\n")[0]
                docstring = f" - {first_line}"
        except Exception:
            pass
        lines.append(f"  src/{rel}{docstring}")
    return lines


def _read_dependencies() -> list[str]:
    """Read requirements.txt and extract package names."""
    lines: list[str] = []
    req_file = ROOT / "requirements.txt"
    if req_file.exists():
        for line in req_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                pkg = re.split(r"[=><!~]", line)[0].strip()
                lines.append(f"  {pkg}")
    return lines


def _read_dev_dependencies() -> list[str]:
    """Read requirements-dev.txt for dev/test dependencies."""
    lines: list[str] = []
    req_file = ROOT / "requirements-dev.txt"
    if req_file.exists():
        for line in req_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                pkg = re.split(r"[=><!~]", line)[0].strip()
                lines.append(f"  {pkg}")
    return lines


def _read_pytest_config() -> dict[str, str]:
    """Extract key pytest settings from pytest.ini."""
    config: dict[str, str] = {}
    ini_file = ROOT / "pytest.ini"
    if ini_file.exists():
        text = ini_file.read_text(encoding="utf-8")
        match = re.search(r"--cov-fail-under=(\d+)", text)
        if match:
            config["coverage_threshold"] = match.group(1)
        match = re.search(r"Target:\s*(\d+)%", text)
        if match:
            config["coverage_target"] = match.group(1)
        match = re.search(r"asyncio_mode\s*=\s*(\w+)", text)
        if match:
            config["asyncio_mode"] = match.group(1)
    return config


def _list_workflows() -> list[str]:
    """List all GitHub Actions workflow files with descriptions."""
    lines: list[str] = []
    wf_dir = ROOT / ".github" / "workflows"
    if wf_dir.exists():
        for yml in sorted(wf_dir.glob("*.yml")):
            name = yml.stem
            try:
                content = yml.read_text(encoding="utf-8")
                match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
                if match:
                    name = match.group(1).strip().strip('"').strip("'")
            except Exception:
                pass
            lines.append(f"  {yml.name} - {name}")
    return lines


def _list_adrs() -> list[str]:
    """List ADR files with their titles."""
    lines: list[str] = []
    adr_dir = ROOT / "docs" / "adr"
    if adr_dir.exists():
        for md in sorted(adr_dir.glob("*.md")):
            title = md.stem
            try:
                content = md.read_text(encoding="utf-8")
                match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                if match:
                    title = match.group(1).strip()
            except Exception:
                pass
            lines.append(f"  {md.name} - {title}")
    return lines


def _extract_known_limitations() -> list[str]:
    """Extract Known Limitations from PROJECT_STATUS.md."""
    lines: list[str] = []
    ps_file = ROOT / "docs" / "PROJECT_STATUS.md"
    if ps_file.exists():
        text = ps_file.read_text(encoding="utf-8")
        match = re.search(
            r"##\s*Known\s+Limitations(.+?)(?=\n##|\Z)", text, re.DOTALL
        )
        if match:
            section = match.group(1)
            for line in section.strip().splitlines():
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    lines.append(f"  {line}")
    return lines


def _extract_roadmap() -> list[str]:
    """Extract Roadmap items from PROJECT_STATUS.md."""
    lines: list[str] = []
    ps_file = ROOT / "docs" / "PROJECT_STATUS.md"
    if ps_file.exists():
        text = ps_file.read_text(encoding="utf-8")
        match = re.search(
            r"##\s*Roadmap(.+?)(?=\n##|\Z)", text, re.DOTALL
        )
        if match:
            section = match.group(1)
            for line in section.strip().splitlines():
                line = line.strip()
                if line.startswith(("- ", "* ", "### ")):
                    lines.append(f"  {line}")
    return lines


def _extract_architecture_summary() -> str:
    """Extract key sections from ARCHITECTURE.md."""
    arch_file = ROOT / "ARCHITECTURE.md"
    if not arch_file.exists():
        return ""
    text = arch_file.read_text(encoding="utf-8")
    summaries: list[str] = []
    match = re.search(
        r"##\s*Key\s+Design\s+Decisions(.+?)(?=\n##|\Z)", text, re.DOTALL
    )
    if match:
        section = match.group(1)
        for line in section.strip().splitlines():
            line = line.strip()
            if line.startswith(("- ", "* ", "### ")):
                summaries.append(line)
    return "\n".join(summaries) if summaries else ""


def _extract_stack_info() -> str:
    """Extract stack/technology info from main.py and requirements."""
    parts: list[str] = []
    main_py = SRC_DIR / "main.py"
    if main_py.exists():
        text = main_py.read_text(encoding="utf-8")
        if "FastAPI" in text:
            parts.append("FastAPI")
        if "Playwright" in text or "playwright" in text:
            parts.append("Playwright")
    req_file = ROOT / "requirements.txt"
    if req_file.exists():
        text = req_file.read_text(encoding="utf-8")
        for lib in ["markdownify", "httpx", "sse-starlette", "slowapi",
                     "defusedxml", "pydantic"]:
            if lib in text:
                parts.append(lib)
    if (ROOT / "Dockerfile").exists() or (ROOT / "docker" / "Dockerfile").exists():
        parts.append("Docker")
    return ", ".join(parts) if parts else "Unknown stack"


def _detect_llm_providers() -> list[str]:
    """Detect configured LLM providers from client.py."""
    providers: list[str] = []
    client_py = SRC_DIR / "llm" / "client.py"
    if client_py.exists():
        text = client_py.read_text(encoding="utf-8")
        if "ollama" in text.lower():
            providers.append("Ollama (default, local)")
        if "openrouter" in text.lower():
            providers.append("OpenRouter (OPENROUTER_API_KEY)")
        if "opencode" in text.lower():
            providers.append("OpenCode (OPENCODE_API_KEY)")
        if "lm_studio" in text.lower() or "lmstudio" in text.lower() or "lm studio" in text.lower():
            providers.append("LM Studio (local)")
    return providers


def _list_docs() -> list[str]:
    """List documentation files at root and docs/."""
    lines: list[str] = []
    for name in ["README.md", "ARCHITECTURE.md", "CHANGELOG.md",
                  "CONTRIBUTING.md", "SECURITY.md", "LICENSE"]:
        p = ROOT / name
        if p.exists():
            size_kb = p.stat().st_size / 1024
            lines.append(f"  {name} ({size_kb:.0f}KB)")
    docs_dir = ROOT / "docs"
    if docs_dir.exists():
        for md in sorted(docs_dir.glob("*.md")):
            size_kb = md.stat().st_size / 1024
            lines.append(f"  docs/{md.name} ({size_kb:.0f}KB)")
    adr_dir = ROOT / "docs" / "adr"
    if adr_dir.exists():
        adr_count = len(list(adr_dir.glob("*.md")))
        if adr_count > 0:
            lines.append(f"  docs/adr/ ({adr_count} ADRs)")
    snap = ROOT / "SNAPSHOT.md"
    if snap.exists():
        size_kb = snap.stat().st_size / 1024
        lines.append(f"  SNAPSHOT.md ({size_kb:.0f}KB, auto-generated)")
    return lines


# -- Generator --


def generate(output: Path = OUTPUT_DEFAULT) -> str:
    """Generate the full MEMORY.md content."""
    version = _detect_version()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pytest_config = _read_pytest_config()

    parts: list[str] = []

    # Header
    parts.append(f"<!-- Auto-generated by scripts/generate_memory.py on {now} -->")
    parts.append("<!-- Do not edit manually -- changes will be overwritten on merge to main -->")
    parts.append("")

    # Purpose & context
    parts.append("Purpose & context")
    parts.append(
        f"Santiago is building DocRawl (v{version}, github.com/plater7/docrawl), "
        "a self-hosted web scraping tool that converts documentation websites into "
        "clean Markdown (or structured JSON) files using an LLM pipeline. The project "
        'follows a "simplicity wins" philosophy with backward compatibility and graceful '
        "failure handling as core principles. Santiago works as a software architect and "
        "uses an issue-driven, PR-based development workflow with conventional commits, "
        "feature branches, and GitHub CLI."
    )
    parts.append("")

    # Technical reference
    parts.append("DocRawl technical reference")
    parts.append("")

    # Stack
    stack = _extract_stack_info()
    parts.append(f"Stack: {stack}")

    # Module structure
    module_map = _build_module_map()
    if module_map:
        parts.append("Module structure:")
        parts.extend(module_map)
    parts.append("")

    # LLM providers
    providers = _detect_llm_providers()
    if providers:
        parts.append("LLM providers: " + "; ".join(providers))
        parts.append("")

    # CI/CD
    workflows = _list_workflows()
    if workflows:
        parts.append(f"CI/CD ({len(workflows)} GitHub Actions workflows)")
        parts.append("")
        parts.extend(workflows)
        parts.append("")

    # Architecture decisions
    adrs = _list_adrs()
    if adrs:
        parts.append("Architecture Decision Records")
        parts.append("")
        parts.extend(adrs)
        parts.append("")

    # Architecture summary
    arch_summary = _extract_architecture_summary()
    if arch_summary:
        parts.append("Key design decisions (from ARCHITECTURE.md)")
        parts.append("")
        parts.append(arch_summary)
        parts.append("")

    # Testing
    parts.append("Testing")
    parts.append("")
    threshold = pytest_config.get("coverage_threshold", "?")
    target = pytest_config.get("coverage_target", "?")
    async_mode = pytest_config.get("asyncio_mode", "?")
    parts.append(f"  Coverage threshold: {threshold}% (target: {target}%)")
    parts.append(f"  asyncio_mode: {async_mode}")
    parts.append("")

    # Dependencies
    deps = _read_dependencies()
    if deps:
        parts.append("Runtime dependencies")
        parts.append("")
        parts.extend(deps)
        parts.append("")

    dev_deps = _read_dev_dependencies()
    if dev_deps:
        parts.append("Dev/test dependencies")
        parts.append("")
        parts.extend(dev_deps)
        parts.append("")

    # Documentation
    docs = _list_docs()
    if docs:
        parts.append("Documentation")
        parts.append("")
        parts.extend(docs)
        parts.append("")

    # Known limitations
    limitations = _extract_known_limitations()
    if limitations:
        parts.append("Known limitations (from PROJECT_STATUS.md)")
        parts.append("")
        parts.extend(limitations)
        parts.append("")

    # Roadmap
    roadmap = _extract_roadmap()
    if roadmap:
        parts.append("Roadmap (from PROJECT_STATUS.md)")
        parts.append("")
        parts.extend(roadmap)
        parts.append("")

    # Key learnings (static -- principles, not auto-extractable)
    parts.append("Key learnings & principles")
    parts.append("")
    parts.append("  Simplicity wins: New features should fail gracefully, maintain backward compatibility, and be opt-in with sensible defaults")
    parts.append("  HTML pre-cleaning is critical: Removing framework noise before markdownify dramatically reduces chunk count and LLM processing time")
    parts.append("  LLM model sizing matters: Oversized models for mechanical cleanup tasks cause severe performance degradation")
    parts.append("  5-level fallback chain: lighter approaches first, escalate only on failure -- optimizes for common case")
    parts.append("  PagePool reuse: ~40% scraping time reduction vs. open/close per URL")
    parts.append("  3-tier cleanup classification: ~30% reduction in LLM calls by skipping code-heavy/short clean chunks")
    parts.append("  Dynamic timeouts (BASE_TIMEOUT + per-KB scaling) prevent both premature failures and indefinite hangs")
    parts.append("  Atomic file writes (.tmp then os.replace) for crash-safe state persistence")
    parts.append("")

    # Approach & patterns (static)
    parts.append("Approach & patterns")
    parts.append("")
    parts.append("  Issue-driven development: GitHub issues then feature branches then PRs with conventional commits")
    parts.append("  Uses Claude Code CLI for planning and implementation")
    parts.append("  Prefers systematic, multi-phase analysis before implementation")
    parts.append("  Testing approach: real documentation sites at ascending difficulty (httpx then FastAPI then Stripe then Cloudflare)")
    parts.append("  Workflow: Ubuntu WSL2 environment, GitHub CLI for PR management")
    parts.append("  Governance: Nebula for automation/monitoring, Claude Code for implementation, Notion for project planning")
    parts.append("")

    content = "\n".join(parts)

    # Content hash for staleness detection
    h = hashlib.sha256(content.encode()).hexdigest()
    content += f"\n---\n<!-- content-hash: {h} -->\n"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return h


def check_stale() -> bool:
    """Return True if docs/MEMORY.md is stale (hash mismatch)."""
    if not OUTPUT_DEFAULT.exists():
        return True
    existing = OUTPUT_DEFAULT.read_text(encoding="utf-8")
    match = re.search(r"<!-- content-hash: ([a-f0-9]+) -->", existing)
    if not match:
        return True
    old_hash = match.group(1)
    tmp = Path(tempfile.mktemp(suffix=".md"))
    try:
        new_hash = generate(tmp)
        return old_hash != new_hash
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate docs/MEMORY.md")
    parser.add_argument(
        "-o", "--output", type=Path, default=OUTPUT_DEFAULT,
        help="Output file path (default: docs/MEMORY.md)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Exit 1 if MEMORY.md is stale",
    )
    args = parser.parse_args()

    if args.check:
        if check_stale():
            print("docs/MEMORY.md is stale -- run generate_memory.py to update")
            sys.exit(1)
        print("docs/MEMORY.md is up to date")
        sys.exit(0)

    h = generate(args.output)
    print(f"Wrote {args.output}  (hash: {h[:12]}...)")


if __name__ == "__main__":
    main()
