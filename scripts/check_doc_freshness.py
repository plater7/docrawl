#!/usr/bin/env python3
"""Verify API_VERSION in src/main.py matches docs/PROJECT_STATUS.md header.

Exit 0 = fresh. Exit 1 = stale.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Extract API_VERSION from src/main.py
main_py = ROOT / "src" / "main.py"
if not main_py.exists():
    print(f"ERROR: Required file not found: {main_py}")
    sys.exit(1)
source = main_py.read_text(encoding="utf-8")
tree = ast.parse(source)
api_version = None
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == "API_VERSION":
                api_version = ast.literal_eval(node.value)
                break

if not api_version:
    print("ERROR: Could not find API_VERSION in src/main.py")
    sys.exit(1)

# Extract version from PROJECT_STATUS.md header
status_md = ROOT / "docs" / "PROJECT_STATUS.md"
if not status_md.exists():
    print(f"ERROR: Required file not found: {status_md}")
    sys.exit(1)
status_text = status_md.read_text(encoding="utf-8")
m = re.search(r"DocRawl v([\d]+\.[\d]+\.?[\d]*)", status_text)
if not m:
    print("ERROR: Could not find version pattern in docs/PROJECT_STATUS.md")
    sys.exit(1)
doc_version = m.group(1)

if api_version != doc_version:
    print(
        f"STALE: src/main.py API_VERSION={api_version!r} "
        f"but docs/PROJECT_STATUS.md says v{doc_version}"
    )
    print("Update docs/PROJECT_STATUS.md to match before releasing.")
    sys.exit(1)

print(f"OK: API_VERSION={api_version!r} matches PROJECT_STATUS.md")
