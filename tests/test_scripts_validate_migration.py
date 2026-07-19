"""Tests for scripts/validate_migration.py — migration validation logic."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

# Import the module once under patch so that DatabaseManager is mocked
# for the entire test session in this module.
with patch("scripts.validate_migration.DatabaseManager"):
    import scripts.validate_migration as _mod

validate = _mod.validate


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_count_rows(count: int) -> list[dict[str, int]]:
    """Simulate rows_to_dicts output for COUNT(*) queries."""
    return [{"cnt": count}]


def _make_table_list(tables: list[str]) -> list[dict[str, str]]:
    """Simulate rows_to_dicts output for the sqlite_master query."""
    return [{"name": t} for t in tables]


def _patched_validate(rows_to_dicts_side_effect: list):
    """Call validate() with a fully mocked DatabaseManager.

    Returns the (results_dict, mock_instance) tuple so tests can
    also assert on the mock itself (e.g. close calls).
    """
    instance = MagicMock(spec=_mod.DatabaseManager)
    instance.rows_to_dicts.side_effect = rows_to_dicts_side_effect
    # Make .conn and .execute work as attribute-access MagicMocks
    # so that sqlite.conn.execute(...).fetchall() returns a generic mock
    # that rows_to_dicts will ignore (since we use side_effect).
    with patch.object(_mod, "DatabaseManager", return_value=instance):
        results = validate(sqlite_path=":memory:", pg_dsn="sqlite:///fake")
    return results, instance


# ── Tests: all match ───────────────────────────────────────────────────────


class TestValidateSuccess:
    def test_all_tables_pass(self):
        results, _ = _patched_validate([
            _make_table_list(["trips", "trucks", "drivers"]),
            _make_count_rows(100),
            _make_count_rows(100),
            _make_count_rows(50),
            _make_count_rows(50),
            _make_count_rows(25),
            _make_count_rows(25),
        ])

        assert len(results["passed"]) == 3
        assert len(results["failed"]) == 0
        assert len(results["errors"]) == 0
        assert ("trips", 100) in results["passed"]
        assert ("trucks", 50) in results["passed"]
        assert ("drivers", 25) in results["passed"]

    def test_single_table_pass(self):
        results, _ = _patched_validate([
            _make_table_list(["settings"]),
            _make_count_rows(5),
            _make_count_rows(5),
        ])

        assert len(results["passed"]) == 1
        assert results["passed"][0] == ("settings", 5)
        assert results["failed"] == []
        assert results["errors"] == []


# ── Tests: count mismatches ────────────────────────────────────────────────


class TestValidateFailure:
    def test_mismatch_reported(self):
        results, _ = _patched_validate([
            _make_table_list(["trips"]),
            _make_count_rows(100),
            _make_count_rows(95),
        ])

        assert len(results["passed"]) == 0
        assert len(results["failed"]) == 1
        table, sql, pg, diff = results["failed"][0]
        assert table == "trips"
        assert sql == 100
        assert pg == 95
        assert diff == -5

    def test_mixed_pass_fail(self):
        results, _ = _patched_validate([
            _make_table_list(["trips", "trucks"]),
            _make_count_rows(100),
            _make_count_rows(100),
            _make_count_rows(50),
            _make_count_rows(48),
        ])

        assert len(results["passed"]) == 1
        assert results["passed"][0] == ("trips", 100)
        assert len(results["failed"]) == 1
        assert results["failed"][0][0] == "trucks"


# ── Tests: exception handling ──────────────────────────────────────────────


class TestValidateErrors:
    def test_db_exception_caught(self):
        results, _ = _patched_validate([
            _make_table_list(["trips", "faulty"]),
            _make_count_rows(100),
            _make_count_rows(100),
            _make_count_rows(50),
            Exception("connection lost"),
        ])

        assert len(results["passed"]) == 1
        assert len(results["errors"]) == 1
        assert results["errors"][0][0] == "faulty"
        assert "connection lost" in results["errors"][0][1]

    def test_all_errors(self):
        results, _ = _patched_validate([
            _make_table_list(["a", "b"]),
            Exception("fail1"),
            Exception("fail2"),
        ])

        assert len(results["passed"]) == 0
        assert len(results["failed"]) == 0
        assert len(results["errors"]) == 2


# ── Tests: edge cases ──────────────────────────────────────────────────────


class TestValidateEmptyDatabase:
    def test_no_tables(self):
        results, _ = _patched_validate([[], ])
        assert results["passed"] == []
        assert results["failed"] == []
        assert results["errors"] == []

    def test_empty_tables(self):
        results, _ = _patched_validate([
            _make_table_list(["empty_table"]),
            _make_count_rows(0),
            _make_count_rows(0),
        ])

        assert len(results["passed"]) == 1
        assert results["passed"][0] == ("empty_table", 0)


# ── Tests: cleanup ─────────────────────────────────────────────────────────


class TestValidateCleanup:
    def test_close_called_on_success(self):
        _, instance = _patched_validate([
            _make_table_list(["t"]),
            _make_count_rows(1),
            _make_count_rows(1),
        ])
        # DatabaseManager() is called twice (sqlite + pg), each returning instance
        # → close() is called twice on the same instance
        assert instance.close.call_count == 2

    def test_close_called_on_exception(self):
        _, instance = _patched_validate([
            _make_table_list(["t"]),
            Exception("boom"),
        ])
        assert instance.close.call_count == 2


# ── Tests: module structure ────────────────────────────────────────────────


class TestValidateModuleStructure:
    def test_module_importable(self):
        assert hasattr(_mod, "validate")

    def test_validate_signature(self):
        import inspect

        sig = inspect.signature(validate)
        assert "sqlite_path" in sig.parameters
        assert "pg_dsn" in sig.parameters
