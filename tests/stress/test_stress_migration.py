"""Stress tests: bulk imports, large datasets, edge-case throughput."""
from __future__ import annotations

import os
import tempfile
import threading
import time
from datetime import datetime
from typing import Any

import pytest

from tests.test_helpers import make_db
from services.migration.types import ExportFormat, ImportFormat, EntityType, MappingConfig

pytestmark = pytest.mark.stresstest


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def service(db):
    from services.migration.import_service import ImportService

    return ImportService(db)


def _generate_client_rows(count: int, name_prefix: str = "Client") -> list[dict[str, Any]]:
    """Generate *count* client rows with unique names."""
    return [{"name": f"{name_prefix} {i:06d}"} for i in range(count)]


class TestStressBulkImport:
    """Stress tests for ImportService under heavy load."""

    def test_import_10000_rows_performance(self, db, service):
        """Import 10 000 client rows — must complete in <5 s."""
        rows = _generate_client_rows(10000)

        start = time.monotonic()
        stats = service.commit(rows, EntityType.CLIENT, dedup_action="import")
        elapsed = time.monotonic() - start

        assert elapsed < 5.0, (
            f"commit() took {elapsed:.2f}s (expected < 5s)"
        )
        assert stats.committed == 10000, (
            f"Expected 10000 committed, got {stats.committed}"
        )

        # Verify all rows in DB
        count = db.conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        assert count == 10000, f"Expected 10000 rows in DB, found {count}"

    def test_commit_with_all_duplicates(self, db, service):
        """Seed 1 client, then commit 1000 identical rows — all skipped."""
        # Seed one client
        db.conn.execute(
            "INSERT INTO clients (name, created_at) VALUES (?, ?)",
            ("Duplicate Client", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.conn.commit()

        rows = [{"name": "Duplicate Client"} for _ in range(1000)]
        stats = service.commit(rows, EntityType.CLIENT, dedup_action="skip")

        assert stats.committed == 0, (
            f"Expected 0 committed, got {stats.committed}"
        )
        assert stats.duplicates_skipped == 1000, (
            f"Expected 1000 skipped, got {stats.duplicates_skipped}"
        )

    def test_many_columns_handled(self, service):
        """Row with 50 columns (5 known, 45 unknown) — validator drops unknowns."""
        row: dict[str, Any] = {
            "name": "Wide Row Client",
            "phone": "+49 30 1234567",
            "email": "test@example.com",
            "address": "123 Main St",
            "vat_number": "DE999999999",
        }
        # Add 45 unknown columns
        for i in range(45):
            row[f"unknown_col_{i}"] = f"value_{i}"

        is_valid, errors, cleaned = service._validator.validate_row(
            row, EntityType.CLIENT
        )
        assert is_valid, f"Expected valid, got errors: {errors}"
        # Cleaned should contain only the 5 known fields
        for key in ("name", "phone", "email", "address", "vat_number"):
            assert key in cleaned, f"Missing expected field '{key}' in cleaned"
        for i in range(45):
            assert f"unknown_col_{i}" not in cleaned, (
                f"Unknown field 'unknown_col_{i}' leaked into cleaned"
            )

    def test_concurrent_exports_different_entities(self, db):
        """Export 500 clients + 500 trucks concurrently — both succeed."""
        pytest.skip("SQLite in-memory DB does not support cross-thread access")
        from services.migration.emigrate_service import EmigrateService

        # Seed data
        for i in range(500):
            db.conn.execute(
                "INSERT INTO clients (name, created_at) VALUES (?, ?)",
                (f"Export Client {i}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
        for i in range(500):
            db.conn.execute(
                "INSERT INTO trucks (plate_number) VALUES (?)",
                (f"EX-{i:04d}",),
            )
        db.conn.commit()

        emigrate = EmigrateService(db)
        tmpdir = tempfile.mkdtemp()
        results: list[Exception | str | None] = [None, None]

        def export_clients():
            try:
                path = os.path.join(tmpdir, "clients.csv")
                results[0] = emigrate.export(
                    EntityType.CLIENT, ExportFormat.CSV, path
                )
            except Exception as exc:
                results[0] = exc

        def export_trucks():
            try:
                path = os.path.join(tmpdir, "trucks.csv")
                results[1] = emigrate.export(
                    EntityType.TRUCK, ExportFormat.CSV, path
                )
            except Exception as exc:
                results[1] = exc

        t1 = threading.Thread(target=export_clients)
        t2 = threading.Thread(target=export_trucks)
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        for idx, result in enumerate(results):
            assert not isinstance(result, Exception), (
                f"Export thread {idx} raised: {result}"
            )
            assert isinstance(result, str), (
                f"Export thread {idx} did not return a path"
            )
            assert os.path.isfile(result), (
                f"Export file missing: {result}"
            )

    def test_large_row_values(self, service):
        """Client name with 10 000 characters — should import fine."""
        huge_name = "A" * 10000
        rows = [{"name": huge_name}]
        stats = service.commit(rows, EntityType.CLIENT, dedup_action="import")
        assert stats.committed == 1, (
            f"Expected 1 committed, got {stats.committed}"
        )

    def test_bulk_validate_10000_rows_memory(self, db, service):
        """Validate 10 000 rows — completes without error / memory leak."""
        rows = _generate_client_rows(10000)
        valid_rows, invalid_rows, error_summary = service.validate_all(
            rows, EntityType.CLIENT
        )
        assert len(valid_rows) == 10000, (
            f"Expected 10000 valid rows, got {len(valid_rows)}"
        )
        assert len(invalid_rows) == 0
        assert error_summary == {}
