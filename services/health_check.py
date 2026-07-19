"""Application health check — verifies DB, filesystem, and core services.

Used by the startup sequence and can be invoked programmatically for diagnostics.
Returns a dict with status and per-component details for each check.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from repositories.settings_repository import SettingsRepository

logger = logging.getLogger("health_check")


def check_database(db_path: str | None = None) -> dict[str, Any]:
    """Verify the database is accessible and has expected tables.

    Supports both SQLite (file-based) and PostgreSQL (connection-pool)
    engines.  Pool statistics are included in the result when available.
    """
    from config import Config

    engine = Config.DB_ENGINE
    path = db_path or Config.DB_PATH
    result: dict[str, Any] = {"component": "database", "path": path, "engine": engine}

    try:
        if engine == "postgresql":
            dsn = Config.POSTGRES_DSN or path
            from database.db_manager import DatabaseManager
            db = DatabaseManager(dsn, engine="postgresql")
            try:
                # Quick connectivity check (engine-agnostic)
                db.execute("SELECT 1")
                # PostgreSQL-specific health checks via _table_exists
                table_checks = {}
                for tbl in ["alerts", "trips", "trucks", "invoices", "settings"]:
                    table_checks[tbl] = db._table_exists(tbl)
                result["table_checks"] = table_checks
                tables = SettingsRepository(db).get_table_names()
                expected_tables = {"alerts", "trips", "trucks", "invoices", "settings"}
                missing = expected_tables - set(tables)
                result["pool"] = db.health_stats
            finally:
                db.close()
            if missing:
                result["status"] = "unhealthy"
                result["error"] = f"Missing critical tables: {', '.join(sorted(missing))}"
                result["table_count"] = len(tables)
                return result
            result["status"] = "healthy"
            result["table_count"] = len(tables)
            return result
        else:
            if not os.path.exists(path):
                result["status"] = "unhealthy"
                result["error"] = f"Database file not found: {path}"
                return result
            from database.db_manager import DatabaseManager
            db = DatabaseManager(path)
            try:
                tables = SettingsRepository(db).get_table_names()
                expected_tables = {"alerts", "trips", "trucks", "invoices", "settings"}
                missing = expected_tables - set(tables)
            finally:
                db.close()
            if missing:
                result["status"] = "unhealthy"
                result["error"] = f"Missing critical tables: {', '.join(sorted(missing))}"
                result["table_count"] = len(tables)
                return result
            result["status"] = "healthy"
            result["table_count"] = len(tables)
            return result
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)
        return result


def check_filesystem() -> dict[str, Any]:
    """Verify critical directories exist and are writable."""
    dirs = ["data", "logs", "invoices", "reports"]
    result: dict[str, Any] = {"component": "filesystem"}
    ok = True
    details = {}
    for d in dirs:
        if os.path.isdir(d):
            try:
                test_file = os.path.join(d, ".health_check_test")
                with open(test_file, "w") as f:
                    f.write("ok")
                os.remove(test_file)
                details[d] = "ok (rw)"
            except Exception as e:
                details[d] = f"not writable: {e}"
                ok = False
        else:
            try:
                os.makedirs(d, exist_ok=True)
                details[d] = "created"
            except Exception as e:
                details[d] = f"cannot create: {e}"
                ok = False
    result["status"] = "healthy" if ok else "unhealthy"
    result["details"] = details
    return result


def check_core_imports() -> dict[str, Any]:
    """Verify core Python dependencies can be imported."""
    required = [
        "PySide6", "PySide6.QtWidgets", "PySide6.QtWebEngineWidgets",
        "plotly", "choreographer", "folium", "requests",
        "reportlab", "pikepdf", "PIL",
        "qtawesome",
    ]
    result: dict[str, Any] = {"component": "imports"}
    ok = True
    details = {}
    for module in required:
        try:
            __import__(module)
            details[module] = "ok"
        except ImportError as e:
            details[module] = f"missing: {e}"
            ok = False
    result["status"] = "healthy" if ok else "degraded"
    result["details"] = details
    return result


def run_health_check(db_path: str | None = None) -> dict[str, Any]:
    """Run all health checks and return a consolidated report.

    Returns a dict with:
        overall: "healthy" | "degraded" | "unhealthy"
        checks: list of per-component results
    """
    checks = [
        check_database(db_path),
        check_filesystem(),
        check_core_imports(),
    ]
    statuses = {c["status"] for c in checks}
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return {"overall": overall, "checks": checks}


if __name__ == "__main__":
    import json
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logging.basicConfig(level=logging.WARNING)
    result = run_health_check()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["overall"] != "healthy":
        sys.exit(1)
