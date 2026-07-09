"""Tests for health_check module.

These tests mock external dependencies (filesystem, database, imports).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.health_check import (
    check_core_imports,
    check_database,
    check_filesystem,
    run_health_check,
)


# ── check_database ───────────────────────────────────────────────


class TestCheckDatabase:
    def test_healthy_db(self):
        """Database file exists and has all critical tables."""
        with patch("os.path.exists", return_value=True), \
             patch("database.db_manager.DatabaseManager"), \
             patch("services.health_check.SettingsRepository") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.get_table_names.return_value = ["alerts", "trips", "trucks", "invoices", "settings"]
            mock_settings_cls.return_value = mock_settings

            result = check_database("/fake/path.db")

            assert result["status"] == "healthy"
            assert result["table_count"] == 5
            assert result["path"] == "/fake/path.db"

    def test_db_file_not_found(self):
        with patch("os.path.exists", return_value=False):
            result = check_database("/nonexistent/path.db")
            assert result["status"] == "unhealthy"
            assert "not found" in result["error"]

    def test_db_connection_error(self):
        """Database exists but connection fails."""
        with patch("os.path.exists", return_value=True), \
             patch("sqlite3.connect", side_effect=Exception("connection refused")):
            result = check_database("/fake/path.db")
            assert result["status"] == "unhealthy"
            assert "connection refused" in result["error"]

    def test_component_name(self):
        with patch("os.path.exists", return_value=False):
            result = check_database()
            assert result["component"] == "database"

    def test_default_path_from_config(self):
        """When no db_path given, uses Config.DB_PATH."""
        with patch("config.Config.DB_PATH", "/default/path.db"), \
             patch("os.path.exists", return_value=False):
            result = check_database()
            assert result["path"] == "/default/path.db"


# ── check_filesystem ─────────────────────────────────────────────


class TestCheckFilesystem:
    def test_all_dirs_exist_and_writable(self, tmp_path):
        """All required directories exist and are writable."""
        dirs = ["data", "logs", "invoices", "reports"]
        for d in dirs:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)

        with patch("os.path.isdir", return_value=True), \
             patch("os.path.join", side_effect=lambda *a: str(tmp_path / a[-1])), \
             patch("os.makedirs"):

            # We need to patch open so the write test succeeds
            with patch("builtins.open", MagicMock()), \
                 patch("os.remove", MagicMock()):

                result = check_filesystem()

                assert result["status"] == "healthy"

    def test_missing_directory_gets_created(self, tmp_path):
        """If a directory is missing, the function tries to create it."""
        with patch("os.path.isdir", return_value=False), \
             patch("os.path.join", side_effect=lambda *a: str(tmp_path / a[-1])), \
             patch("os.makedirs") as mock_makedirs, \
             patch("builtins.open", MagicMock()), \
             patch("os.remove", MagicMock()):

            result = check_filesystem()

            mock_makedirs.assert_called()
            # The function creates missing dirs, so it should still be healthy
            assert result["status"] == "healthy"

    def test_directory_not_writable(self, tmp_path):
        """If a directory is not writable, status becomes unhealthy."""
        with patch("os.path.isdir", return_value=True), \
             patch("os.path.join", side_effect=lambda *a: str(tmp_path / a[-1])), \
             patch("builtins.open", side_effect=PermissionError("no write access")), \
             patch("os.remove", MagicMock()):

            result = check_filesystem()
            assert result["status"] == "unhealthy"

    def test_details_contains_all_dirs(self):
        with patch("os.path.isdir", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("os.remove", MagicMock()):
            result = check_filesystem()
            for d in ["data", "logs", "invoices", "reports"]:
                assert d in result["details"]

    def test_component_name(self):
        with patch("os.path.isdir", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("os.remove", MagicMock()):
            result = check_filesystem()
            assert result["component"] == "filesystem"


# ── check_core_imports ───────────────────────────────────────────


class TestCheckCoreImports:
    def test_all_imports_healthy(self):
        """All required modules import successfully."""
        with patch("builtins.__import__", return_value=MagicMock()):
            result = check_core_imports()
            assert result["status"] == "healthy"

    def test_some_imports_missing(self):
        """Some modules fail to import → degraded status."""
        def mock_import(name, *args, **kwargs):
            if name == "PIL":
                raise ImportError(f"No module named {name}")
            return MagicMock()

        with patch("builtins.__import__", side_effect=mock_import):
            result = check_core_imports()
            assert result["status"] == "degraded"
            assert "missing" in result["details"].get("PIL", "")

    def test_all_imports_missing(self):
        def mock_import(name, *args, **kwargs):
            raise ImportError(f"No module named {name}")

        with patch("builtins.__import__", side_effect=mock_import):
            result = check_core_imports()
            assert result["status"] == "degraded"

    def test_component_name(self):
        with patch("builtins.__import__", return_value=MagicMock()):
            result = check_core_imports()
            assert result["component"] == "imports"

    def test_details_contains_expected_modules(self):
        with patch("builtins.__import__", return_value=MagicMock()):
            result = check_core_imports()
            expected_modules = ["PySide6", "plotly", "folium", "requests", "reportlab"]
            for mod in expected_modules:
                assert mod in result["details"]


# ── run_health_check ─────────────────────────────────────────────


class TestRunHealthCheck:
    def test_all_healthy(self):
        with patch("services.health_check.check_database",
                   return_value={"component": "database", "status": "healthy"}):
            with patch("services.health_check.check_filesystem",
                       return_value={"component": "filesystem", "status": "healthy"}):
                with patch("services.health_check.check_core_imports",
                           return_value={"component": "imports", "status": "healthy"}):
                    result = run_health_check()
                    assert result["overall"] == "healthy"
                    assert len(result["checks"]) == 3

    def test_degraded_when_imports_degraded(self):
        with patch("services.health_check.check_database",
                   return_value={"component": "database", "status": "healthy"}):
            with patch("services.health_check.check_filesystem",
                       return_value={"component": "filesystem", "status": "healthy"}):
                with patch("services.health_check.check_core_imports",
                           return_value={"component": "imports", "status": "degraded"}):
                    result = run_health_check()
                    assert result["overall"] == "degraded"

    def test_unhealthy_when_db_unhealthy(self):
        with patch("services.health_check.check_database",
                   return_value={"component": "database", "status": "unhealthy"}):
            with patch("services.health_check.check_filesystem",
                       return_value={"component": "filesystem", "status": "healthy"}):
                with patch("services.health_check.check_core_imports",
                           return_value={"component": "imports", "status": "healthy"}):
                    result = run_health_check()
                    assert result["overall"] == "unhealthy"

    def test_unhealthy_dominates_degraded(self):
        """unhealthy should dominate degraded."""
        with patch("services.health_check.check_database",
                   return_value={"component": "database", "status": "unhealthy"}):
            with patch("services.health_check.check_filesystem",
                       return_value={"component": "filesystem", "status": "healthy"}):
                with patch("services.health_check.check_core_imports",
                           return_value={"component": "imports", "status": "degraded"}):
                    result = run_health_check()
                    assert result["overall"] == "unhealthy"

    def test_calls_all_three_checks(self):
        with patch("services.health_check.check_database",
                   return_value={"component": "database", "status": "healthy"}) as mock_db:
            with patch("services.health_check.check_filesystem",
                       return_value={"component": "filesystem", "status": "healthy"}) as mock_fs:
                with patch("services.health_check.check_core_imports",
                           return_value={"component": "imports", "status": "healthy"}) as mock_imp:
                    run_health_check()
                    mock_db.assert_called_once()
                    mock_fs.assert_called_once()
                    mock_imp.assert_called_once()

    def test_passes_db_path_to_check_database(self):
        with patch("services.health_check.check_database",
                   return_value={"component": "database", "status": "healthy"}) as mock_db:
            with patch("services.health_check.check_filesystem",
                       return_value={"component": "filesystem", "status": "healthy"}):
                with patch("services.health_check.check_core_imports",
                           return_value={"component": "imports", "status": "healthy"}):
                    run_health_check(db_path="/custom/path.db")
                    mock_db.assert_called_once_with("/custom/path.db")
