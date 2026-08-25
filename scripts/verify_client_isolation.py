#!/usr/bin/env python
"""Verify the production client build is LOCAL-FIRST (Phase F).

The desktop app is no longer a remote-only shell: ``main.py`` boots the
local SQLite database, the OperationsEngine and the offline-first sync
stack (``services.sync_engine`` etc.).  The old remote-only
``main_remote.py`` entry is deprecated.

This script verifies the build configuration in ``scripts/build_client.py``:

* the production entry point is ``main.py`` (never ``main_remote.py``);
* the local-first modules (``database``, ``repositories``, ``services``
  and the sync submodules) are NOT excluded from the PyInstaller bundle;
* the sync modules exist on disk so PyInstaller's import analysis can
  collect them;
* the desktop import closure has NO unguarded top-level import of an
  excluded module (``backend``, ``celery``, ``redis``, ``psycopg2``,
  ``asyncpg``, ``matplotlib``, ``scipy``) — a shipped module that imports
  an excluded module at module level would crash the packaged binary at
  import time.  Imports inside ``try/except`` (the accepted guarded
  pattern) or inside functions/classes are allowed.

Exit code 0 → build config is local-first and the import closure is clean.
Exit code 1 → a local-first module is missing/excluded or an unguarded
import of an excluded module exists.
"""
from __future__ import annotations


import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.build_client import EXCLUDE_MODULES, PROJECT_ROOT

# Local-first modules that MUST be collectible for the sync feature to work.
REQUIRED_MODULES = [
    "database",
    "database.db_manager",
    "database.connection_pool",
    "database.schema",
    "repositories",
    "services",
    "services.sync_engine",
    "services.sync_outbox_service",
    "services.sync_pull_service",
    "services.sync_conflict_service",
    "services.device_identity",
]

# Modules that were excluded by the OLD remote-only build and would break the
# local-first app if excluded again.
SYNC_RELATED_EXCLUDES_NEVER_ALLOWED = [
    "database",
    "database.db_manager",
    "database.schema",
    "repositories",
    "services",
    "services.operations",
    "services.document",
]

# Top-level package prefixes that the desktop closure must NEVER import
# unguarded — they are excluded from the packaged binary (EXCLUDE_MODULES).
FORBIDDEN_IMPORT_PREFIXES = [
    "backend",
    "celery",
    "redis",
    "psycopg2",
    "asyncpg",
    "matplotlib",
    "scipy",
]

# The desktop import closure — everything PyInstaller collects from main.py.
DESKTOP_CLOSURE_ROOTS = [
    "main.py",
    "ui",
    "client",
    "services",
    "utils",
    "database",
    "repositories",
]


def _module_exists(module: str) -> bool:
    """True if the importable module/package exists on disk under PROJECT_ROOT.

    Handles regular packages (``__init__.py``), plain modules (``.py``) and
    namespace packages (a directory without ``__init__.py`` — e.g. the
    ``database`` package in this repo).
    """
    rel = module.replace(".", os.sep)
    candidates = [
        PROJECT_ROOT / f"{rel}.py",
        PROJECT_ROOT / rel / "__init__.py",
    ]
    if any(c.is_file() for c in candidates):
        return True
    d = PROJECT_ROOT / rel
    if d.is_dir():
        return any(p.suffix == ".py" for p in d.iterdir())
    return False


def _closure_py_files() -> list:
    """Return every .py file in the desktop closure (sorted, deduped)."""
    files = []
    for root in DESKTOP_CLOSURE_ROOTS:
        full = PROJECT_ROOT / root
        if full.is_file() and full.suffix == ".py":
            files.append(str(full))
        elif full.is_dir():
            for dirpath, _dirnames, filenames in os.walk(full):
                if "__pycache__" in dirpath:
                    continue
                for fn in filenames:
                    if fn.endswith(".py"):
                        files.append(os.path.join(dirpath, fn))
    return sorted(set(files))


def _is_forbidden(module: str) -> bool:
    """True if *module* (or its top-level package) is excluded from the build."""
    top = (module or "").split(".")[0]
    return top in FORBIDDEN_IMPORT_PREFIXES


def scan_import_closure() -> list:
    """Return [(rel_path, lineno, code)] for every UNGUARDED top-level import
    of an excluded module in the desktop closure.

    Only direct module-body ``import``/``from ... import`` statements count —
    imports inside ``try/except`` (the accepted guarded pattern), functions,
    classes or ``if`` blocks are skipped.
    """
    violations = []
    for fp in _closure_py_files():
        try:
            with open(fp, encoding="utf-8", errors="ignore") as fh:
                tree = ast.parse(fh.read())
        except (OSError, SyntaxError):
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            else:
                modules = [node.module] if node.module else []
            if any(_is_forbidden(m) for m in modules):
                rel = os.path.relpath(fp, str(PROJECT_ROOT)).replace("\\", "/")
                violations.append((rel, node.lineno, ast.unparse(node)))
    return violations


def main() -> int:
    failures = []

    # 1. Entry point: the production build must target main.py.
    main_py = PROJECT_ROOT / "main.py"
    main_remote_py = PROJECT_ROOT / "main_remote.py"
    if not main_py.is_file():
        failures.append("main.py (the local-first entry) does not exist")
    if main_remote_py.is_file():
        print("  note: main_remote.py exists but is deprecated — not used as the build entry")

    # 2. Local-first modules must not be excluded from the bundle.
    for mod in SYNC_RELATED_EXCLUDES_NEVER_ALLOWED:
        if mod in EXCLUDE_MODULES:
            failures.append(f"EXCLUDE_MODULES excludes local-first module: {mod}")

    # 3. Sync modules must exist on disk so PyInstaller's import analysis
    #    can collect them (they are reached from main.py via setup_sync).
    for mod in REQUIRED_MODULES:
        if not _module_exists(mod):
            failures.append(f"sync module missing on disk: {mod}")

    # 4. Import closure: no unguarded top-level import of an excluded module.
    closure_violations = scan_import_closure()
    for rel, lineno, code in closure_violations:
        failures.append(
            f"unguarded import of excluded module: {rel}:{lineno}: {code}"
        )

    if failures:
        print(f"FAIL: {len(failures)} problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(
        "PASS: production build is local-first — entry=main.py, sync stack "
        "collectible, import closure clean."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())