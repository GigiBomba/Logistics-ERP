"""Chaos tests: simulate failures during migration operations."""
from __future__ import annotations

import os
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from tests.test_helpers import make_db
from services.migration.types import ExportFormat, ImportFormat, EntityType, MappingConfig

pytestmark = pytest.mark.chaos


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def service(db):
    from services.migration.import_service import ImportService

    return ImportService(db)


@pytest.fixture
def exporter(db):
    from services.migration.emigrate_service import EmigrateService

    return EmigrateService(db)


class TestChaosMigration:
    """Chaos tests for migration import / export operations."""

    # ── DB failure / rollback ──────────────────────────────────────────

    def test_import_commit_with_db_failure_rolls_back(self, db, service):
        """Mock commit_transaction to raise OperationalError — no partial data.

        All inserts should be rolled back when the final commit fails.
        """
        from repositories import BaseRepository

        rows = [{"name": "Rollback Client"}]

        with patch.object(
            BaseRepository,
            "commit_transaction",
            side_effect=sqlite3.OperationalError("disk I/O error"),
        ):
            stats = service.commit(rows, EntityType.CLIENT)

        assert stats.committed == 0, (
            f"Expected 0 committed on failure, got {stats.committed}"
        )
        # Verify no rows leaked into the database
        count = db.conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        assert count == 0, (
            f"Expected 0 rows after rollback, found {count}"
        )

    # ── Corrupt / empty file handling ──────────────────────────────────

    def test_import_with_corrupt_file_handled(self, service):
        """Binary garbage (not valid CSV) → preview raises or returns errors."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"\x00\xFF\xFE\xFD\xFCcorrupt\x01\x02\x03")
            f.flush()
            tmp_path = f.name

        try:
            with pytest.raises((ValueError, Exception)):
                service.preview(tmp_path, ImportFormat.CSV, EntityType.CLIENT)
        finally:
            os.unlink(tmp_path)

    def test_import_zero_rows_empty_file(self, service):
        """Empty file → importer handles gracefully (no crash)."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            f.write("")
            f.flush()
            tmp_path = f.name

        try:
            rows, errors = service.preview(tmp_path, ImportFormat.CSV, EntityType.CLIENT)
            # An empty CSV returns no rows; the schema validator reports the problem
            assert rows == [], f"Expected no rows, got {len(rows)}"
            assert any("no data rows" in e.lower() for e in errors), (
                f"Expected schema error about missing data, got: {errors}"
            )
        finally:
            os.unlink(tmp_path)

    # ── Filesystem / permission failures ───────────────────────────────

    def test_export_to_readonly_directory(self, exporter):
        """Mock os.makedirs to raise PermissionError — export raises."""
        with patch("os.makedirs", side_effect=PermissionError("Access denied")):
            with pytest.raises((PermissionError, RuntimeError, Exception)):
                exporter.export(
                    EntityType.CLIENT,
                    ExportFormat.CSV,
                    "/readonly/export.csv",
                )

    # ── Mapping / column failures ──────────────────────────────────────

    def test_missing_columns_in_mapping(self, service):
        """Apply mapping where a source column does not exist in rows.

        Should not crash — missing columns yield no value, defaults apply.
        """
        rows = [{"name": "Test Client"}]
        mapping = MappingConfig(
            source_columns=["name", "nonexistent_col"],
            target_fields={
                "name": "name",
                "nonexistent_col": "phone",
            },
            entity_type=EntityType.CLIENT,
            defaults={"phone": "+49 30 0000000"},
        )
        mapped = service.apply_mapping(rows, mapping)
        assert len(mapped) == 1
        # 'nonexistent_col' was not in the row, so 'phone' gets the default
        assert mapped[0].get("phone") == "+49 30 0000000", (
            f"Expected default phone, got {mapped[0].get('phone')}"
        )
        assert mapped[0].get("name") == "Test Client"

    # ── None / null handling ───────────────────────────────────────────

    def test_none_values_in_row_safe(self):
        """Row where all values are None — validator handles without crash."""
        from services.migration.import_validator import ImportValidator

        v = ImportValidator()
        is_valid, errors, cleaned = v.validate_row(
            {"name": None, "phone": None, "email": None}, EntityType.CLIENT
        )
        # name=None → missing required field
        assert not is_valid
        assert any("Missing required field" in e for e in errors)
        # None values should not be in cleaned
        assert "name" not in cleaned or cleaned.get("name") is None

    # ── Duplicate detector failure mid-commit ──────────────────────────

    def test_duplicate_detector_db_disconnected(self, db, service):
        """Mock DuplicateDetector.find_duplicates to raise OperationalError.

        The commit() outer try/except should catch it and roll back.
        """
        from services.migration.duplicate_detector import DuplicateDetector

        rows = [{"name": "Safe Client"}, {"name": "Also Safe"}]

        with patch.object(
            DuplicateDetector,
            "find_duplicates",
            side_effect=sqlite3.OperationalError("database is locked"),
        ):
            stats = service.commit(rows, EntityType.CLIENT, dedup_action="skip")

        # All rows should be reported as failed because find_duplicates
        # raised on every row
        assert stats.committed == 0, (
            f"Expected 0 committed after detector failure, got {stats.committed}"
        )

    # ── Half-way transaction failure ───────────────────────────────────

    def test_import_transaction_halfway_token_error(self, db, service):
        """Patch repo._execute_insert to succeed 5 times then raise.

        The service uses best-effort: rows that succeeded before the
        first failure remain committed, failed rows are reported.
        """
        from repositories import BaseRepository

        rows = [{"name": f"Partial Client {i}"} for i in range(10)]
        call_count = [0]

        def _insert_with_failure(sql, params, commit=True):
            call_count[0] += 1
            if call_count[0] > 5:
                raise sqlite3.OperationalError("mid-insert failure")
            return 1

        with patch.object(BaseRepository, "_execute_insert", side_effect=_insert_with_failure):
            stats = service.commit(rows, EntityType.CLIENT)

        assert stats.committed == 5, (
            f"Expected 5 committed before failure, got {stats.committed}"
        )
        assert stats.validation_failures == 5
