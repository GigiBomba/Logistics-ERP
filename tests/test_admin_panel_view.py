"""Tests for the admin panel view."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def admin_panel(qt_widget, qtbot):
    db = MagicMock()
    api_client = MagicMock()
    view = __import__(
        "ui.views.admin_panel_view", fromlist=["QtAdminPanelView"]
    ).QtAdminPanelView(
        qt_widget,
        db=db,
        api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


class TestQtAdminPanelView:
    """Suite of tests for QtAdminPanelView."""

    def test_creation(self, admin_panel):
        """View constructs without crashing."""
        assert admin_panel.db is not None
        assert admin_panel._api is not None

    def test_tab_widget_created(self, admin_panel):
        """Main tab widget is present."""
        assert hasattr(admin_panel, "_tab_widget")
        assert admin_panel._tab_widget.count() == 5

    def test_diagnostics_tab_widgets(self, admin_panel):
        """Diagnostics tab (index 0) has latency, celery, redis, config cards."""
        assert hasattr(admin_panel, "_diag_latency")
        assert hasattr(admin_panel, "_celery_active")
        assert hasattr(admin_panel, "_celery_scheduled")
        assert hasattr(admin_panel, "_celery_queue")
        assert hasattr(admin_panel, "_celery_workers")
        assert hasattr(admin_panel, "_redis_connected")
        assert hasattr(admin_panel, "_redis_memory")
        assert hasattr(admin_panel, "_redis_keys")
        assert hasattr(admin_panel, "_redis_hit_rate")
        assert hasattr(admin_panel, "_cfg_db_engine")
        assert hasattr(admin_panel, "_cfg_env_mode")
        assert hasattr(admin_panel, "_cfg_api_version")
        assert hasattr(admin_panel, "_cfg_debug")
        assert hasattr(admin_panel, "_diag_refresh_btn")

    def test_db_inspector_tab_widgets(self, admin_panel):
        """Database Inspector tab (index 1) has table combo, schema, sql editor."""
        assert hasattr(admin_panel, "_table_combo")
        assert hasattr(admin_panel, "_schema_table")
        assert hasattr(admin_panel, "_sql_input")
        assert hasattr(admin_panel, "_query_results")

    def test_doc_stats_tab_widgets(self, admin_panel):
        """Document Statistics tab (index 2) has stat cards and category table."""
        assert hasattr(admin_panel, "_doc_total")
        assert hasattr(admin_panel, "_doc_storage")
        assert hasattr(admin_panel, "_doc_ocr")
        assert hasattr(admin_panel, "_doc_orphans")
        assert hasattr(admin_panel, "_doc_cat_header")
        assert hasattr(admin_panel, "_doc_cat_table")

    def test_system_tab_widgets(self, admin_panel):
        """System Info tab (index 3) has sys table, env table, log text."""
        assert hasattr(admin_panel, "_sys_table")
        assert hasattr(admin_panel, "_env_table")
        assert hasattr(admin_panel, "_log_text")

    def test_health_tab_widgets(self, admin_panel):
        """Health tab (index 4) has health grid."""
        assert hasattr(admin_panel, "_health_grid")

    def test_shutdown_cleanup(self, admin_panel):
        """shutdown() stops workers and can be called safely."""
        admin_panel.shutdown()

    def test_shutdown_idempotent(self, admin_panel):
        """shutdown() can be called multiple times without error."""
        admin_panel.shutdown()
        admin_panel.shutdown()

    def test_wakeup_does_not_crash(self, admin_panel):
        """wakeup() triggers diagnostics fetch without crashing."""
        admin_panel._api = MagicMock()
        admin_panel.wakeup()

    def test_diagnostics_populates_labels(self, admin_panel):
        """_on_diagnostics updates widget labels from data."""
        data = {
            "latency_ms": 42,
            "celery": {
                "active_tasks": 3,
                "scheduled_tasks": 1,
                "queue_size": 0,
                "workers_online": 2,
            },
            "redis": {
                "connected": True,
                "memory_used_mb": 12.5,
                "keys_count": 150,
                "hit_rate_pct": 98.5,
            },
            "config_flags": {
                "db_engine": "postgresql",
                "env_mode": "staging",
                "api_version": "2.1.0",
                "debug_mode": False,
            },
        }
        admin_panel._on_diagnostics(data)
        assert admin_panel._celery_active.text() == "3"
        assert admin_panel._redis_connected.text() == "✓"
        assert admin_panel._cfg_db_engine.text() == "postgresql"

    def test_diagnostics_redis_unavailable(self, admin_panel):
        """When redis data is missing, labels show '—'."""
        data = {
            "latency_ms": 200,
            "celery": None,
            "redis": None,
            "config_flags": {},
        }
        admin_panel._on_diagnostics(data)
        assert admin_panel._redis_connected.text() == "✗"
        assert admin_panel._celery_active.text() == "Unavailable"
        assert admin_panel._cfg_db_engine.text() == "—"

    def test_on_tables_populates_combo(self, admin_panel):
        """_on_tables fills the table combo box."""
        tables = [{"name": "clients"}, {"name": "invoices"}]
        admin_panel._on_tables(tables)
        assert admin_panel._table_combo.count() == len(tables)

    def test_on_table_schema_populates_table(self, admin_panel):
        """_on_table_schema fills the schema table widget."""
        columns = [
            {"name": "id", "type": "INTEGER", "pk": True},
            {"name": "name", "type": "TEXT", "pk": False},
        ]
        admin_panel._on_table_schema(columns)
        assert admin_panel._schema_table.rowCount() == 2

    def test_on_query_result_empty(self, admin_panel):
        """Empty query result shows 'No data' header."""
        admin_panel._on_query_result([])
        assert admin_panel._query_results.columnCount() == 1
        assert admin_panel._query_results.horizontalHeaderItem(0).text() == "No data"

    def test_on_query_result_populates(self, admin_panel):
        """Query result populates the results table."""
        rows = [{"id": 1, "name": "test"}]
        admin_panel._on_query_result(rows)
        assert admin_panel._query_results.rowCount() == 1
        assert admin_panel._query_results.columnCount() == 2

    def test_on_doc_stats_populates_cards(self, admin_panel):
        """_on_doc_stats updates document stat cards."""
        data = {
            "total_documents": 100,
            "total_storage_bytes": 5 * 1024 ** 3,
            "ocr_coverage_pct": 75.0,
            "by_category": {"Invoice": 40, "Receipt": 60},
        }
        admin_panel._on_doc_stats(data)
        assert admin_panel._doc_cat_table.rowCount() == 2

    def test_on_health_creates_cards(self, admin_panel):
        """_on_health creates service status cards in the grid."""
        data = {
            "services": [
                {"name": "database", "status": "ok"},
                {"name": "cache", "status": "warning"},
            ]
        }
        admin_panel._on_health(data)
        assert admin_panel._health_grid.count() == 2

    def test_on_system_info_populates(self, admin_panel):
        """_on_system_info fills the system info table."""
        data = {
            "python_version": "3.11",
            "db_engine": "sqlite",
            "db_path": "/data/db.sqlite",
            "api_version": "1.0",
            "platform": "linux",
        }
        admin_panel._on_system_info(data)
        assert admin_panel._sys_table.rowCount() == 5

    def test_on_system_env_populates(self, admin_panel):
        """_on_system_env fills the environment table."""
        data = {"variables": {"HOME": "/root", "PATH": "/usr/bin"}}
        admin_panel._on_system_env(data)
        assert admin_panel._env_table.rowCount() == 2

    def test_on_logs_sets_text(self, admin_panel):
        """_on_logs sets the log text widget content."""
        data = {"lines": ["line1", "line2", "line3"]}
        admin_panel._on_logs(data)
        assert "line1" in admin_panel._log_text.toPlainText()
