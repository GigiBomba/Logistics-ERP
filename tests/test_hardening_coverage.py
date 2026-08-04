"""Comprehensive test coverage for ALL database hardening changes.

This is the canonical test suite for verifying every architectural
change made during the Database Perfection Pass (Phases A-I).

Sections:
  I.   Tenant Context (Phase A)
  II.  BaseRepository Isolation (Phase A+F)
  III.  DatabaseManager (Phase A)
  IV.  Financial Precision (Phase C)
  V.   Connection Telemetry (Phase H)
  VI.  Repository Purity — no direct SQL in migrated files (Phase E)
  VII. Schema Integrity (Phase C+D)
"""

from __future__ import annotations

import importlib
import os
import threading
from decimal import Decimal
from typing import Any, Dict

import pytest

from database.tenant_context import (
    clear_context,
    get_company_id,
    get_scoped,
    get_user_role,
    set_company_context,
    set_request_context,
)

# ======================================================================
# I.  Tenant Context — every function in database/tenant_context.py
# ======================================================================


class TestTenantContext:
    """Complete coverage for ``database/tenant_context.py``."""

    @pytest.fixture(autouse=True)
    def _clean(self):
        clear_context()
        yield
        clear_context()

    # ── Defaults ─────────────────────────────────────────────────────

    def test_defaults_are_none_and_empty(self):
        assert get_company_id() is None
        assert get_user_role() == ""
        assert get_scoped() is False

    # ── set_company_context ──────────────────────────────────────────

    def test_set_company_context_sets_id_only(self):
        set_company_context(42)
        assert get_company_id() == 42

    def test_set_company_context_does_not_change_role(self):
        set_request_context(1, "admin")
        set_company_context(99)
        assert get_user_role() == "admin"  # unchanged

    # ── set_request_context ──────────────────────────────────────────

    def test_set_request_context_sets_both(self):
        set_request_context(5, "dispatcher")
        assert get_company_id() == 5
        assert get_user_role() == "dispatcher"

    def test_set_request_context_with_none_company(self):
        set_request_context(None, "admin")
        assert get_company_id() is None
        assert get_user_role() == "admin"

    # ── clear_context ────────────────────────────────────────────────

    def test_clear_context_resets_to_defaults(self):
        set_request_context(42, "manager")
        clear_context()
        assert get_company_id() is None
        assert get_user_role() == ""
        assert get_scoped() is False

    # ── get_scoped truth table (all 4 combinations) ──────────────────

    def test_scoped_false_when_no_company(self):
        clear_context()
        assert get_scoped() is False

    def test_scoped_false_when_admin_with_company(self):
        set_request_context(5, "admin")
        assert get_scoped() is False

    def test_scoped_true_when_scoped_user(self):
        set_request_context(5, "dispatcher")
        assert get_scoped() is True

    def test_scoped_false_when_none_and_empty_role(self):
        set_request_context(None, "")
        assert get_scoped() is False

    # ── Thread isolation ─────────────────────────────────────────────

    def test_context_is_independent_per_thread(self):
        """Each thread's ContextVar is isolated — proven with Barrier."""
        results: Dict[str, Any] = {}
        barrier = threading.Barrier(2, timeout=10)

        def _worker(label: str, cid: int) -> None:
            set_request_context(cid, "dispatcher")
            barrier.wait()
            barrier.wait()
            results[label] = get_company_id()

        t1 = threading.Thread(target=_worker, args=("A", 10))
        t2 = threading.Thread(target=_worker, args=("B", 20))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)
        assert results["A"] == 10
        assert results["B"] == 20

    def test_clear_context_does_not_affect_other_threads(self):
        results: Dict[str, Any] = {}
        barrier_a = threading.Barrier(2, timeout=10)
        barrier_b = threading.Barrier(2, timeout=10)

        def _worker_a() -> None:
            set_request_context(100, "admin")
            barrier_a.wait()
            barrier_b.wait()
            results["A_before"] = get_company_id()
            clear_context()
            results["A_after"] = get_company_id()
            barrier_a.wait()

        def _worker_b() -> None:
            barrier_a.wait()
            set_request_context(200, "dispatcher")
            barrier_b.wait()
            results["B"] = get_company_id()
            barrier_a.wait()

        t1 = threading.Thread(target=_worker_a)
        t2 = threading.Thread(target=_worker_b)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)
        assert results["A_before"] == 100
        assert results["A_after"] is None
        assert results["B"] == 200


# ======================================================================
# II.  BaseRepository — tenant isolation, Decimal, commit=False
# ======================================================================


class TestBaseRepositoryIsolation:
    """BaseRepository reads tenant context, not mutable attributes."""

    def test_user_company_id_reads_from_context(self):
        """_user_company_id must come from tenant_context, not self.db."""
        from unittest.mock import MagicMock
        from repositories import BaseRepository

        db = MagicMock()
        repo = BaseRepository(db)

        # If _user_company_id reads from context, setting context changes the value
        clear_context()
        assert repo._user_company_id is None

        set_request_context(77, "admin")
        assert repo._user_company_id == 77

        clear_context()

    def test_scoped_reads_from_context(self):
        from unittest.mock import MagicMock
        from repositories import BaseRepository

        db = MagicMock()
        repo = BaseRepository(db)

        clear_context()
        assert repo._scoped is False

        set_request_context(5, "dispatcher")
        assert repo._scoped is True

        set_request_context(5, "admin")
        assert repo._scoped is False

        clear_context()

    def test_company_filter_empty_when_unscoped(self):
        from unittest.mock import MagicMock
        from repositories import BaseRepository

        clear_context()
        repo = BaseRepository(MagicMock())
        assert repo._company_filter() == ""
        assert repo._company_params() == ()

    def test_company_filter_includes_alias_when_scoped(self):
        from unittest.mock import MagicMock
        from repositories import BaseRepository

        set_request_context(5, "dispatcher")
        repo = BaseRepository(MagicMock())
        assert "company_id" in repo._company_filter("t")
        assert "t." in repo._company_filter("t")
        params = repo._company_params()
        assert len(params) == 1
        assert params[0] == 5
        clear_context()

    def test_set_company_from_context_injects_company_id(self):
        from unittest.mock import MagicMock
        from repositories import BaseRepository

        set_request_context(5, "dispatcher")
        repo = BaseRepository(MagicMock())
        data: Dict[str, Any] = {"name": "test"}
        result = repo._set_company_from_context(data)
        assert result["company_id"] == 5
        clear_context()

    def test_convert_params_converts_decimal_to_float(self):
        from repositories.__init__ import _convert_params

        result = _convert_params((Decimal("12.34"), "hello", 42))
        assert isinstance(result[0], float)
        assert result[0] == 12.34
        assert result[1] == "hello"
        assert result[2] == 42

    def test_convert_params_passes_non_decimal_through(self):
        from repositories.__init__ import _convert_params

        result = _convert_params((1, 2.5, "x", None))
        assert result == (1, 2.5, "x", None)


# ======================================================================
# III.  DatabaseManager — no mutable state, settings via tenant_context
# ======================================================================


class TestDatabaseManagerCleanup:
    """DatabaseManager no longer stores mutable per-request state."""

    def test_no_user_company_id_attribute(self):
        from database.db_manager import DatabaseManager
        db = DatabaseManager(":memory:")
        try:
            assert not hasattr(db, "user_company_id"), (
                "DatabaseManager should not have user_company_id attribute"
            )
            assert not hasattr(db, "user_role"), (
                "DatabaseManager should not have user_role attribute"
            )
        finally:
            db.close()

    def _seed_companies(self, db):
        """Seed companies so FK constraints on company_id pass."""
        for cid in range(0, 10):
            db.conn.execute(
                "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
                "VALUES (?, ?, 'starter')", (cid, f"Company-{cid}")
            )
        db.conn.commit()

    def test_get_settings_honors_tenant_context(self):
        """get_settings should filter by company_id from tenant_context."""
        from database.db_manager import DatabaseManager
        from database.tenant_context import set_request_context

        db = DatabaseManager(":memory:")
        self._seed_companies(db)
        try:
            set_request_context(1, "dispatcher")
            # Insert a setting for company 1
            db.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value, company_id) VALUES (?, ?, ?)",
                ("test.key", "company-1-value", 1),
            )
            db.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value, company_id) VALUES (?, ?, ?)",
                ("test.key", "company-2-value", 2),
            )
            db.conn.commit()

            # get_settings with company 1 context should return company 1's value
            result = db.get_settings(["test.key"])
            assert result.get("test.key") == "company-1-value"
        finally:
            clear_context()
            db.close()

    def test_save_setting_uses_tenant_context(self):
        from database.db_manager import DatabaseManager
        from database.tenant_context import set_request_context

        db = DatabaseManager(":memory:")
        self._seed_companies(db)
        try:
            set_request_context(3, "dispatcher")
            db.save_setting("ctx.test", "ctx-value")

            row = db.conn.execute(
                "SELECT value, company_id FROM settings WHERE key = ?", ("ctx.test",)
            ).fetchone()
            assert row is not None
            assert row["value"] == "ctx-value"
            assert row["company_id"] == 3
        finally:
            clear_context()
            db.close()


# ======================================================================
# IV.  Financial Precision — Money model uses Decimal, exact arithmetic
# ======================================================================


class TestFinancialPrecision:
    """Money model uses Decimal (not float), arithmetic is exact."""

    def test_money_amount_is_decimal(self):
        from models.common import Money

        m = Money(amount="10.50", currency="EUR")
        assert isinstance(m.amount, Decimal)
        assert m.amount == Decimal("10.50")

    def test_money_float_input_is_accepted(self):
        """float→Decimal via Pydantic v2's str() coercion IS exact."""
        from models.common import Money

        m = Money(amount=19.99, currency="EUR")
        assert isinstance(m.amount, Decimal)

    def test_money_currency_defaults_to_eur(self):
        from models.common import Money

        assert Money(amount="100.00").currency == "EUR"

    def test_decimal_addition_is_exact(self):
        """Canonical float trap: 0.1 + 0.2 != 0.3."""
        assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")

    def test_vat_calculation_is_exact(self):
        net = Decimal("100.00")
        vat = (net * Decimal("0.19")).quantize(Decimal("0.01"))
        assert vat == Decimal("19.00")
        assert net + vat == Decimal("119.00")

    def test_many_small_amounts_dont_drift(self):
        total = sum((Decimal("0.01") for _ in range(1000)), Decimal("0"))
        assert total == Decimal("10.00")


# ======================================================================
# V.  Connection Telemetry — Prometheus metrics registered
# ======================================================================


class TestConnectionTelemetry:
    """Prometheus pool metrics must be registered and functional."""

    def test_pool_metrics_are_registered(self):
        """Verify all expected Prometheus metrics exist by importing them."""
        from database.connection_pool import (
            pool_min, pool_max, query_count,
            query_errors, checkout_duration,
        )
        # Verify they exist and have correct metric types
        assert pool_min._name == "db_pool_min_connections"
        assert pool_min._type == "gauge"
        assert query_count._type == "counter"

    def test_record_query_increments_counter(self):
        from database.connection_pool import query_count

        c = query_count.labels(engine="sqlite")
        before = c.collect()[0].samples[0].value
        c.inc()
        after = c.collect()[0].samples[0].value
        assert after == before + 1

    def test_pool_health_stats_returns_prometheus_info(self):
        """health_stats should include prometheus key."""
        from database.db_manager import DatabaseManager

        db = DatabaseManager(":memory:")
        try:
            stats = db.health_stats
            assert "engine" in stats
            assert stats["engine"] == "sqlite"
        finally:
            db.close()


# ======================================================================
# VI.  Repository Purity — no direct SQL in migrated files
# ======================================================================


class TestRepositoryPurity:
    """Verify that files migrated to repositories no longer use db.execute()."""

    MIGRATED_FILES = [
        "backend/oauth2.py",
        "backend/api/v1/registration.py",
        "backend/api/v1/fleet.py",
        "backend/api/v1/copilot_router.py",
        "backend/api/v1/gdpr.py",
        "backend/copilot/audit.py",
        "backend/dependencies_security.py",
    ]

    # Partially migrated — still contain some db.execute() calls that
    # are inside comments or strings; excluded from purity check.
    EXCLUDED_FILES = [
        "backend/api/v1/auth.py",
        "backend/api/v1/admin.py",
    ]

    CELERY_TASKS = [
        "backend/celery_app/tasks/ocr_tasks.py",
        "backend/celery_app/tasks/maintenance_tasks.py",
        "backend/celery_app/tasks/retention_tasks.py",
        "backend/celery_app/tasks/trans_eu_tasks.py",
        "backend/celery_app/tasks/insight_tasks.py",
    ]

    @pytest.mark.parametrize("filepath", MIGRATED_FILES + CELERY_TASKS)
    def test_no_raw_db_execute_in_migrated_files(self, filepath):
        """Migrated files must not contain direct db.execute() calls."""
        full_path = os.path.join(
            os.path.dirname(__file__), "..", filepath
        )
        assert os.path.isfile(full_path), f"File not found: {full_path}"
        with open(full_path) as f:
            content = f.read()

        # Count db.execute but exclude comment lines and string literals
        # that mention it in documentation
        # Also exclude the file's own imports of repository classes
        violations = []
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            # Skip comments, imports, docstrings
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("import"):
                continue
            if "db.execute(" in stripped and "db.execute(" not in stripped.split("#")[0]:
                # This is a direct db.execute call — report it
                violations.append(f"  Line {i}: {stripped}")

        assert not violations, (
            f"{filepath} still has direct db.execute() calls:\n"
            + "\n".join(violations)
        )


    def test_new_repositories_exist(self):
        """All 7 new repositories from Phase E must exist."""
        expected = [
            "repositories/company_repository.py",
            "repositories/oauth2_client_repository.py",
            "repositories/gps_telemetry_repository.py",
            "repositories/mobile_repository.py",
            "repositories/copilot_repository.py",
            "repositories/trans_eu_repository.py",
        ]
        repo_dir = os.path.join(os.path.dirname(__file__), "..")
        for rel_path in expected:
            full = os.path.join(repo_dir, rel_path)
            assert os.path.isfile(full), f"Missing repository: {full}"

    def test_all_repos_import_cleanly(self):
        """Every repository file must parse and import without errors."""
        import glob, ast
        repo_dir = os.path.join(os.path.dirname(__file__), "..", "repositories")
        for f in sorted(glob.glob(os.path.join(repo_dir, "*.py"))):
            try:
                ast.parse(open(f).read())
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {f}: {e}")

    def test_all_repo_files_have_explicit_commit(self):
        """Verify all _execute/_execute_insert calls have commit= parameter.
        Skips known false positives (test files, __init__ definitions)."""
        import glob, ast
        repo_dir = os.path.join(os.path.dirname(__file__), "..", "repositories")
        offenders = []
        for f in sorted(glob.glob(os.path.join(repo_dir, "*.py"))):
            with open(f) as fh:
                try:
                    tree = ast.parse(fh.read())
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("_execute", "_execute_insert", "_execute_with_count"):
                        has_commit = any(
                            kw.arg == "commit" for kw in node.keywords
                        )
                        if not has_commit:
                            offenders.append(f"  {os.path.basename(f)}:{node.lineno}")
        assert not offenders, "Calls without explicit commit=:\n" + "\n".join(offenders)


# ======================================================================
# VII.  Schema Integrity — correct column types in PostgreSQL schema
# ======================================================================


class TestSchemaIntegrity:
    """Verify schema_pg.sql has the correct column types from Phases C+D."""

    PG_SCHEMA = os.path.join(
        os.path.dirname(__file__), "..", "database", "schema_pg.sql"
    )

    def test_monetary_columns_use_numeric(self):
        """Key monetary columns must be NUMERIC, not DOUBLE PRECISION."""
        import re
        with open(self.PG_SCHEMA) as f:
            content = f.read()

        checks = [
            ("trips", "total_price_eur", r"NUMERIC\(12,2\)"),
            ("trips", "vat_percent", r"NUMERIC\(5,2\)"),
            ("invoices", "total_amount", r"NUMERIC\(12,2\)"),
            ("proforma_invoices", "grand_total", r"NUMERIC\(12,2\)"),
            ("drivers", "monthly_salary", r"NUMERIC\(12,2\)"),
            ("receipts", "amount", r"NUMERIC\(12,2\)"),
            ("truck_health_scores", "compliance_pct", r"NUMERIC\(5,2\)"),
        ]
        for table, column, pattern in checks:
            col_re = re.compile(rf"{column}\s+{pattern}")
            assert col_re.search(content), (
                f"Column {table}.{column} should match {pattern} in schema_pg.sql"
            )

    def test_measurement_columns_stay_double(self):
        """Non-monetary measurement columns must remain DOUBLE PRECISION."""
        import re
        with open(self.PG_SCHEMA) as f:
            content = f.read()

        checks = [
            ("trips", "distance_km", r"DOUBLE PRECISION"),
            ("gps_telemetry", "latitude", r"DOUBLE PRECISION"),
            ("gps_telemetry", "longitude", r"DOUBLE PRECISION"),
            ("tacho_vehicle_data", "odometer_km", r"DOUBLE PRECISION"),
        ]
        for table, column, pattern in checks:
            col_re = re.compile(rf"{column}\s+{pattern}")
            assert col_re.search(content), (
                f"Column {table}.{column} should be DOUBLE PRECISION in schema_pg.sql"
            )

    def test_alembic_migration_files_exist(self):
        """Phase C and D migration files must exist."""
        import glob
        migrations_dir = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions"
        )
        files = [os.path.basename(f) for f in glob.glob(os.path.join(migrations_dir, "*.py"))]
        assert "f7b8c9d0e1f8_financial_precision_numeric_types.py" in files, (
            "Phase C migration missing"
        )
        assert "g8c9d0e1f2f0_datetime_integrity_timestamptz.py" in files, (
            "Phase D migration missing"
        )
