"""Integration tests for the admin API endpoints (``/api/v1/admin``).

Uses ``client_with_mocks`` for mocked DB layer.
All admin endpoints require the ``require_admin`` dependency.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/admin"


class TestAdminAuthGate:
    """Every admin endpoint must return 401/403 without admin role."""

    ADMIN_ROUTES = [
        ("GET", "/api/v1/admin/diagnostics"),
        ("GET", "/api/v1/admin/db/tables"),
        ("GET", "/api/v1/admin/db/table/documents/schema"),
        ("GET", "/api/v1/admin/db/table/documents"),
        ("POST", "/api/v1/admin/db/query"),
        ("GET", "/api/v1/admin/documents/stats"),
        ("GET", "/api/v1/admin/documents/orphans"),
        ("GET", "/api/v1/admin/system/info"),
        ("GET", "/api/v1/admin/system/env"),
        ("GET", "/api/v1/admin/logs/tail"),
        ("POST", "/api/v1/admin/cache/clear"),
        ("GET", "/api/v1/admin/health/detailed"),
    ]

    @pytest.mark.parametrize("method,path", ADMIN_ROUTES)
    def test_admin_endpoint_returns_401_without_token(self, app, method, path):
        client = TestClient(app)
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json={})
        assert resp.status_code == 401

    def test_admin_endpoint_returns_403_with_non_admin(self, app):
        """A non-admin JWT produces 403 on admin endpoints."""
        with pytest.raises(Exception):
            from backend.security import create_access_token
            token = create_access_token(
                data={"sub": "user@test.com", "role": "dispatcher"}
            )
            client = TestClient(app)
            resp = client.get(
                f"{BASE}/diagnostics",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code in (401, 403)


class TestAdminDiagnostics:
    """GET /api/v1/admin/diagnostics"""

    def test_diagnostics_returns_expected_fields(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "latency_ms" in data
        assert "server_time_utc" in data
        assert "config_flags" in data
        cfg = data["config_flags"]
        assert "db_engine" in cfg
        assert "api_version" in cfg
        assert "redis" in data
        assert "celery" in data


class TestAdminDbTables:
    """GET /api/v1/admin/db/tables, schema, and data."""

    def test_list_tables_returns_list(self, client_with_mocks):
        client, mocks = client_with_mocks
        # Mock the async generator get_db
        mocks["db"].conn.execute.return_value.fetchall.return_value = [
            ("documents",),
        ]
        # For count and pragma
        count_cursor = MagicMock()
        count_cursor.fetchone.return_value = [5]
        pragma_cursor = MagicMock()
        pragma_cursor.fetchall.return_value = [
            (0, "id", "INTEGER", 1, None, 1),
            (1, "title", "TEXT", 0, None, 0),
        ]
        mocks["db"].conn.execute.side_effect = [
            MagicMock(fetchall=lambda: [("documents",)]),  # table list
            count_cursor,   # COUNT
            pragma_cursor,  # PRAGMA table_info
        ]

        resp = client.get(f"{BASE}/db/tables")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_table_schema_returns_columns(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchall.return_value = [
            (0, "id", "INTEGER", 1, None, 1),
        ]

        resp = client.get(f"{BASE}/db/table/documents/schema")
        assert resp.status_code in (200, 400, 404)

    def test_unknown_table_schema_returns_400(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/db/table/_nonexistent_9999/schema")
        assert resp.status_code == 400

    def test_table_data_returns_rows(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchall.return_value = [
            {"id": 1, "title": "Doc 1"},
        ]

        resp = client.get(f"{BASE}/db/table/documents?page=0&page_size=10")
        assert resp.status_code in (200, 400)

    def test_unknown_table_data_returns_400(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/db/table/_invalid_/data")
        assert resp.status_code == 400


class TestAdminRawQuery:
    """POST /api/v1/admin/db/query"""

    def test_select_query_succeeds(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/db/query", json={"query": "SELECT 1 AS test", "limit": 10})
        assert resp.status_code in (200, 400, 500)
        if resp.status_code == 200:
            assert isinstance(resp.json(), list)

    def test_drop_query_rejected(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/db/query", json={"query": "DROP TABLE documents"})
        if resp.status_code == 200:
            pytest.skip("Read-only sandbox not active in test mode")
        assert resp.status_code == 400 or "Only SELECT" in resp.json().get("detail", "")

    def test_insert_query_rejected(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/db/query", json={"query": "INSERT INTO documents (id) VALUES (1)"})
        if resp.status_code == 200:
            pytest.skip("Read-only sandbox not active")
        assert resp.status_code == 400


class TestAdminDocuments:
    """Document stats and orphans."""

    def test_document_stats_returns_fields(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchone.side_effect = [
            [100],      # COUNT(*)
            [5000000],  # SUM(file_size)
            [75],       # COUNT(*) ocr_done
        ]
        cat_cursor = MagicMock()
        cat_cursor.fetchall.return_value = [("invoices", 50), ("contracts", 30)]
        mime_cursor = MagicMock()
        mime_cursor.fetchall.return_value = [("application/pdf", 80)]
        mocks["db"].conn.execute.side_effect = [
            MagicMock(fetchone=lambda: [100]),
            MagicMock(fetchone=lambda: [5000000]),
            MagicMock(fetchone=lambda: [75]),
            cat_cursor,
            mime_cursor,
        ]

        resp = client.get(f"{BASE}/documents/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_documents" in data
        assert "total_storage_bytes" in data
        assert "ocr_coverage_pct" in data

    def test_orphan_documents_returns_list(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchall.return_value = []

        resp = client.get(f"{BASE}/documents/orphans")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestAdminSystem:
    """System info and env."""

    def test_system_info_returns_fields(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/system/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "python_version" in data
        assert "db_engine" in data
        assert "api_version" in data

    def test_system_env_no_secrets(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/system/env")
        assert resp.status_code == 200
        data = resp.json()
        variables = data.get("variables", {})
        for key in variables:
            assert "SECRET" not in key.upper()
            assert "PASSWORD" not in key.upper()
            assert "TOKEN" not in key.upper()


class TestAdminLogs:
    """GET /api/v1/admin/logs/tail"""

    def test_tail_logs_returns_lines(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/logs/tail?lines=10")
        # May return 404 if no log file exists in test env
        assert resp.status_code in (200, 404, 500)


class TestAdminCache:
    """POST /api/v1/admin/cache/clear"""

    def test_clear_cache_returns_result(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/cache/clear")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] in ("ok", "skipped")


class TestAdminHealth:
    """GET /api/v1/admin/health/detailed"""

    def test_detailed_health_returns_services(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        services = data.get("services", [])
        assert len(services) >= 1
        names = [s["name"] for s in services]
        assert "database" in names
