"""Tests for scripts/validate_migration.py — migration validation logic."""
from __future__ import annotations

from decimal import Decimal
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


def _make_null_rate(total: int, nulls: int) -> list[dict[str, int]]:
    """Simulate rows_to_dicts output for the null-rate query."""
    return [{"total": total, "nulls": nulls}]


def _make_fk_count(cnt: int) -> list[dict[str, int]]:
    """Simulate rows_to_dicts output for an orphan-count query."""
    return [{"cnt": cnt}]


def _make_money(sum_v, avg_v, n=100, c=100) -> list[dict]:
    """Simulate rows_to_dicts output for a SUM/AVG/count money query."""
    return [{"s": sum_v, "a": avg_v, "n": n, "c": c}]


def _make_col_types(*types) -> list[dict]:
    """Simulate rows_to_dicts output for the PG information_schema type lookup.

    *types* are ``(table, column, data_type)`` triples.
    """
    return [
        {"table_name": t, "column_name": c, "data_type": d}
        for t, c, d in types
    ]


def _make_ts_sample(*values) -> list[dict]:
    """Simulate rows_to_dicts output for a timestamp sample query."""
    return [{"v": v} for v in values]


def _make_unique(nonnull: int, distincts: int) -> list[dict[str, int]]:
    """Simulate rows_to_dicts output for a duplicate-count query."""
    return [{"nonnull": nonnull, "distincts": distincts}]


def _make_db(rows_side_effect: list):
    """A lightweight per-engine mock for direct family-check tests.

    ``rows_to_dicts`` returns each *rows_side_effect* item in order; the
    intermediate ``execute(...).fetchall()`` chain is a generic MagicMock
    that ``rows_to_dicts`` ignores (side_effect takes precedence).
    """
    db = MagicMock()
    db.rows_to_dicts.side_effect = rows_side_effect
    return db


def _patched_validate(rows_to_dicts_side_effect: list, **kwargs):
    """Call validate() with a fully mocked DatabaseManager.

    Returns the (results_dict, mock_instance) tuple so tests can
    also assert on the mock itself (e.g. close calls).

    ``skip_extended`` defaults to True so the legacy row-count tests keep
    their original side-effect lists; extended-check tests pass
    ``skip_extended=False`` explicitly.
    """
    instance = MagicMock(spec=_mod.DatabaseManager)
    instance.rows_to_dicts.side_effect = rows_to_dicts_side_effect
    # Make .conn and .execute work as attribute-access MagicMocks
    # so that sqlite.conn.execute(...).fetchall() returns a generic mock
    # that rows_to_dicts will ignore (since we use side_effect).
    with patch.object(_mod, "DatabaseManager", return_value=instance):
        results = validate(
            sqlite_path=":memory:",
            pg_dsn="sqlite:///fake",
            skip_extended=kwargs.pop("skip_extended", True),
            **kwargs,
        )
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

    def test_validate_signature_extended_params(self):
        import inspect

        sig = inspect.signature(validate)
        assert "skip_extended" in sig.parameters
        assert "sample_size" in sig.parameters
        assert sig.parameters["skip_extended"].default is False
        assert sig.parameters["sample_size"].default == 200


# ── Tests: extended checks — null rates ────────────────────────────────────


class TestNullRates:
    def test_all_within_one_percent(self):
        sqlite = _make_db([
            _make_null_rate(100, 5),    # trips.client_name
            _make_null_rate(100, 2),    # trips.truck_number
            _make_null_rate(80, 0),     # invoices.invoice_number
            _make_null_rate(30, 0),     # documents.doc_number
        ])
        pg = _make_db([
            _make_null_rate(100, 5),
            _make_null_rate(100, 2),
            _make_null_rate(80, 0),
            _make_null_rate(30, 0),
        ])
        check = _mod._check_null_rates(sqlite, pg)
        assert check["check"] == "null_rates"
        assert len(check["passed"]) == 4
        assert check["failed"] == []
        assert check["errors"] == []

    def test_mismatch_reported(self):
        sqlite = _make_db([
            _make_null_rate(100, 5),
            _make_null_rate(100, 2),
            _make_null_rate(80, 0),
            _make_null_rate(30, 0),
        ])
        pg = _make_db([
            _make_null_rate(100, 50),   # 50% vs 5% on trips.client_name
            _make_null_rate(100, 2),
            _make_null_rate(80, 0),
            _make_null_rate(30, 0),
        ])
        check = _mod._check_null_rates(sqlite, pg)
        assert len(check["passed"]) == 3
        assert len(check["failed"]) == 1
        table, col, s_rate, p_rate = check["failed"][0]
        assert table == "trips"
        assert col == "client_name"
        assert s_rate == 0.05
        assert p_rate == 0.5

    def test_query_error_recorded(self):
        sqlite = _make_db([
            _make_null_rate(100, 5),
            Exception("boom"),
            _make_null_rate(80, 0),
            _make_null_rate(30, 0),
        ])
        pg = _make_db([
            _make_null_rate(100, 5),
            _make_null_rate(100, 2),
            _make_null_rate(80, 0),
            _make_null_rate(30, 0),
        ])
        check = _mod._check_null_rates(sqlite, pg)
        assert len(check["errors"]) == 1
        assert "boom" in check["errors"][0][-1]


# ── Tests: extended checks — FK orphans ────────────────────────────────────


class TestFkOrphans:
    def test_no_orphans(self):
        sqlite = _make_db([_make_fk_count(0)] * 4)
        pg = _make_db([_make_fk_count(0)] * 4)
        check = _mod._check_fk_orphans(sqlite, pg)
        assert check["check"] == "fk_orphans"
        assert len(check["passed"]) == 4
        assert check["failed"] == []
        assert check["errors"] == []

    def test_orphans_reported_with_breakdown(self):
        sqlite = _make_db([
            _make_fk_count(3),   # trips.driver_id -> drivers
            _make_fk_count(0),   # trips.truck_id -> trucks
            _make_fk_count(1),   # invoices.trip_id -> trips
            _make_fk_count(0),   # alerts.trip_id -> trips
        ])
        pg = _make_db([
            _make_fk_count(0),
            _make_fk_count(0),
            _make_fk_count(0),
            _make_fk_count(2),   # alerts.trip_id -> trips
        ])
        check = _mod._check_fk_orphans(sqlite, pg)
        assert len(check["passed"]) == 1
        assert len(check["failed"]) == 3
        child, fk, parent, s_cnt, p_cnt = check["failed"][0]
        assert (child, fk, parent) == ("trips", "driver_id", "drivers")
        assert (s_cnt, p_cnt) == (3, 0)
        child, fk, parent, s_cnt, p_cnt = check["failed"][-1]
        assert (child, fk, parent) == ("alerts", "trip_id", "trips")
        assert (s_cnt, p_cnt) == (0, 2)


# ── Tests: extended checks — monetary rounding ─────────────────────────────


class TestMonetaryRounding:
    def test_values_agree(self):
        sqlite = _make_db([
            _make_money(Decimal("1000.00"), Decimal("100.00")),
            _make_money(Decimal("5000.50"), Decimal("500.05")),
            _make_money(Decimal("750.75"), Decimal("75.08")),
        ])
        pg = _make_db([
            _make_money(Decimal("1000.00"), Decimal("100.00")),
            _make_money(Decimal("5000.50"), Decimal("500.05")),
            _make_money(Decimal("750.75"), Decimal("75.08")),
        ])
        check = _mod._check_monetary_rounding(sqlite, pg)
        assert check["check"] == "monetary_rounding"
        assert len(check["passed"]) == 3
        assert check["failed"] == []
        assert check["errors"] == []

    def test_round_before_compare(self):
        # 1000.004 vs 1000.00 both round to 1000.00 -> pass despite raw diff.
        sqlite = _make_db([
            _make_money(Decimal("1000.004"), Decimal("100.004")),
            _make_money(Decimal("5000.004"), Decimal("500.004")),
            _make_money(Decimal("750.004"), Decimal("75.004")),
        ])
        pg = _make_db([
            _make_money(Decimal("1000.00"), Decimal("100.00")),
            _make_money(Decimal("5000.00"), Decimal("500.00")),
            _make_money(Decimal("750.00"), Decimal("75.00")),
        ])
        check = _mod._check_monetary_rounding(sqlite, pg)
        assert len(check["passed"]) == 3
        assert check["failed"] == []

    def test_disagreement_reported(self):
        sqlite = _make_db([
            _make_money(Decimal("999.50"), Decimal("99.95")),
            _make_money(Decimal("5000.50"), Decimal("500.05")),
            _make_money(Decimal("750.75"), Decimal("75.08")),
        ])
        pg = _make_db([
            _make_money(Decimal("1000.50"), Decimal("100.05")),
            _make_money(Decimal("5000.50"), Decimal("500.05")),
            _make_money(Decimal("750.75"), Decimal("75.08")),
        ])
        check = _mod._check_monetary_rounding(sqlite, pg)
        assert len(check["passed"]) == 2
        assert len(check["failed"]) == 1
        table, col, *_ = check["failed"][0]
        assert (table, col) == ("invoices", "total_amount")

    def test_row_count_divergence_reported_contextually(self):
        # PG trips is empty because the import aborted; report the missing
        # rows instead of a SUM/AVG numeric mismatch.
        sqlite = _make_db([
            _make_money(Decimal("8870.47"), Decimal("2956.82")),
            _make_money(Decimal("19870.47"), Decimal("3974.09"), n=5, c=5),
            _make_money(Decimal("750.75"), Decimal("75.08")),
        ])
        pg = _make_db([
            _make_money(Decimal("8870.47"), Decimal("2956.82")),
            _make_money(None, None, n=0, c=0),
            _make_money(Decimal("750.75"), Decimal("75.08")),
        ])
        check = _mod._check_monetary_rounding(sqlite, pg)
        assert len(check["passed"]) == 2
        assert len(check["failed"]) == 1
        entry = check["failed"][0]
        assert (entry[0], entry[1]) == ("trips", "total_price_eur")
        assert "row-count divergence" in entry[2]
        assert entry[3] == 5
        assert entry[4] == 0

    def test_same_metric_used_on_both_engines(self):
        # SUM and AVG are compared against their own kind (not SUM vs AVG).
        sqlite = _make_db([
            _make_money(Decimal("19870.47"), Decimal("3974.09")),
            _make_money(Decimal("5000.50"), Decimal("500.05")),
            _make_money(Decimal("750.75"), Decimal("75.08")),
        ])
        pg = _make_db([
            _make_money(Decimal("19870.47"), Decimal("3974.09")),
            _make_money(Decimal("5000.50"), Decimal("500.05")),
            _make_money(Decimal("750.75"), Decimal("75.08")),
        ])
        check = _mod._check_monetary_rounding(sqlite, pg)
        assert len(check["passed"]) == 3
        assert check["failed"] == []
        # The generated SQL selects both metrics and a row count.
        sql_used = sqlite.execute.call_args_list[0].args[0]
        assert "SUM(" in sql_used and "AVG(" in sql_used and "COUNT(*)" in sql_used


# ── Tests: extended checks — timestamp formats ─────────────────────────────


class TestTimestampFormats:
    def test_all_iso_pass(self):
        sqlite = _make_db([
            _make_ts_sample("2026-01-01T08:00:00Z", "2026-01-02T08:00:00.123Z"),
            _make_ts_sample("2026-02-01T00:00:00Z"),
        ])
        pg = _make_db([
            _make_col_types(
                ("trips", "created_at", "timestamp with time zone"),
                ("trips", "start_date", "timestamp with time zone"),
            ),
            _make_ts_sample("2026-01-01T08:00:00Z", "2026-01-02T08:00:00Z"),
            _make_ts_sample("2026-02-01T00:00:00Z"),
        ])
        check = _mod._check_timestamp_formats(sqlite, pg, sample_size=200)
        assert check["check"] == "timestamp_formats"
        assert len(check["passed"]) == 2
        assert check["failed"] == []
        assert check["errors"] == []

    def test_timestamp_column_uses_to_char(self):
        sqlite = _make_db([
            _make_ts_sample("2026-01-01T08:00:00Z"),
            _make_ts_sample("2026-02-01T00:00:00Z"),
        ])
        pg = _make_db([
            _make_col_types(
                ("trips", "created_at", "timestamp with time zone"),
                ("trips", "start_date", "timestamp without time zone"),
            ),
            _make_ts_sample("2026-01-01T08:00:00Z"),
            _make_ts_sample("2026-02-01T00:00:00Z"),
        ])
        check = _mod._check_timestamp_formats(sqlite, pg, sample_size=200)
        assert check["passed"]
        pg_sqls = [c.args[0] for c in pg.execute.call_args_list]
        assert all("AT TIME ZONE" in s for s in pg_sqls if s.startswith("SELECT to_char"))

    def test_text_column_uses_raw_value_without_to_char(self):
        # Legacy export/import path stores datetimes as TEXT; the raw value is
        # matched directly (no to_char / AT TIME ZONE).
        sqlite = _make_db([
            _make_ts_sample("2026-01-01T08:00:00Z"),
            _make_ts_sample("2026-01-01"),
        ])
        pg = _make_db([
            _make_col_types(
                ("trips", "created_at", "text"),
                ("trips", "start_date", "text"),
            ),
            _make_ts_sample("2026-01-01T08:00:00Z"),
            _make_ts_sample("2026-01-01"),
        ])
        check = _mod._check_timestamp_formats(sqlite, pg, sample_size=200)
        assert len(check["passed"]) == 2
        assert check["errors"] == []
        pg_sqls = [c.args[0] for c in pg.execute.call_args_list]
        assert not any("AT TIME ZONE" in s for s in pg_sqls)

    def test_type_lookup_error_recorded_not_crash(self):
        sqlite = _make_db([
            _make_ts_sample("2026-01-01T08:00:00Z"),
            _make_ts_sample("2026-02-01T00:00:00Z"),
        ])
        pg = _make_db([Exception("permission denied for information_schema")])
        check = _mod._check_timestamp_formats(sqlite, pg, sample_size=200)
        assert check["passed"] == []
        assert len(check["errors"]) == 2
        assert "permission denied" in check["errors"][0][-1]

    def test_format_discrepancy_reported(self):
        sqlite = _make_db([
            _make_ts_sample("2026-01-01 08:00:00", "not-a-date"),  # 0% iso
            _make_ts_sample("2026-02-01T00:00:00Z"),
        ])
        pg = _make_db([
            _make_col_types(
                ("trips", "created_at", "timestamp with time zone"),
                ("trips", "start_date", "timestamp with time zone"),
            ),
            _make_ts_sample("2026-01-01T08:00:00Z", "2026-01-02T08:00:00Z"),  # 100%
            _make_ts_sample("2026-02-01T00:00:00Z"),
        ])
        check = _mod._check_timestamp_formats(sqlite, pg, sample_size=200)
        assert len(check["failed"]) == 1
        table, col, s_n, s_rate, p_n, p_rate = check["failed"][0]
        assert (table, col) == ("trips", "created_at")
        assert s_n == 2 and p_n == 2
        assert s_rate == 0.0 and p_rate == 1.0

    def test_sample_size_flows_into_limit(self):
        sqlite = _make_db([
            _make_ts_sample("2026-01-01T08:00:00Z"),
            _make_ts_sample("2026-01-01T08:00:00Z"),
        ])
        pg = _make_db([
            _make_col_types(
                ("trips", "created_at", "timestamp with time zone"),
                ("trips", "start_date", "timestamp with time zone"),
            ),
            _make_ts_sample("2026-01-01T08:00:00Z"),
            _make_ts_sample("2026-01-01T08:00:00Z"),
        ])
        check = _mod._check_timestamp_formats(sqlite, pg, sample_size=42)
        assert len(check["passed"]) == 2
        params_used = [c.args[1] for c in sqlite.execute.call_args_list]
        assert params_used == [(42,), (42,)]


# ── Tests: extended checks — unique sampling ───────────────────────────────


class TestUniqueSampling:
    def test_no_duplicates(self):
        sqlite = _make_db([
            _make_unique(80, 80),   # invoices.invoice_number
            _make_unique(30, 30),   # documents.doc_number
            _make_unique(10, 10),   # proforma_invoices.proforma_number
        ])
        pg = _make_db([
            _make_unique(80, 80),
            _make_unique(30, 30),
            _make_unique(10, 10),
        ])
        check = _mod._check_unique_sampling(sqlite, pg)
        assert check["check"] == "unique_sampling"
        assert len(check["passed"]) == 3
        assert check["failed"] == []
        assert check["errors"] == []

    def test_duplicates_reported(self):
        sqlite = _make_db([
            _make_unique(80, 80),
            _make_unique(30, 28),   # 2 duplicate docs on sqlite
            _make_unique(10, 10),
        ])
        pg = _make_db([
            _make_unique(80, 80),
            _make_unique(30, 30),
            _make_unique(10, 9),    # 1 duplicate proforma on pg
        ])
        check = _mod._check_unique_sampling(sqlite, pg)
        assert len(check["passed"]) == 1
        assert len(check["failed"]) == 2
        table, col, s_dups, p_dups = check["failed"][0]
        assert (table, col) == ("documents", "doc_number")
        assert (s_dups, p_dups) == (2, 0)
        table, col, s_dups, p_dups = check["failed"][1]
        assert (table, col) == ("proforma_invoices", "proforma_number")
        assert (s_dups, p_dups) == (0, 1)


# ── Tests: extended checks — full validate() wiring ────────────────────────


class TestValidateExtended:
    def test_all_five_families_reported(self):
        seq = [
            _make_table_list(["trips"]),
            _make_count_rows(100),
            _make_count_rows(100),
            # null_rates: 4 columns x (sqlite, pg)
            _make_null_rate(100, 5), _make_null_rate(100, 5),
            _make_null_rate(100, 2), _make_null_rate(100, 2),
            _make_null_rate(80, 0), _make_null_rate(80, 0),
            _make_null_rate(30, 0), _make_null_rate(30, 0),
            # fk_orphans: 4 FKs x (sqlite, pg), all zero
            _make_fk_count(0), _make_fk_count(0),
            _make_fk_count(0), _make_fk_count(0),
            _make_fk_count(0), _make_fk_count(0),
            _make_fk_count(0), _make_fk_count(0),
            # monetary_rounding: 3 columns x (sqlite, pg)
            _make_money(Decimal("1000.00"), Decimal("100.00")),
            _make_money(Decimal("1000.00"), Decimal("100.00")),
            _make_money(Decimal("1000.00"), Decimal("100.00")),
            _make_money(Decimal("1000.00"), Decimal("100.00")),
            _make_money(Decimal("1000.00"), Decimal("100.00")),
            _make_money(Decimal("1000.00"), Decimal("100.00")),
            # timestamp_formats: pg type lookup, then 2 columns x (sqlite, pg)
            _make_col_types(
                ("trips", "created_at", "timestamp with time zone"),
                ("trips", "start_date", "timestamp with time zone"),
            ),
            _make_ts_sample("2026-01-01T08:00:00Z"),
            _make_ts_sample("2026-01-01T08:00:00Z"),
            _make_ts_sample("2026-01-01T08:00:00Z"),
            _make_ts_sample("2026-01-01T08:00:00Z"),
            # unique_sampling: 3 columns x (sqlite, pg)
            _make_unique(80, 80), _make_unique(80, 80),
            _make_unique(30, 30), _make_unique(30, 30),
            _make_unique(10, 10), _make_unique(10, 10),
        ]
        results, _ = _patched_validate(seq, skip_extended=False)

        # Row-count behaviour is unchanged.
        assert results["passed"] == [("trips", 100)]
        assert results["failed"] == []
        assert results["errors"] == []

        # All five families are reported, each self-contained.
        assert [c["check"] for c in results["checks"]] == [
            "null_rates", "fk_orphans", "monetary_rounding",
            "timestamp_formats", "unique_sampling",
        ]
        for check in results["checks"]:
            assert check["failed"] == []
            assert check["errors"] == []
            assert isinstance(check["passed"], list)
        # Row counts never leak into the checks.
        assert results["checks"][0]["check"] == "null_rates"

    def test_skip_extended_leaves_checks_empty(self):
        results, _ = _patched_validate([
            _make_table_list(["trips"]),
            _make_count_rows(1),
            _make_count_rows(1),
        ])
        assert results["checks"] == []
        assert results["passed"] == [("trips", 1)]
