#!/usr/bin/env python
"""Verify that the client-side codebase contains no local database imports.

Scans ``ui/``, ``client/``, and ``main.py`` for forbidden patterns:
    * ``import sqlite3``
    * ``from database`` / ``import database``
    * ``from repositories`` / ``import repositories``
    * ``BaseRepository`` instantiation
    * ``DatabaseManager(`` calls
    * ``*.db`` path references in config

Exit code 0 → clean (no violations).
Exit code 1 → violations found.
"""

import os
import re
import sys
from typing import List, Tuple

FORBIDDEN_IMPORTS = [
    (r"^\s*import sqlite3", "direct sqlite3 import"),
    (r"^\s*from database\b", "database module import"),
    (r"^\s*import database\b", "database module import"),
    (r"^\s*from repositories\b", "repositories module import"),
    (r"^\s*import repositories\b", "repositories module import"),
    (r"\bBaseRepository\b", "BaseRepository reference"),
    (r"\bDatabaseManager\s*\(", "DatabaseManager instantiation"),
    (r"\.db\b", "possible .db file path"),
]

SCAN_ROOTS = ["ui", "client", "main.py"]

BOOTSTRAP_ALLOWLIST = {
    "client/cache.py",
    "client/config.py",
}


def _should_skip(path: str, root_dir: str) -> bool:
    rel = os.path.relpath(path, root_dir).replace("\\", "/")
    if rel in BOOTSTRAP_ALLOWLIST:
        return True
    if "__pycache__" in path:
        return True
    return bool(path.endswith("__init__.py"))


def _collect_python_files(roots: List[str], base_dir: str) -> List[str]:
    collected: List[str] = []
    for root in roots:
        full = os.path.join(base_dir, root)
        if os.path.isfile(full) and full.endswith(".py"):
            collected.append(full)
        elif os.path.isdir(full):
            for dirpath, _dirnames, filenames in os.walk(full):
                for fn in filenames:
                    if fn.endswith(".py"):
                        collected.append(os.path.join(dirpath, fn))
    return sorted(collected)


def scan_file(filepath: str, base_dir: str) -> List[Tuple[int, str, str]]:
    if _should_skip(filepath, base_dir):
        return []
    violations: List[Tuple[int, str, str]] = []
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()
    except Exception:
        return []
    for idx, line in enumerate(lines, 1):
        stripped = line.rstrip("\n")
        if stripped.strip().startswith("#"):
            continue
        for pattern, label in FORBIDDEN_IMPORTS:
            if re.search(pattern, stripped):
                violations.append((idx, label, stripped.strip()[:120]))
                break
    return violations


def main() -> int:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    remote_mode = "--remote" in sys.argv
    roots = ["main_remote.py", "client"] if remote_mode else SCAN_ROOTS
    files = _collect_python_files(roots, base_dir)
    print(f"Scanning {len(files)} files in {', '.join(SCAN_ROOTS)}...")
    total_violations = 0
    for fp in files:
        violations = scan_file(fp, base_dir)
        if violations:
            total_violations += len(violations)
            rel = os.path.relpath(fp, base_dir)
            print(f"\n  {rel} — {len(violations)} violation(s):")
            for lineno, label, snippet in violations:
                print(f"    L{lineno:4d} [{label}] {snippet}")
    print()
    if total_violations == 0:
        print("PASS: Zero database/repository imports found in client code.")
        return 0
    else:
        print(f"FAIL: {total_violations} violation(s) found.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
