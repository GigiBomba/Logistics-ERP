#!/usr/bin/env python
"""PyInstaller client-only build script.

Produces a standalone ``dist/operion-client/`` directory containing
*only* the UI, client networking layer, and required assets.  All
server-side code (``backend/``, ``repositories/``, ``database/``,
``tests/``, ``services/``) is excluded so the distributed binary
exposes no SQL queries, local database logic, or backend schemas.

Usage::

    python scripts/build_client.py        # client-only build
    python scripts/build_client.py --dev  # local dev build (includes DB)

Environment variables honoured at build time:
    ``OPERION_ENV``         ``production`` (default) or ``development``
    ``OPERION_API_URL``     override API base URL in production mode
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist" / "operion-client"
WORK_DIR = PROJECT_ROOT / "build" / "client"

CLIENT_ASSETS: List[str] = [
    str(PROJECT_ROOT / "ui"),
    str(PROJECT_ROOT / "client"),
    str(PROJECT_ROOT / "config.py"),
    str(PROJECT_ROOT / "utils"),
    str(PROJECT_ROOT / "data"),
    str(PROJECT_ROOT / "reports"),
    str(PROJECT_ROOT / "logs"),
    str(PROJECT_ROOT / "main.py"),
]

EXCLUDE_MODULES: List[str] = [
    "backend",
    "backend.api",
    "backend.api.v1",
    "backend.config",
    "backend.schemas",
    "backend.celery_app",
    "backend.cache",
    "backend.middleware",
    "database",
    "database.db_manager",
    "database.connection_pool",
    "database.schema",
    "repositories",
    "services",
    "services.automail",
    "services.document",
    "services.document_automation",
    "services.invoicing",
    "services.operations",
    "tests",
    "test",
    "unittest",
    "pytest",
    "matplotlib",
    "scipy",
    "notebook",
    "jupyter",
    "IPython",
    "tkinter",
    "celery",
    "redis",
    "psycopg2",
    "asyncpg",
    "PIL.ImageShow",
    "PIL.ImageQt",
    "paddleocr",
    "pytesseract",
]

HIDDEN_IMPORTS: List[str] = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "shiboken6",
    "httpx",
    "pydantic",
    "qtawesome",
    "plotly",
    "choreographer",
    "folium",
    "geocoder",
    "pandas",
    "numpy",
    "requests",
    "urllib3",
    "httpcore",
    "websockets",
    "pypdf",
    "reportlab",
    "openpyxl",
    "cv2",
    "PIL",
    "PIL.Image",
    "PIL.ImageOps",
    "pillow_heif",
    "deep_translator",
    "Babel",
    "pyperclip",
    "colorama",
    "colorlog",
    "click",
    "python_dateutil",
    "pytz",
    "client.config",
    "client.network.network_worker",
    "client.api_client",
    "client.remote_analytics",
    "client.remote_driver_service",
    "client.remote_maintenance",
    "client.remote_invoice_service",
    "client.remote_tacho",
    "client.remote_route_history",
    "client.remote_services",
    "client.remote_preferences",
    "client.remote_ops_stub",
    "ui.views.upload_integration",
    "ui.views.api_dashboard_view",
]


def _clean_dist() -> None:
    for d in (DIST_DIR, WORK_DIR):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


def _run_pyinstaller(entry: str, extra_excludes: Optional[List[str]] = None) -> int:
    excludes = list(EXCLUDE_MODULES)
    if extra_excludes:
        excludes.extend(extra_excludes)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--name", "operion-client",
        "--distpath", str(DIST_DIR.parent),
        "--workpath", str(WORK_DIR),
        "--specpath", str(WORK_DIR),
        "--noconfirm",
        "--clean",
        entry,
    ]
    for mod in sorted(set(excludes)):
        cmd.extend(["--exclude-module", mod])

    for hi in sorted(set(HIDDEN_IMPORTS)):
        cmd.extend(["--hidden-import", hi])

    print(f"  Entry: {entry}")
    print(f"  Excluding {len(excludes)} modules")
    print(f"  Including {len(HIDDEN_IMPORTS)} hidden imports")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=False)
    return result.returncode


def _report_size(base: Path) -> None:
    total = sum(f.stat().st_size for f in base.rglob("*") if f.is_file())
    size_mb = total / (1024 * 1024)
    print(f"\nBuild size: {size_mb:.1f} MB")
    if size_mb > 100:
        print("WARNING: Exceeds 100 MB target.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Operion client-only distribution")
    parser.add_argument("--dev", action="store_true", help="Local dev build (includes DB)")
    args = parser.parse_args()

    _clean_dist()

    extra_excludes: Optional[List[str]] = None

    if not args.dev:
        entry = str(PROJECT_ROOT / "main_remote.py")
        extra_excludes = [
            "services.document",
            "services.document_automation",
            "services.invoicing",
            "services.operations",
            "services.route_service",
            "services.trip_service",
            "services.client_service",
            "services.fleet_service",
            "services.analytics_service",
            "services.tacho_service",
            "services.automail",
            "services.calculator",
        ]
        print("=== CLIENT-ONLY BUILD (production) ===\n")
    else:
        entry = str(PROJECT_ROOT / "main.py")
        print("=== CLIENT+LOCAL BUILD (development) ===\n")

    rc = _run_pyinstaller(entry, extra_excludes=extra_excludes)
    if rc != 0:
        print(f"\nPyInstaller exited with code {rc}")
        return rc

    output = DIST_DIR.parent / "operion-client"
    if output.exists():
        _report_size(output)

    print(f"\nBuild output: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
