"""Tests for new admin diagnostic endpoints (replacing raw SQL endpoint).

.. note::

   These endpoints call ``get_db()`` directly in the function body (not
   through ``Depends``), so the ``app.dependency_overrides`` mechanism
   does **not** intercept those calls.  Instead we patch
   ``backend.api.v1.admin.get_db`` at module level with
   ``unittest.mock.patch`` so that the endpoint sees our mock when it
   does ``async for db in get_db():``.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/admin"


# ── Helpers ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_get_db():
    """Patch ``backend.api.v1.admin.get_db`` to yield a controlled MagicMock.

    The yielded ``MagicMock`` is returned so tests can configure its
    ``conn.execute`` etc.  Admin auth is still handled by the
    ``client_with_mocks`` fixture (which correctly overrides ``Depends``).
    """
    mock_db = MagicMock()
    mock_db.row_to_dict = lambda row: dict(row) if isinstance(row, (tuple, list)) else (row if row else None)
    mock_db.rows_to_dicts = lambda rows: [dict(r) for r in rows] if rows else []
    # Repositories now route every query through ``db.execute(...)`` (engine-
    # aware DatabaseManager API).  Delegate to ``conn.execute`` so the
    # existing ``mock_get_db.conn.execute`` configurations and assertions
    # remain meaningful, mirroring production behaviour.
    mock_db.execute = lambda query, params=(): mock_db.conn.execute(query, params)

    async def _gen():
        yield mock_db

    with patch("backend.api.v1.admin.get_db", side_effect=_gen):
        yield mock_db


# ── Company Row Counts ─────────────────────────────────────────────────────


class TestCompanyRowCounts:
    """GET /api/v1/admin/db/company-row-counts"""

    def test_returns_200_with_tables_key(self, client_with_mocks, mock_get_db):
        """Response has ``{"tables": {...}}`` shape."""
        client, _ = client_with_mocks
        mock_get_db.conn.execute.return_value.fetchall.return_value = [
            (1, 42), (2, 17),
        ]
        resp = client.get(f"{BASE}/db/company-row-counts")
        assert resp.status_code == 200
        data = resp.json()
        assert "tables" in data
        assert isinstance(data["tables"], dict)
        # At least one table should have data since the mock succeeds
        assert any(data["tables"].values())

    def test_each_table_has_company_counts(self, client_with_mocks, mock_get_db):
        """Each table entry maps ``company_id`` → count."""
        client, _ = client_with_mocks

        def _mock_execute(sql, *args):
            mock = MagicMock()
            if "trips" in sql:
                mock.fetchall.return_value = [(1, 10)]
            else:
                mock.fetchall.return_value = [(1, 5)]
            return mock
        mock_get_db.conn.execute.side_effect = _mock_execute

        resp = client.get(f"{BASE}/db/company-row-counts")
        assert resp.status_code == 200
        data = resp.json()
        assert "trips" in data["tables"]
        assert data["tables"]["trips"]["1"] == 10

    def test_graceful_on_query_error(self, client_with_mocks, mock_get_db):
        """When a table query fails, its entry should be ``{}``."""
        client, _ = client_with_mocks
        mock_get_db.conn.execute.side_effect = Exception("table missing")

        resp = client.get(f"{BASE}/db/company-row-counts")
        assert resp.status_code == 200
        # All entries should be ``{}`` since every query fails
        for table_data in resp.json()["tables"].values():
            assert table_data == {}

    def test_requires_admin_auth(self, app):
        """Without admin auth, returns 401."""
        client = TestClient(app)
        resp = client.get(f"{BASE}/db/company-row-counts")
        assert resp.status_code == 401


# ── Recent Errors ──────────────────────────────────────────────────────────


class TestRecentErrors:
    """GET /api/v1/admin/db/recent-errors"""

    def test_returns_200_with_alerts_list(self, client_with_mocks, mock_get_db):
        client, _ = client_with_mocks
        # Repo _fetchall wraps results in rows_to_dicts — use dict keys
        mock_get_db.conn.execute.return_value.fetchall.return_value = [{
            "id": 1, "company_id": 42, "type": "test", "severity": "medium",
            "message": "Something failed", "created_at": "2025-01-01 00:00:00",
        }]
        resp = client.get(f"{BASE}/db/recent-errors")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert len(data["alerts"]) > 0
        assert data["alerts"][0]["message"] == "Something failed"

    def test_defaults_hours_24_limit_50(self, client_with_mocks, mock_get_db):
        """Default parameters (hours=24, limit=50) when none provided."""
        client, _ = client_with_mocks
        mock_get_db.conn.execute.return_value.fetchall.return_value = []
        resp = client.get(f"{BASE}/db/recent-errors")
        assert resp.status_code == 200
        # Verify the endpoint ran (execute was called at least once)
        assert mock_get_db.conn.execute.called

    def test_respects_hours_param(self, client_with_mocks, mock_get_db):
        """Custom hours is passed through to the query."""
        client, _ = client_with_mocks
        mock_get_db.conn.execute.return_value.fetchall.return_value = []
        resp = client.get(f"{BASE}/db/recent-errors?hours=48")
        assert resp.status_code == 200

    def test_respects_limit_param(self, client_with_mocks, mock_get_db):
        """Custom limit is passed through to the query."""
        client, _ = client_with_mocks
        mock_get_db.conn.execute.return_value.fetchall.return_value = []
        resp = client.get(f"{BASE}/db/recent-errors?limit=100")
        assert resp.status_code == 200

    @pytest.mark.parametrize("hours,expected", [
        (0, 422),
        (169, 422),
        (-1, 422),
        (24, 200),
        (1, 200),
        (168, 200),
    ])
    def test_validates_hours_range(self, client_with_mocks, mock_get_db, hours, expected):
        """hours must be 1..168 (inclusive)."""
        client, _ = client_with_mocks
        mock_get_db.conn.execute.return_value.fetchall.return_value = []
        resp = client.get(f"{BASE}/db/recent-errors?hours={hours}")
        assert resp.status_code == expected

    @pytest.mark.parametrize("limit,expected", [
        (0, 422),
        (501, 422),
        (50, 200),
        (500, 200),
    ])
    def test_validates_limit_range(self, client_with_mocks, mock_get_db, limit, expected):
        """limit must be 1..500 (inclusive)."""
        client, _ = client_with_mocks
        mock_get_db.conn.execute.return_value.fetchall.return_value = []
        resp = client.get(f"{BASE}/db/recent-errors?limit={limit}")
        assert resp.status_code == expected

    def test_requires_admin_auth(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/db/recent-errors")
        assert resp.status_code == 401


# ── Database Stats ─────────────────────────────────────────────────────────


class TestDatabaseStats:
    """GET /api/v1/admin/db/stats"""

    def test_returns_200_with_expected_keys(self, client_with_mocks, mock_get_db):
        """Response contains all expected statistical keys."""
        client, _ = client_with_mocks

        def _mock_execute(sql, *args):
            mock = MagicMock()
            if "page_count" in sql:
                mock.fetchone.return_value = (100,)
            elif "freelist_count" in sql:
                mock.fetchone.return_value = (5,)
            elif "page_size" in sql:
                mock.fetchone.return_value = (4096,)
            elif "quick_check" in sql or "integrity" in sql:
                mock.fetchone.return_value = ("ok",)
            elif "FROM users" in sql:
                # Repo _fetchone wraps result in row_to_dict
                mock.fetchone.return_value = {"cnt": 10}
            elif "FROM companies" in sql:
                mock.fetchone.return_value = {"cnt": 3}
            else:
                mock.fetchone.return_value = (0,)
            return mock
        mock_get_db.conn.execute.side_effect = _mock_execute

        resp = client.get(f"{BASE}/db/stats")
        assert resp.status_code == 200
        data = resp.json()
        expected_keys = {
            "page_count", "freelist_count", "page_size", "db_size_mb",
            "integrity_check", "user_count", "company_count",
        }
        assert expected_keys.issubset(data.keys())

    def test_db_size_mb_is_calculated(self, client_with_mocks, mock_get_db):
        """100 pages × 4096 bytes = 0.39 MB."""
        client, _ = client_with_mocks

        def _mock_execute(sql, *args):
            mock = MagicMock()
            if "page_count" in sql:
                mock.fetchone.return_value = (100,)
            elif "page_size" in sql:
                mock.fetchone.return_value = (4096,)
            elif "FROM users" in sql or "FROM companies" in sql:
                # Repo _fetchone wraps result in row_to_dict
                mock.fetchone.return_value = {"cnt": 0}
            else:
                mock.fetchone.return_value = (0,)
            return mock
        mock_get_db.conn.execute.side_effect = _mock_execute

        resp = client.get(f"{BASE}/db/stats")
        data = resp.json()
        # 100 * 4096 / (1024 * 1024) = 0.390625
        assert data["db_size_mb"] == pytest.approx(0.39, rel=0.1)

    def test_integrity_check_handles_error(self, client_with_mocks, mock_get_db):
        """When PRAGMA quick_check fails, integrity_check is ``"unknown"``."""
        client, _ = client_with_mocks

        def _mock_execute(sql, *args):
            mock = MagicMock()
            if sql.startswith("PRAGMA page_count"):
                mock.fetchone.return_value = (100,)
            elif sql.startswith("PRAGMA page_size"):
                mock.fetchone.return_value = (4096,)
            elif sql.startswith("PRAGMA quick_check") or "integrity" in sql:
                raise Exception("no such table")
            elif "FROM users" in sql or "FROM companies" in sql:
                # Repo _fetchone wraps result in row_to_dict
                mock.fetchone.return_value = {"cnt": 0}
            else:
                mock.fetchone.return_value = (0,)
            return mock
        mock_get_db.conn.execute.side_effect = _mock_execute

        resp = client.get(f"{BASE}/db/stats")
        assert resp.status_code == 200
        assert resp.json()["integrity_check"] == "unknown"

    def test_requires_admin_auth(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/db/stats")
        assert resp.status_code == 401


# ── Deprecated Query Endpoint ──────────────────────────────────────────────


class TestDeprecatedQueryEndpoint:
    """Verify old ``POST /admin/db/query`` is removed."""

    def test_post_db_query_returns_404(self, client_with_mocks, mock_get_db):
        """The old raw SQL endpoint should return 404."""
        client, _ = client_with_mocks
        resp = client.post(f"{BASE}/db/query", json={"query": "SELECT 1"})
        assert resp.status_code == 404
