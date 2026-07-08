"""Tests for DatabaseManager — CRUD, connection handling, error handling, read-only connections."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import warnings

import pytest

from database.db_manager import DatabaseManager


# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
def db_path():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    yield tmp.name
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def db(db_path):
    _db = DatabaseManager(db_path)
    yield _db
    try:
        _db.close()
    except Exception:
        pass


# ── Init & Connection ───────────────────────────────────────────────────────


class TestInit:
    def test_init_sqlite_default(self, db_path):
        """DatabaseManager defaults to SQLite engine."""
        dm = DatabaseManager(db_path)
        assert dm._engine == "sqlite"
        assert dm.conn is not None
        dm.close()

    def test_init_creates_tables(self, db):
        tables = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for required in ("trips", "trucks", "drivers", "clients", "invoices", "settings"):
            assert required in tables, f"Missing table: {required}"

    def test_init_creates_indexes(self, db):
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_trips_status" in indexes

    def test_init_idempotent(self, db_path):
        """Opening twice on same path does not raise."""
        dm1 = DatabaseManager(db_path)
        dm1.close()
        dm2 = DatabaseManager(db_path)
        dm2.close()

    def test_engine_from_env(self, db_path, monkeypatch):
        monkeypatch.setenv("OPERION_DB_ENGINE", "sqlite")
        dm = DatabaseManager(db_path)
        assert dm._engine == "sqlite"
        dm.close()


# ── Settings API ─────────────────────────────────────────────────────────────


class TestSettings:
    def test_save_and_get_setting(self, db):
        db.save_setting("theme", "dark")
        assert db.get_setting("theme") == "dark"

    def test_get_setting_missing(self, db):
        assert db.get_setting("nonexistent") is None

    def test_get_settings_bulk(self, db):
        db.save_setting("a", "1")
        db.save_setting("b", "2")
        result = db.get_settings(["a", "b"])
        assert result == {"a": "1", "b": "2"}

    def test_save_setting_overwrites(self, db):
        db.save_setting("key", "old")
        db.save_setting("key", "new")
        assert db.get_setting("key") == "new"

    def test_settings_persist_across_reopen(self, db_path):
        dm1 = DatabaseManager(db_path)
        dm1.save_setting("persist", "yes")
        dm1.close()
        dm2 = DatabaseManager(db_path)
        assert dm2.get_setting("persist") == "yes"
        dm2.close()


# ── Row / Dict helpers ────────────────────────────────────────────────────────


class TestRowConversion:
    def test_row_to_dict_none(self):
        assert DatabaseManager.row_to_dict(None) is None

    def test_row_to_dict(self, db):
        db.conn.execute("INSERT INTO settings (key, value) VALUES ('k', 'v')")
        row = db.conn.execute("SELECT key, value FROM settings WHERE key='k'").fetchone()
        d = DatabaseManager.row_to_dict(row)
        assert d == {"key": "k", "value": "v"}

    def test_rows_to_dicts_empty(self):
        assert DatabaseManager.rows_to_dicts(None) == []
        assert DatabaseManager.rows_to_dicts([]) == []

    def test_rows_to_dicts(self, db):
        db.save_setting("x", "1")
        db.save_setting("y", "2")
        rows = db.conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
        dicts = DatabaseManager.rows_to_dicts(rows)
        assert dicts == [{"key": "x", "value": "1"}, {"key": "y", "value": "2"}]


# ── Column validation ────────────────────────────────────────────────────────


class TestColumnValidation:
    def test_valid_columns_cached(self, db):
        cols = db._valid_columns("settings")
        assert "key" in cols
        assert "value" in cols
        # Second call returns cached
        assert db._valid_columns("settings") is db._schema_cache["settings"]

    def test_validate_column_keys_valid(self, db):
        # Should not raise
        db._validate_column_keys({"key": "k", "value": "v"}, "settings")

    def test_validate_column_keys_invalid(self, db):
        with pytest.raises(ValueError, match="Invalid column"):
            db._validate_column_keys({"nonexistent": 1}, "settings")


# ── Read-only connection ─────────────────────────────────────────────────────


class TestReadOnlyConnection:
    def test_open_readonly_in_memory(self):
        conn = DatabaseManager.open_readonly_connection(":memory:")
        assert conn is not None
        assert conn.execute("SELECT 1").fetchone()[0] == 1
        conn.close()

    def test_open_readonly_file(self, db_path):
        # First create a real DB
        dm = DatabaseManager(db_path)
        dm.save_setting("ro_test", "ok")
        dm.close()

        ro = DatabaseManager.open_readonly_connection(db_path)
        val = ro.execute("SELECT value FROM settings WHERE key='ro_test'").fetchone()[0]
        assert val == "ok"
        ro.close()

    def test_readonly_rejects_writes(self, db_path):
        dm = DatabaseManager(db_path)
        dm.save_setting("ro_test", "ok")
        dm.close()

        ro = DatabaseManager.open_readonly_connection(db_path)
        with pytest.raises(sqlite3.OperationalError):
            ro.execute("INSERT INTO settings (key, value) VALUES ('x', 'y')")
        ro.close()

    def test_open_readonly_missing_file(self):
        with pytest.raises(sqlite3.OperationalError):
            DatabaseManager.open_readonly_connection("/nonexistent/path.db")

    def test_readonly_uses_row_factory(self, db_path):
        dm = DatabaseManager(db_path)
        dm.save_setting("rf", "1")
        dm.close()
        ro = DatabaseManager.open_readonly_connection(db_path)
        row = ro.execute("SELECT key, value FROM settings WHERE key='rf'").fetchone()
        assert hasattr(row, "keys")  # sqlite3.Row
        ro.close()


# ── Close ────────────────────────────────────────────────────────────────────


class TestClose:
    def test_close_sqlite(self, db):
        db.close()
        # After close, conn property creates a new connection (pool resets)
        assert db.conn is not None

    def test_close_called_multiple_times(self, db):
        db.close()
        db.close()  # Should not raise

    def test_close_then_use(self, db):
        db.close()
        db.conn.execute("SELECT 1")  # Should create a fresh connection


# ── Deprecated CRUD warnings ────────────────────────────────────────────────


class TestDeprecatedWarnings:
    """Deprecated methods emit a DeprecationWarning AND execute real repo code.

    We verify the warning fires, but wrap in try/except because the
    underlying repo call may fail on an empty/partially-initialized DB.
    """

    def test_add_trip_deprecated(self, db):
        with pytest.warns(DeprecationWarning, match="add_trip"):
            try:
                db.add_trip({})
            except Exception:
                pass

    def test_update_trip_deprecated(self, db):
        with pytest.warns(DeprecationWarning, match="update_trip"):
            try:
                db.update_trip(1, {})
            except Exception:
                pass

    def test_delete_trip_deprecated(self, db):
        with pytest.warns(DeprecationWarning, match="delete_trip"):
            try:
                db.delete_trip(1)
            except Exception:
                pass

    def test_get_all_trucks_deprecated(self, db):
        with pytest.warns(DeprecationWarning, match="get_all_trucks"):
            try:
                db.get_all_trucks()
            except Exception:
                pass

    def test_add_truck_deprecated(self, db):
        with pytest.warns(DeprecationWarning, match="add_truck"):
            try:
                db.add_truck({})
            except Exception:
                pass


# ── Error handling ───────────────────────────────────────────────────────────


class TestErrorHandling:
    def test_conn_execute_wrong_table(self, db):
        with pytest.raises(sqlite3.OperationalError):
            db.conn.execute("SELECT * FROM nonexistent")

    def test_save_setting_integrity(self, db):
        # Should not raise — INSERT OR REPLACE handles duplicates
        db.save_setting("k", "v1")
        db.save_setting("k", "v2")  # no error
        assert db.get_setting("k") == "v2"

    def test_init_with_bad_path_raises(self):
        with pytest.raises(sqlite3.OperationalError):
            DatabaseManager("/invalid/path/that/does/not/exist/db.sqlite")

    def test_ensure_expenses_table_creates(self, db):
        with pytest.warns(DeprecationWarning):
            db.ensure_expenses_table()
        tables = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "expenses" in tables


# ── User / Company attributes ───────────────────────────────────────────────


class TestUserCompany:
    def test_default_attributes(self, db):
        assert db.user_company_id is None
        assert db.user_role == ""

    def test_set_attributes(self, db):
        db.user_company_id = 42
        db.user_role = "admin"
        assert db.user_company_id == 42
        assert db.user_role == "admin"


# ── Unique lists helper ──────────────────────────────────────────────────────


class TestUniqueLists:
    def test_get_unique_lists_empty(self, db):
        trucks, drivers = db.get_unique_lists()
        assert trucks == []
        assert drivers == []
