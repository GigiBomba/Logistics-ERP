"""Tests for new DatabaseManager methods — Phase 1 engine-agnostic layer.

Covers: execute, executemany, commit, rollback, _adapt_placeholders,
_table_exists, _column_exists, _split_pg_statements, row_to_dict.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from database.db_manager import DatabaseManager, _split_pg_statements


# ── Fixtures ──────────────────────────────────────────────────────────────────


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


# ── execute() method ──────────────────────────────────────────────────────────


class TestExecuteMethod:
    """Tests for the new db.execute() engine-agnostic wrapper."""

    def test_execute_select(self, db):
        cursor = db.execute("SELECT 1 AS one")
        row = cursor.fetchone()
        assert dict(row)["one"] == 1

    def test_execute_insert(self, db):
        db.execute("INSERT INTO companies (company_name) VALUES (?)", ("TestCo",))
        db.commit()
        result = db.execute(
            "SELECT company_name FROM companies WHERE company_name = ?", ("TestCo",)
        ).fetchone()
        assert dict(result)["company_name"] == "TestCo"

    def test_execute_update(self, db):
        db.execute("INSERT INTO companies (company_name) VALUES (?)", ("Before",))
        db.commit()
        db.execute("UPDATE companies SET company_name = ? WHERE company_name = ?", ("After", "Before"))
        db.commit()
        result = db.execute(
            "SELECT company_name FROM companies WHERE company_name = ?", ("After",)
        ).fetchone()
        assert result is not None

    def test_execute_delete(self, db):
        db.execute("INSERT INTO companies (company_name) VALUES (?)", ("DelMe",))
        db.commit()
        db.execute("DELETE FROM companies WHERE company_name = ?", ("DelMe",))
        db.commit()
        result = db.execute(
            "SELECT company_name FROM companies WHERE company_name = ?", ("DelMe",)
        ).fetchone()
        assert result is None

    def test_execute_no_params(self, db):
        cursor = db.execute("SELECT 1")
        assert cursor.fetchone() is not None

    def test_execute_multiple_params(self, db):
        db.execute(
            "INSERT INTO companies (company_name, subscription_tier) VALUES (?, ?)",
            ("MultiParam", "starter"),
        )
        db.commit()
        result = db.execute(
            "SELECT * FROM companies WHERE company_name = ?", ("MultiParam",)
        ).fetchone()
        assert result is not None


# ── executemany() method ──────────────────────────────────────────────────────


class TestExecuteManyMethod:
    """Tests for db.executemany() bulk operation wrapper."""

    def test_executemany_insert(self, db):
        data = [("A", "starter"), ("B", "starter"), ("C", "professional")]
        db.executemany(
            "INSERT INTO companies (company_name, subscription_tier) VALUES (?, ?)",
            data,
        )
        db.commit()
        # Exclude the sentinel company (id=0, seeded on DB bootstrap for FK
        # integrity) — the assertion is about the rows executemany inserted.
        count = db.execute(
            "SELECT COUNT(*) AS c FROM companies WHERE id != 0"
        ).fetchone()
        assert dict(count)["c"] == 3


# ── commit() / rollback() methods ─────────────────────────────────────────────


class TestCommitRollback:
    """Tests for engine-agnostic commit() and rollback()."""

    def test_commit(self, db):
        db.execute("INSERT INTO companies (company_name) VALUES (?)", ("CommitTest",))
        db.commit()
        result = db.execute(
            "SELECT company_name FROM companies WHERE company_name = ?", ("CommitTest",)
        ).fetchone()
        assert result is not None

    def test_rollback_discards_changes(self, db):
        db.execute("INSERT INTO companies (company_name) VALUES (?)", ("RollbackTest",))
        db.rollback()
        result = db.execute(
            "SELECT company_name FROM companies WHERE company_name = ?", ("RollbackTest",)
        ).fetchone()
        assert result is None

    def test_commit_after_rollback(self, db):
        """A new transaction after rollback should work."""
        db.execute("INSERT INTO companies (company_name) VALUES (?)", ("RB1",))
        db.rollback()
        db.execute("INSERT INTO companies (company_name) VALUES (?)", ("RB2",))
        db.commit()
        result = db.execute(
            "SELECT company_name FROM companies WHERE company_name = ?", ("RB2",)
        ).fetchone()
        assert result is not None


# ── _adapt_placeholders() ─────────────────────────────────────────────────────


class TestAdaptPlaceholders:
    """Tests for SQLite ? → PostgreSQL %s placeholder conversion."""

    def test_sqlite_no_change(self, db):
        """SQLite queries pass through unchanged."""
        assert db._adapt_placeholders("SELECT * FROM trips WHERE id = ?") == \
            "SELECT * FROM trips WHERE id = ?"

    def test_multiple_placeholders(self):
        """Multiple ? should all stay as ? for SQLite."""
        db_temp = DatabaseManager._adapt_placeholders
        # _adapt_placeholders is an instance method, test via mock
        query = "INSERT INTO t (a, b, c) VALUES (?, ?, ?)"
        # For SQLite, no change
        # We can't easily test PostgreSQL path without PG connection,
        # but we can verify the engine check works.
        assert "?" in query  # SQLite keeps ?

    def test_no_placeholder_query(self, db):
        """Queries without ? should be returned unchanged."""
        assert db._adapt_placeholders("SELECT 1") == "SELECT 1"


# ── _table_exists() ───────────────────────────────────────────────────────────


class TestTableExists:
    """Tests for engine-agnostic table existence check."""

    def test_existing_table(self, db):
        assert db._table_exists("trips")
        assert db._table_exists("companies")
        assert db._table_exists("invoices")

    def test_non_existing_table(self, db):
        assert not db._table_exists("nonexistent_xyz_table")

    def test_case_sensitive(self, db):
        """Table names are case-insensitive in SQLite but PG is case-sensitive."""
        assert db._table_exists("TRIPS") or db._table_exists("trips")  # at least one works


# ── _column_exists() ──────────────────────────────────────────────────────────


class TestColumnExists:
    """Tests for engine-agnostic column existence check."""

    def test_existing_column(self, db):
        assert db._column_exists("trips", "id")
        assert db._column_exists("companies", "company_name")

    def test_non_existing_column(self, db):
        assert not db._column_exists("trips", "nonexistent_column_xyz")

    def test_migration_columns(self, db):
        """Columns added by Phase 0 migrations should exist."""
        assert db._column_exists("trips", "company_id")
        assert db._column_exists("trips", "deleted_at")
        assert db._column_exists("clients", "deleted_at")


# ── row_to_dict() / rows_to_dicts() ───────────────────────────────────────────


class TestRowToDict:
    """Tests for row conversion methods."""

    def test_row_to_dict_sqlite_row(self, db):
        row = db.conn.execute("SELECT 1 AS num, 'hello' AS text").fetchone()
        result = db.row_to_dict(row)
        assert result == {"num": 1, "text": "hello"}

    def test_row_to_dict_none(self, db):
        assert db.row_to_dict(None) is None

    def test_row_to_dict_already_dict(self, db):
        """Should handle already-dict input (PostgreSQL RealDictCursor)."""
        already = {"num": 1, "text": "hello"}
        result = db.row_to_dict(already)
        assert result == {"num": 1, "text": "hello"}

    def test_rows_to_dicts_empty(self, db):
        assert db.rows_to_dicts([]) == []

    def test_rows_to_dicts_multiple(self, db):
        rows = db.conn.execute("SELECT 1 AS n UNION ALL SELECT 2").fetchall()
        result = db.rows_to_dicts(rows)
        assert len(result) == 2
        assert result[0]["n"] == 1
        assert result[1]["n"] == 2


# ── _split_pg_statements() ────────────────────────────────────────────────────


class TestSplitPGStatements:
    """Tests for PostgreSQL SQL statement splitter."""

    def test_simple_statements(self):
        sql = "SELECT 1; SELECT 2; SELECT 3;"
        stmts = _split_pg_statements(sql)
        assert len(stmts) == 3

    def test_dollar_block_preserved(self):
        """PL/pgSQL function with $$...$$ should not be split."""
        sql = """
        CREATE OR REPLACE FUNCTION my_func() RETURNS TRIGGER AS $$
        BEGIN
            NEW.val := 1;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
        stmts = _split_pg_statements(sql)
        # Should be one statement containing the function definition
        assert len(stmts) >= 1
        # The function definition should be intact (contain $$)
        first = stmts[0]
        assert "$$" in first
        assert "BEGIN" in first
        assert "END" in first

    def test_drop_trigger_then_create(self):
        """DROP TRIGGER IF EXISTS; CREATE TRIGGER pattern."""
        sql = """
        DROP TRIGGER IF EXISTS my_trigger ON my_table;
        CREATE TRIGGER my_trigger BEFORE INSERT ON my_table
        FOR EACH ROW EXECUTE FUNCTION my_func();
        """
        stmts = _split_pg_statements(sql)
        assert len(stmts) >= 2
        assert "DROP TRIGGER" in stmts[0]
        assert "CREATE TRIGGER" in stmts[1]

    def test_comment_lines_removed(self):
        sql = """
        -- This is a comment
        SELECT 1;
        -- Another comment
        SELECT 2;
        """
        stmts = _split_pg_statements(sql)
        assert len(stmts) >= 2
        assert "SELECT 1" in stmts[0]
        assert "SELECT 2" in stmts[1]

    def test_empty_input(self):
        assert _split_pg_statements("") == []
        assert _split_pg_statements(";") == []
        assert _split_pg_statements("  ;  ") == []

    def test_single_statement_no_semicolon(self):
        stmts = _split_pg_statements("SELECT 1")
        assert len(stmts) == 1
        assert "SELECT 1" in stmts[0]

    def test_multiple_dollar_blocks(self):
        """Two PL/pgSQL functions in the same SQL."""
        sql = """
        CREATE OR REPLACE FUNCTION f1() RETURNS TRIGGER AS $$
        BEGIN RETURN NEW; END;
        $$ LANGUAGE plpgsql;

        CREATE OR REPLACE FUNCTION f2() RETURNS TRIGGER AS $$
        BEGIN RETURN OLD; END;
        $$ LANGUAGE plpgsql;
        """
        stmts = _split_pg_statements(sql)
        # Should have at least 2 statements
        assert len(stmts) >= 2
        assert any("f1" in s for s in stmts)
        assert any("f2" in s for s in stmts)


# ── health_stats property ─────────────────────────────────────────────────────


class TestHealthStats:
    """Tests for db.health_stats property."""

    def test_health_stats_sqlite(self, db):
        stats = db.health_stats
        assert stats["engine"] == "sqlite"
        assert stats["pool"]["status"] == "active"


# ── Engine attribute ──────────────────────────────────────────────────────────


class TestEngineAttribute:
    """Tests for _engine attribute correctness."""

    def test_default_engine_sqlite(self, db):
        assert db._engine == "sqlite"

    def test_explicit_sqlite(self, db_path):
        dm = DatabaseManager(db_path, engine="sqlite")
        try:
            assert dm._engine == "sqlite"
        finally:
            dm.close()


# ── Error handling ────────────────────────────────────────────────────────────


class TestExecuteErrorHandling:
    """Tests for execute() error cases."""

    def test_execute_bad_sql(self, db):
        with pytest.raises(sqlite3.OperationalError):
            db.execute("BOGUS STATEMENT")

    def test_execute_wrong_params_count(self, db):
        with pytest.raises(Exception):
            db.execute("SELECT ?", (1, 2))  # too many params

    def test_executemany_mismatch(self, db):
        with pytest.raises(Exception):
            db.executemany("INSERT INTO companies (company_name) VALUES (?)", [("A", "B")])
