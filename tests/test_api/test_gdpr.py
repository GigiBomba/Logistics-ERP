"""Comprehensive unit tests for GDPR compliance API endpoints.

Routes tested (all under /api/v1/gdpr):
  - POST /export/company/{company_id}   — export all company data as JSON
  - POST /export/user/{user_id}         — export user data (strips password_hash)
  - POST /delete/company/{company_id}   — soft-delete all company data (?confirm=DELETE)
  - POST /delete/user/{user_id}         — deactivate user
  - GET  /data-inventory                — static data inventory

All endpoints require admin auth (mocked via dependency override).
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.v1.gdpr import _row_to_dict, EXPORT_TABLES

BASE = "/api/v1/gdpr"


# ── Helpers ───────────────────────────────────────────────────────────


def _mock_row(keys_values: dict) -> MagicMock:
    """Build a mock sqlite3.Row from a plain dict."""
    row = MagicMock()
    row.keys.return_value = list(keys_values.keys())
    row.__getitem__ = lambda self, k: keys_values[k]
    return row


def _make_db(**conn_attrs) -> MagicMock:
    """Create a bare MagicMock DatabaseManager with a conn attached."""
    mock_db = MagicMock()
    mock_conn = MagicMock(**conn_attrs)
    type(mock_db).conn = PropertyMock(return_value=mock_conn)
    # Wire db.execute() → db.conn.execute() so production code works via either path
    mock_db.execute = MagicMock(side_effect=lambda q, p=None: mock_conn.execute(q, p))
    # Wire db.commit() → db.conn.commit()
    mock_db.commit = MagicMock(side_effect=lambda: mock_conn.commit())
    # Fake engine so repository code does not try to adapt queries
    mock_db._engine = "sqlite"
    return mock_db


def _override_deps(app, mock_db, mock_user=None):
    """Override ``get_db`` and ``require_admin`` on *app*.

    Returns a ``TestClient`` ready to make requests.
    Caller **must** call ``app.dependency_overrides.clear()`` after the test.
    """
    from backend.dependencies import get_db
    from backend.dependencies_security import require_admin

    if mock_user is None:
        mock_user = {
            "id": 1,
            "email": "admin@test.com",
            "role": "admin",
            "is_admin": True,
            "company_id": 1,
        }
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_admin] = lambda: mock_user
    return TestClient(app)


def _eval_pragma_table(sql: str) -> str | None:
    """Extract table name from ``PRAGMA table_info(<table>)`` or return None."""
    if sql.startswith("PRAGMA table_info("):
        return sql[len("PRAGMA table_info("):].rstrip(")")
    return None


# ═══════════════════════════════════════════════════════════════════════
#  POST /export/company/{company_id}
# ═══════════════════════════════════════════════════════════════════════


class TestExportCompany:
    """POST /api/v1/gdpr/export/company/{company_id}"""

    # -- helpers -------------------------------------------------------

    @staticmethod
    def _make_db_with_data(
        rows_per_table: int = 2,
        tables_without_company_id: set[str] | None = None,
        error_tables: dict[str, str] | None = None,
        user_row: dict | None = None,
    ) -> MagicMock:
        """Build a mock DB that returns controlled data for all EXPORT_TABLES.

        Parameters
        ----------
        rows_per_table:
            How many rows each table returns (0 = empty).
        tables_without_company_id:
            Tables whose PRAGMA does *not* include a company_id column.
        error_tables:
            Mapping of table name → error message: those tables raise during PRAGMA.
        """
        if tables_without_company_id is None:
            tables_without_company_id = set()
        if error_tables is None:
            error_tables = {}

        mock_db = _make_db()
        mock_conn = mock_db.conn

        def execute_side_effect(sql, params=None):
            result = MagicMock()

            # -- PRAGMA table_info ------------------------------------
            table = _eval_pragma_table(sql)
            if table is not None:
                if table in error_tables:
                    raise RuntimeError(error_tables[table])

                if table in tables_without_company_id:
                    result.fetchall.return_value = [(0, "id", "INTEGER")]
                else:
                    result.fetchall.return_value = [
                        (0, "id", "INTEGER"),
                        (1, "company_id", "INTEGER"),
                        (2, "name", "TEXT"),
                    ]
                return result

            # -- SELECT -----------------------------------------------
            if sql.startswith("SELECT"):
                table_for_select = None
                # Crude but sufficient: extract table name from SELECT
                for candidate in EXPORT_TABLES:
                    if f"FROM {candidate}" in sql:
                        table_for_select = candidate
                        break

                # If the table had no company_id, the route never issues SELECT
                result.fetchall.return_value = [
                    _mock_row({"id": i, "company_id": params[0] if params else 1, "name": f"row-{i}"})
                    for i in range(rows_per_table)
                ]
                return result

            # -- UPDATE / DELETE (fallback) ---------------------------
            result.rowcount = rows_per_table
            return result

        mock_conn.execute.side_effect = execute_side_effect
        return mock_db

    # -- tests ---------------------------------------------------------

    def test_success_returns_json_file(self, app):
        """Happy path — returns 200 with ``application/json`` and all expected keys."""
        mock_db = self._make_db_with_data(rows_per_table=3)
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/company/1")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"

        data = resp.json()
        assert data["company_id"] == 1
        assert "exported_at" in data
        assert data["total_records"] == len(EXPORT_TABLES) * 3
        assert set(data["tables"].keys()) == set(EXPORT_TABLES)

        # Every table was read — each has count=3 and 3 records
        for t in EXPORT_TABLES:
            tbl = data["tables"][t]
            assert tbl["count"] == 3, f"table {t!r} expected count=3, got {tbl['count']}"
            assert len(tbl["records"]) == 3
            assert "error" not in tbl, f"table {t!r} should have no error"

        app.dependency_overrides.clear()

    def test_tables_without_company_id_are_empty(self, app):
        """Tables whose schema lacks ``company_id`` are included with count=0."""
        omitted = {"trips", "invoices", "drivers"}
        mock_db = self._make_db_with_data(
            rows_per_table=2, tables_without_company_id=omitted
        )
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/company/1")
        assert resp.status_code == 200
        data = resp.json()

        for t in omitted:
            tbl = data["tables"][t]
            assert tbl["count"] == 0, f"{t!r} should be empty"
            assert tbl["records"] == []

        # Other tables still have data
        for t in set(EXPORT_TABLES) - omitted:
            assert data["tables"][t]["count"] == 2

        app.dependency_overrides.clear()

    def test_table_read_error_is_captured(self, app):
        """When a table raises during read, the error message appears in the response."""
        mock_db = self._make_db_with_data(
            rows_per_table=2,
            error_tables={"trips": "disk full"},
        )
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/company/1")
        assert resp.status_code == 200
        data = resp.json()

        # trips entry contains the error
        assert "error" in data["tables"]["trips"]
        assert "disk full" in data["tables"]["trips"]["error"]

        # Other tables are unaffected
        for t in set(EXPORT_TABLES) - {"trips"}:
            assert "error" not in data["tables"][t]
            assert data["tables"][t]["count"] == 2

        app.dependency_overrides.clear()

    def test_table_read_error_in_select(self, app):
        """A table whose PRAGMA succeeds but SELECT fails is handled."""
        mock_db = _make_db()
        mock_conn = mock_db.conn

        call_count = 0

        def execute_side_effect(sql, params=None):
            nonlocal call_count
            result = MagicMock()

            if sql.startswith("PRAGMA table_info("):
                # All tables have company_id
                result.fetchall.return_value = [
                    (0, "id", "INTEGER"),
                    (1, "company_id", "INTEGER"),
                ]
                return result

            if sql.startswith("SELECT"):
                call_count += 1
                if call_count == 1:  # First SELECT -> trips
                    raise RuntimeError("SELECT failed on trips")
                result.fetchall.return_value = [
                    _mock_row({"id": 1, "company_id": 1, "name": "ok"})
                ]
                return result

            result.rowcount = 1
            return result

        mock_conn.execute.side_effect = execute_side_effect
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/company/1")
        assert resp.status_code == 200
        data = resp.json()

        assert "error" in data["tables"]["trips"]
        assert "SELECT failed on trips" in data["tables"]["trips"]["error"]

        app.dependency_overrides.clear()

    def test_empty_database_all_tables_empty(self, app):
        """When every table returns zero rows, total_records = 0."""
        mock_db = self._make_db_with_data(rows_per_table=0)
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/company/1")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_records"] == 0
        for t in EXPORT_TABLES:
            assert data["tables"][t]["count"] == 0
            assert data["tables"][t]["records"] == []

        app.dependency_overrides.clear()

    def test_total_records_matches_sum_of_counts(self, app):
        """``total_records`` equals the sum of all per-table counts."""
        mock_db = self._make_db_with_data(rows_per_table=5)
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/company/1")
        assert resp.status_code == 200
        data = resp.json()

        expected = sum(tbl["count"] for tbl in data["tables"].values())
        assert data["total_records"] == expected
        assert data["total_records"] == len(EXPORT_TABLES) * 5

        app.dependency_overrides.clear()

    def test_exported_at_is_iso_format(self, app):
        """The ``exported_at`` timestamp is in ISO-8601 format."""
        from datetime import datetime

        mock_db = self._make_db_with_data(rows_per_table=1)
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/company/1")
        data = resp.json()

        # Should parse without error
        dt = datetime.fromisoformat(data["exported_at"])
        assert dt is not None

        app.dependency_overrides.clear()

    def test_invalid_company_id_negative(self, app):
        """A negative company_id is passed through to the database."""
        mock_db = self._make_db_with_data(rows_per_table=0)
        mock_conn = mock_db.conn
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/company/-1")
        # 200 because the route does not validate — the DB would return 0 rows
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_id"] == -1

        # Verify the SQL parameter was passed through
        select_calls = [
            c for c in mock_conn.execute.call_args_list
            if c[0][0].startswith("SELECT")
        ]
        if select_calls:
            _, kwargs = select_calls[0]
            assert kwargs.get("params") == (-1,) or (
                len(select_calls[0][0]) > 1
                and select_calls[0][0][1] == (-1,)
            )

        app.dependency_overrides.clear()

    def test_content_disposition_filename(self, app):
        """Response includes a meaningful ``Content-Disposition`` header."""
        mock_db = self._make_db_with_data(rows_per_table=1)
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/company/42")
        assert resp.status_code == 200

        cd = resp.headers.get("content-disposition", "")
        assert "operion_gdpr_export_company_42" in cd
        # filename value is wrapped in quotes: attachment; filename="...json"
        assert "filename=" in cd
        filename_part = cd.split("filename=")[-1].strip('"')
        assert filename_part.endswith(".json")

        app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════
#  POST /export/user/{user_id}
# ═══════════════════════════════════════════════════════════════════════


class TestExportUser:
    """POST /api/v1/gdpr/export/user/{user_id}"""

    def test_success_strips_password_hash(self, app):
        """User export returns all user fields except ``password_hash``."""
        mock_db = _make_db()
        mock_conn = mock_db.conn

        user_row = _mock_row({
            "id": 1,
            "email": "user@example.com",
            "password_hash": "super-secret",
            "company_id": 5,
            "role": "driver",
            "is_active": 1,
        })
        mock_conn.execute.return_value.fetchone.return_value = user_row

        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/user/1")
        assert resp.status_code == 200
        data = resp.json()

        assert "exported_at" in data
        assert data["company_id"] == 5
        assert data["user"]["id"] == 1
        assert data["user"]["email"] == "user@example.com"
        assert "password_hash" not in data["user"]

        app.dependency_overrides.clear()

    def test_user_not_found_returns_404(self, app):
        """When user does not exist the endpoint returns 404."""
        mock_db = _make_db()
        mock_conn = mock_db.conn
        mock_conn.execute.return_value.fetchone.return_value = None

        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/user/999")
        assert resp.status_code == 404
        detail = resp.json()
        # FastAPI 422 / standard error shape
        assert "detail" in detail

        app.dependency_overrides.clear()

    def test_user_has_no_company_id(self, app):
        """Export works for users with ``company_id = None``."""
        mock_db = _make_db()
        mock_conn = mock_db.conn

        user_row = _mock_row({
            "id": 2,
            "email": "orphan@example.com",
            "password_hash": "abc",
            "company_id": None,
            "role": "viewer",
        })
        mock_conn.execute.return_value.fetchone.return_value = user_row

        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/user/2")
        assert resp.status_code == 200
        data = resp.json()

        assert data["user"]["company_id"] is None
        assert data["company_id"] is None
        assert "password_hash" not in data["user"]

        app.dependency_overrides.clear()

    def test_user_without_company_id_field(self, app):
        """If the row lacks a ``company_id`` key, fallback to None."""
        mock_db = _make_db()
        mock_conn = mock_db.conn

        user_row = _mock_row({
            "id": 3,
            "email": "nocompany@example.com",
            "password_hash": "xyz",
        })
        mock_conn.execute.return_value.fetchone.return_value = user_row

        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/user/3")
        assert resp.status_code == 200
        data = resp.json()

        assert data["company_id"] is None

        app.dependency_overrides.clear()

    def test_export_filename_contains_user_id(self, app):
        """The ``Content-Disposition`` filename includes the user id."""
        mock_db = _make_db()
        mock_conn = mock_db.conn
        mock_conn.execute.return_value.fetchone.return_value = _mock_row({
            "id": 7, "email": "a@b.com", "password_hash": "x", "company_id": 1,
        })

        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/export/user/7")
        cd = resp.headers.get("content-disposition", "")
        assert "gdpr_export_user_7" in cd

        app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════
#  POST /delete/company/{company_id}
# ═══════════════════════════════════════════════════════════════════════


class TestDeleteCompany:
    """POST /api/v1/gdpr/delete/company/{company_id}"""

    # -- helpers -------------------------------------------------------

    @staticmethod
    def _make_db_for_delete(
        tables_with_is_active: set[str] | None = None,
        tables_without_company_id: set[str] | None = None,
        error_tables: dict[str, str] | None = None,
    ) -> MagicMock:
        """Build a mock DB suitable for delete-company tests.

        *tables_with_is_active* — tables whose PRAGMA includes ``is_active``.
        """
        if tables_with_is_active is None:
            tables_with_is_active = set()
        if tables_without_company_id is None:
            tables_without_company_id = set()
        if error_tables is None:
            error_tables = {}

        mock_db = _make_db()
        mock_conn = mock_db.conn

        def execute_side_effect(sql, params=None):
            result = MagicMock()

            table = _eval_pragma_table(sql)
            if table is not None:
                if table in error_tables:
                    raise RuntimeError(error_tables[table])

                cols = [(0, "id", "INTEGER")]
                if table not in tables_without_company_id:
                    cols.append((1, "company_id", "INTEGER"))
                if table in tables_with_is_active:
                    cols.append((2, "is_active", "INTEGER"))
                result.fetchall.return_value = cols
                return result

            # UPDATE / DELETE
            result.rowcount = 5
            return result

        mock_conn.execute.side_effect = execute_side_effect
        return mock_db

    # -- tests ---------------------------------------------------------

    def test_requires_confirm_param(self, app):
        """Calling without ``?confirm=DELETE`` returns 400."""
        mock_db = self._make_db_for_delete()
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/delete/company/1")
        assert resp.status_code == 400
        assert "confirm" in resp.json()["detail"].lower() or "DELETE" in resp.json()["detail"]

        app.dependency_overrides.clear()

    def test_wrong_confirm_value_returns_400(self, app):
        """Calling with ``?confirm=something-else`` returns 400."""
        mock_db = self._make_db_for_delete()
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/delete/company/1?confirm=YES")
        assert resp.status_code == 400

        app.dependency_overrides.clear()

    def test_success_soft_deletes_all_tables(self, app):
        """With ``?confirm=DELETE`` all tables are soft-deleted, companies updated, audit logged."""
        mock_db = self._make_db_for_delete(
            tables_with_is_active=set(EXPORT_TABLES),
        )
        mock_conn = mock_db.conn
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/delete/company/1?confirm=DELETE")
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "completed"
        assert data["company_id"] == 1
        assert "tables_affected" in data

        # Every table was updated (soft-delete via UPDATE)
        for t in EXPORT_TABLES:
            assert t in data["tables_affected"]
            # rowcount = 5 from our mock
            assert data["tables_affected"][t] == 5

        # Companies table was updated
        update_company_calls = [
            c for c in mock_conn.execute.call_args_list
            if "UPDATE companies" in c[0][0]
        ]
        assert len(update_company_calls) == 1

        # Commit was called
        assert mock_conn.commit.called

        app.dependency_overrides.clear()

    def test_table_without_is_active_gets_delete(self, app):
        """Tables that lack an ``is_active`` column are hard-deleted (DELETE FROM)."""
        tables_with_active = {"trips", "invoices"}
        mock_db = self._make_db_for_delete(tables_with_is_active=tables_with_active)
        mock_conn = mock_db.conn
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/delete/company/1?confirm=DELETE")
        assert resp.status_code == 200
        data = resp.json()

        # Collect which SQL statements were issued, keyed by table name.
        # Use precise SQL-prefix matching so that names like "route_history"
        # don't falsely match "route_history_v2".
        issued: dict[str, str] = {}  # table -> SQL type ("UPDATE" | "DELETE")
        for call_args in mock_conn.execute.call_args_list:
            sql = call_args[0][0]
            if "companies" in sql and "UPDATE" in sql:
                continue  # the companies UPDATE is separate
            for t in EXPORT_TABLES:
                # UPDATE  → "UPDATE {table} SET is_active = 0 WHERE company_id = ?"
                # DELETE  → "DELETE FROM {table} WHERE company_id = ?"
                if sql == f"UPDATE {t} SET is_active = 0 WHERE company_id = ?":
                    issued[t] = "UPDATE"
                    break
                if sql == f"DELETE FROM {t} WHERE company_id = ?":
                    issued[t] = "DELETE"
                    break

        # Tables with is_active were UPDATEd
        for t in tables_with_active:
            assert issued.get(t) == "UPDATE", f"{t!r} expected UPDATE, got {issued.get(t)}"

        # Tables without is_active were DELETEd
        for t in set(EXPORT_TABLES) - tables_with_active:
            assert issued.get(t) == "DELETE", f"{t!r} expected DELETE, got {issued.get(t)}"

        app.dependency_overrides.clear()

    def test_table_error_handled_gracefully(self, app):
        """When a table operation fails, it's captured in the response."""
        mock_db = self._make_db_for_delete(
            tables_with_is_active=set(EXPORT_TABLES),
            error_tables={"trips": "permission denied"},
        )
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/delete/company/1?confirm=DELETE")
        assert resp.status_code == 200
        data = resp.json()

        assert "error: permission denied" in str(data["tables_affected"]["trips"])

        # Other tables still succeeded
        for t in set(EXPORT_TABLES) - {"trips"}:
            assert isinstance(data["tables_affected"][t], int)

        app.dependency_overrides.clear()

    def test_table_update_error_handled(self, app):
        """When UPDATE/DELETE itself raises, it's captured."""
        mock_db = _make_db()
        mock_conn = mock_db.conn

        def execute_side_effect(sql, params=None):
            result = MagicMock()
            table = _eval_pragma_table(sql)
            if table is not None:
                # All tables have company_id and is_active
                result.fetchall.return_value = [
                    (0, "id", "INTEGER"),
                    (1, "company_id", "INTEGER"),
                    (2, "is_active", "INTEGER"),
                ]
                return result
            if "trips" in sql:
                raise RuntimeError("UPDATE failed on trips")
            result.rowcount = 3
            return result

        mock_conn.execute.side_effect = execute_side_effect
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/delete/company/1?confirm=DELETE")
        assert resp.status_code == 200
        data = resp.json()

        assert "error: UPDATE failed on trips" in str(data["tables_affected"]["trips"])

        app.dependency_overrides.clear()

    def test_audit_log_called(self, app):
        """AuditRepository.log_event is invoked during a successful deletion."""
        mock_db = self._make_db_for_delete(
            tables_with_is_active=set(EXPORT_TABLES),
        )

        # Patch at the definition site — AuditRepository is imported *inside*
        # the delete_company_data function body.
        with patch("backend.repositories.audit_repository.AuditRepository") as mock_audit_cls:
            mock_audit_instance = MagicMock()
            mock_audit_cls.return_value = mock_audit_instance

            client = _override_deps(app, mock_db)
            resp = client.post(f"{BASE}/delete/company/1?confirm=DELETE")

            assert resp.status_code == 200

            # AuditRepository was instantiated with the db
            mock_audit_cls.assert_called_once_with(mock_db)

            # log_event was called with expected arguments
            mock_audit_instance.log_event.assert_called_once()
            call_kwargs = mock_audit_instance.log_event.call_args[1]
            assert call_kwargs["event_type"] == "gdpr.deletion"
            assert call_kwargs["entity_type"] == "company"
            assert call_kwargs["entity_id"] == "1"
            assert call_kwargs["company_id"] == 1
            assert "trips" in call_kwargs["data"]["tables_affected"]

        app.dependency_overrides.clear()

    def test_audit_failure_does_not_break_response(self, app):
        """If audit logging fails, the endpoint still returns 200."""
        mock_db = self._make_db_for_delete(
            tables_with_is_active=set(EXPORT_TABLES),
        )

        with patch("backend.repositories.audit_repository.AuditRepository") as mock_audit_cls:
            mock_audit_cls.side_effect = RuntimeError("audit fail")

            client = _override_deps(app, mock_db)
            resp = client.post(f"{BASE}/delete/company/1?confirm=DELETE")

            assert resp.status_code == 200
            assert resp.json()["status"] == "completed"

        app.dependency_overrides.clear()

    def test_table_without_company_id_skipped(self, app):
        """Tables whose schema lacks ``company_id`` are not modified."""
        skipped = {"trips", "invoices"}
        mock_db = self._make_db_for_delete(
            tables_with_is_active=set(EXPORT_TABLES),
            tables_without_company_id=skipped,
        )
        mock_conn = mock_db.conn
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/delete/company/1?confirm=DELETE")
        assert resp.status_code == 200

        # Tables without company_id should not have UPDATE/DELETE calls.
        # Use exact SQL comparison to avoid prefix collisions.
        update_template = "UPDATE {t} SET is_active = 0 WHERE company_id = ?"
        delete_template = "DELETE FROM {t} WHERE company_id = ?"
        for call_args in mock_conn.execute.call_args_list:
            sql = call_args[0][0]
            if sql.startswith("PRAGMA"):
                continue
            for t in skipped:
                if sql == update_template.format(t=t) or sql == delete_template.format(t=t):
                    pytest.fail(f"{t!r} should not have been modified, but got: {sql}")

        app.dependency_overrides.clear()

    def test_response_note_included(self, app):
        """Response includes a note about soft-deletion."""
        mock_db = self._make_db_for_delete(tables_with_is_active=set(EXPORT_TABLES))
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/delete/company/1?confirm=DELETE")
        data = resp.json()

        assert "note" in data
        assert "soft delete" in data["note"].lower()

        app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════
#  POST /delete/user/{user_id}
# ═══════════════════════════════════════════════════════════════════════


class TestDeleteUser:
    """POST /api/v1/gdpr/delete/user/{user_id}"""

    def test_success_deactivates_user(self, app):
        """User is deactivated (``is_active = 0``) and response confirms."""
        mock_db = _make_db()
        mock_conn = mock_db.conn
        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/delete/user/7")
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "deactivated"
        assert data["user_id"] == 7
        assert "note" in data

        # Verify UPDATE was issued
        update_calls = [
            c for c in mock_conn.execute.call_args_list
            if "UPDATE users" in c[0][0]
        ]
        assert len(update_calls) == 1
        sql, params = update_calls[0][0]
        assert "is_active = 0" in sql
        assert params == (7,)

        # Commit was called
        assert mock_conn.commit.called

        app.dependency_overrides.clear()

    def test_deactivate_nonexistent_user(self, app):
        """The endpoint does not validate user existence — it just runs UPDATE."""
        mock_db = _make_db()
        mock_conn = mock_db.conn
        # Even if no rows are affected, the route returns 200
        mock_conn.execute.return_value.rowcount = 0

        client = _override_deps(app, mock_db)

        resp = client.post(f"{BASE}/delete/user/99999")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deactivated"

        app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════
#  GET /data-inventory
# ═══════════════════════════════════════════════════════════════════════


class TestDataInventory:
    """GET /api/v1/gdpr/data-inventory"""

    def test_returns_static_structure(self, app):
        """The endpoint returns a static dict with the three expected root keys."""
        mock_db = _make_db()
        client = _override_deps(app, mock_db)

        resp = client.get(f"{BASE}/data-inventory")
        assert resp.status_code == 200
        data = resp.json()

        assert "data_categories" in data
        assert "data_subject_rights" in data
        assert "processing_purposes" in data

        app.dependency_overrides.clear()

    def test_data_categories_has_expected_keys(self, app):
        """Each category has *category*, *tables*, and *retention* fields."""
        mock_db = _make_db()
        client = _override_deps(app, mock_db)

        resp = client.get(f"{BASE}/data-inventory")
        data = resp.json()

        for cat in data["data_categories"]:
            assert "category" in cat
            assert "tables" in cat
            assert "retention" in cat
            assert isinstance(cat["tables"], list)
            assert len(cat["tables"]) > 0

        app.dependency_overrides.clear()

    def test_data_subject_rights_non_empty(self, app):
        """The rights list contains at least one right."""
        mock_db = _make_db()
        client = _override_deps(app, mock_db)

        resp = client.get(f"{BASE}/data-inventory")
        rights = resp.json()["data_subject_rights"]
        assert len(rights) >= 1
        assert any("export" in r.lower() for r in rights)

        app.dependency_overrides.clear()

    def test_processing_purposes_non_empty(self, app):
        """The purposes list contains at least one purpose."""
        mock_db = _make_db()
        client = _override_deps(app, mock_db)

        resp = client.get(f"{BASE}/data-inventory")
        purposes = resp.json()["processing_purposes"]
        assert len(purposes) >= 1
        assert any("transport" in p.lower() for p in purposes)

        app.dependency_overrides.clear()

    def test_inventory_is_idempotent(self, app):
        """Calling the endpoint twice returns identical results."""
        mock_db = _make_db()
        client = _override_deps(app, mock_db)

        resp1 = client.get(f"{BASE}/data-inventory")
        resp2 = client.get(f"{BASE}/data-inventory")
        assert resp1.json() == resp2.json()

        app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════
#  _row_to_dict helper
# ═══════════════════════════════════════════════════════════════════════


class TestRowToDict:
    """``_row_to_dict`` helper function."""

    def test_none_returns_empty_dict(self):
        """``None`` input produces an empty dict."""
        assert _row_to_dict(None) == {}

    def test_mock_row_converts_to_dict(self):
        """A mock row with known keys becomes a plain dict."""
        row = _mock_row({"id": 1, "name": "test", "company_id": 42})
        result = _row_to_dict(row)
        assert result == {"id": 1, "name": "test", "company_id": 42}

    def test_empty_row_returns_empty_dict(self):
        """A row with no keys returns an empty dict."""
        row = _mock_row({})
        assert _row_to_dict(row) == {}

    def test_row_with_none_values(self):
        """A row containing ``None`` values preserves them."""
        row = _mock_row({"id": 1, "deleted_at": None, "note": None})
        result = _row_to_dict(row)
        assert result["id"] == 1
        assert result["deleted_at"] is None
        assert result["note"] is None

    def test_row_with_various_types(self):
        """A row with mixed types is handled correctly."""
        row = _mock_row({
            "id": 1,
            "price": 19.99,
            "is_active": True,
            "tags": ["a", "b"],
            "metadata": {"key": "val"},
        })
        result = _row_to_dict(row)
        assert result["id"] == 1
        assert result["price"] == 19.99
        assert result["is_active"] is True
        assert result["tags"] == ["a", "b"]
        assert result["metadata"] == {"key": "val"}

    def test_keys_method_called(self, app):
        """The function calls ``.keys()`` on the row object."""
        row = MagicMock()
        row.keys.return_value = ["x"]
        row.__getitem__ = lambda self, k: 42

        result = _row_to_dict(row)
        assert result == {"x": 42}
        row.keys.assert_called_once()
