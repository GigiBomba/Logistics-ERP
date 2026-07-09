"""Unit tests for ImportService — full import pipeline orchestration."""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from unittest.mock import MagicMock

from services.migration.types import (
    EntityType,
    ImportFormat,
    ImportStats,
    MappingConfig,
)
from tests.test_helpers import make_db


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def service(db):
    from services.migration.import_service import ImportService

    return ImportService(db)


# ── Preview ──────────────────────────────────────────────────────────────────


class TestPreview:
    def test_preview_csv_returns_rows_and_errors(self, service):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            f.write("name,email\nAlice,alice@test.com\nBob,bob@test.com\n")
            f.flush()
            path = f.name
        try:
            rows, errors = service.preview(path, ImportFormat.CSV, EntityType.CLIENT)
            assert len(rows) == 2
            assert rows[0] == {"name": "Alice", "email": "alice@test.com"}
            assert errors == []
        finally:
            os.unlink(path)

    def test_preview_json_returns_rows(self, service):
        data = [{"name": "Alice"}, {"name": "Bob"}]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            path = f.name
        try:
            rows, errors = service.preview(path, ImportFormat.JSON, EntityType.CLIENT)
            assert len(rows) == 2
            assert rows == data
            assert errors == []
        finally:
            os.unlink(path)

    def test_preview_empty_csv_returns_errors(self, service):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            f.write("name,email\n")
            f.flush()
            path = f.name
        try:
            rows, errors = service.preview(path, ImportFormat.CSV, EntityType.CLIENT)
            assert rows == []
            assert len(errors) >= 1
        finally:
            os.unlink(path)

    def test_preview_with_progress_callback(self, service):
        callback = MagicMock()
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            f.write("name\nTest\n")
            f.flush()
            path = f.name
        try:
            rows, errors = service.preview(path, ImportFormat.CSV, EntityType.CLIENT, progress_cb=callback)
            assert len(rows) == 1
            # Should have been called at least once
            callback.assert_called()
        finally:
            os.unlink(path)

    def test_preview_unknown_format_raises(self, service):
        """Passing a raw string raises ValueError or AttributeError."""
        with pytest.raises((ValueError, AttributeError)):
            with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
                path = f.name
            try:
                service.preview(path, "unknown_format", EntityType.CLIENT)  # type: ignore[arg-type]
            finally:
                os.unlink(path)


# ── Apply Mapping ────────────────────────────────────────────────────────────


class TestApplyMapping:
    def test_rename_columns(self, service):
        rows = [{"full_name": "Alice", "email_addr": "alice@test.com"}]
        mapping = MappingConfig(
            source_columns=["full_name", "email_addr"],
            target_fields={"full_name": "name", "email_addr": "email"},
            entity_type=EntityType.CLIENT,
        )
        mapped = service.apply_mapping(rows, mapping)
        assert len(mapped) == 1
        assert mapped[0] == {"name": "Alice", "email": "alice@test.com"}

    def test_drops_unmapped_columns(self, service):
        rows = [{"name": "Alice", "should_drop": "xyz"}]
        mapping = MappingConfig(
            source_columns=["name"],
            target_fields={"name": "name"},
            entity_type=EntityType.CLIENT,
        )
        mapped = service.apply_mapping(rows, mapping)
        assert "should_drop" not in mapped[0]

    def test_applies_defaults(self, service):
        rows = [{"name": "Alice"}]
        mapping = MappingConfig(
            source_columns=["name"],
            target_fields={"name": "name"},
            entity_type=EntityType.CLIENT,
            defaults={"is_active": 1, "currency_preference": "EUR"},
        )
        mapped = service.apply_mapping(rows, mapping)
        assert mapped[0] == {"name": "Alice", "is_active": 1, "currency_preference": "EUR"}

    def test_default_does_not_override_existing(self, service):
        rows = [{"name": "Alice", "is_active": 0}]
        mapping = MappingConfig(
            source_columns=["name", "is_active"],
            target_fields={"name": "name", "is_active": "is_active"},
            entity_type=EntityType.CLIENT,
            defaults={"is_active": 1},
        )
        mapped = service.apply_mapping(rows, mapping)
        assert mapped[0]["is_active"] == 0  # existing value kept

    def test_empty_rows_returns_empty(self, service):
        mapping = MappingConfig(
            source_columns=[],
            target_fields={},
            entity_type=EntityType.CLIENT,
        )
        assert service.apply_mapping([], mapping) == []

    def test_null_values_skipped(self, service):
        rows = [{"full_name": None, "email_addr": "alice@test.com"}]
        mapping = MappingConfig(
            source_columns=["full_name", "email_addr"],
            target_fields={"full_name": "name", "email_addr": "email"},
            entity_type=EntityType.CLIENT,
        )
        mapped = service.apply_mapping(rows, mapping)
        assert "name" not in mapped[0]
        assert mapped[0]["email"] == "alice@test.com"


# ── Validate All ─────────────────────────────────────────────────────────────


class TestValidateAll:
    def test_splits_valid_and_invalid(self, service):
        rows = [
            {"name": "Alice"},
            {"name": ""},
            {"name": "Bob"},
        ]
        valid, invalid, summary = service.validate_all(rows, EntityType.CLIENT)
        assert len(valid) == 2
        assert len(invalid) == 1
        assert invalid[0]["row_index"] == 1

    def test_error_summary_counts(self, service):
        rows = [
            {"name": ""},
            {"name": ""},
            {"name": "Valid"},
        ]
        valid, invalid, summary = service.validate_all(rows, EntityType.CLIENT)
        assert summary.get("Missing required field: 'name'", 0) == 2

    def test_all_valid(self, service):
        rows = [{"name": "A"}, {"name": "B"}, {"name": "C"}]
        valid, invalid, summary = service.validate_all(rows, EntityType.CLIENT)
        assert len(valid) == 3
        assert invalid == []
        assert summary == {}

    def test_with_progress_callback(self, service):
        callback = MagicMock()
        rows = [{"name": str(i)} for i in range(10)]
        valid, invalid, summary = service.validate_all(rows, EntityType.CLIENT, progress_cb=callback)
        callback.assert_called()

    def test_cleaned_row_drops_unknown_fields(self, service):
        rows = [{"name": "Alice", "unknown_col": 42}]
        valid, invalid, summary = service.validate_all(rows, EntityType.CLIENT)
        assert len(valid) == 1
        assert "unknown_col" not in valid[0]
        assert valid[0] == {"name": "Alice"}

    def test_empty_rows(self, service):
        valid, invalid, summary = service.validate_all([], EntityType.CLIENT)
        assert valid == []
        assert invalid == []
        assert summary == {}


# ── Check Duplicates ─────────────────────────────────────────────────────────


class TestCheckDuplicates:
    def test_detects_duplicate_client(self, service, db):
        # Seed a client
        db.conn.execute(
            "INSERT INTO clients (name, vat_number, created_at) VALUES (?, ?, datetime('now'))",
            ("Existing Client", ""),
        )
        db.conn.commit()

        rows = [{"name": "Existing Client"}]
        candidates = service.check_duplicates(rows, EntityType.CLIENT)
        assert len(candidates) == 1
        assert candidates[0].score == 1.0
        assert candidates[0].matched_on == ["name"]

    def test_no_duplicates_returns_empty(self, service):
        rows = [{"name": "Unique Client"}]
        candidates = service.check_duplicates(rows, EntityType.CLIENT)
        assert candidates == []

    def test_with_progress_callback(self, service, db):
        callback = MagicMock()
        rows = [{"name": "Unique"}]
        candidates = service.check_duplicates(rows, EntityType.CLIENT, progress_cb=callback)
        callback.assert_called()


# ── Commit ───────────────────────────────────────────────────────────────────


class TestCommit:
    def test_commit_inserts_rows(self, service, db):
        rows = [{"name": "Test Client", "vat_number": "RO123"}]
        stats = service.commit(rows, EntityType.CLIENT)
        assert stats.committed == 1
        assert stats.total_rows == 1
        assert stats.duplicates_skipped == 0
        assert stats.validation_failures == 0
        # Verify row appears in DB
        result = db.conn.execute(
            "SELECT name, vat_number FROM clients WHERE name = ?", ("Test Client",)
        ).fetchone()
        assert result is not None
        assert result[0] == "Test Client"

    def test_commit_multiple_rows(self, service, db):
        rows = [
            {"name": "Client A"},
            {"name": "Client B"},
            {"name": "Client C"},
        ]
        stats = service.commit(rows, EntityType.CLIENT)
        assert stats.committed == 3
        count = db.conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        assert count == 3

    def test_commit_with_dedup_skip_skips_duplicates(self, service, db):
        # Seed a client
        db.conn.execute(
            "INSERT INTO clients (name, vat_number, created_at) VALUES (?, ?, datetime('now'))",
            ("Existing Client", ""),
        )
        db.conn.commit()

        rows = [{"name": "Existing Client"}, {"name": "New Client"}]
        stats = service.commit(rows, EntityType.CLIENT, dedup_action="skip")
        assert stats.committed == 1  # only new client committed
        assert stats.duplicates_skipped == 1
        count = db.conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        assert count == 2  # seeded (1) + new (1)

    def test_commit_with_dedup_import_ignores_duplicates(self, service, db):
        db.conn.execute(
            "INSERT INTO clients (name, vat_number, created_at) VALUES (?, ?, datetime('now'))",
            ("Existing Client", ""),
        )
        db.conn.commit()

        rows = [{"name": "Existing Client"}]
        stats = service.commit(rows, EntityType.CLIENT, dedup_action="import")
        assert stats.committed == 1  # inserted regardless
        assert stats.duplicates_skipped == 0

    def test_commit_handles_insert_failure(self, service, db):
        """When _fallback_insert raises, the failure is counted in stats."""
        from services.migration.import_service import ImportService
        with patch.object(ImportService, "_fallback_insert", side_effect=RuntimeError("insert fail")):
            rows = [{"name": "Fail Test"}]
            stats = service.commit(rows, EntityType.CLIENT)
        assert stats.committed == 0
        assert stats.validation_failures == 1

    def test_commit_with_progress_callback(self, service, db):
        callback = MagicMock()
        rows = [{"name": "Progress Test"}]
        stats = service.commit(rows, EntityType.CLIENT, progress_cb=callback)
        callback.assert_called()

    def test_commit_empty_rows(self, service):
        stats = service.commit([], EntityType.CLIENT)
        assert stats.committed == 0
        assert stats.total_rows == 0


# ── Import Data (end-to-end) ─────────────────────────────────────────────────


class TestImportData:
    def test_import_data_end_to_end_csv(self, service, db):
        """Full pipeline: preview → validate → commit via import_data()."""
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            f.write("name,vat_number\nAlice,RO001\nBob,RO002\n")
            f.flush()
            path = f.name
        try:
            stats = service.import_data(path, ImportFormat.CSV, EntityType.CLIENT)
            assert isinstance(stats, ImportStats)
            assert stats.total_rows == 2
            assert stats.committed == 2
            assert stats.validation_failures == 0
        finally:
            os.unlink(path)

    def test_import_data_with_mapping(self, service, db):
        """Full pipeline with column mapping."""
        mapping = MappingConfig(
            source_columns=["full_name"],
            target_fields={"full_name": "name"},
            entity_type=EntityType.CLIENT,
        )
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            f.write("full_name,vat_number\nAlice,RO001\n")
            f.flush()
            path = f.name
        try:
            stats = service.import_data(path, ImportFormat.CSV, EntityType.CLIENT, mapping=mapping)
            assert stats.committed == 1
            assert stats.total_rows == 1
        finally:
            os.unlink(path)

    def test_import_data_with_dedup_skip(self, service, db):
        """Pipeline with dedup: duplicate row is skipped."""
        db.conn.execute(
            "INSERT INTO clients (name, vat_number, created_at) VALUES (?, ?, datetime('now'))",
            ("Alice", "RO001"),
        )
        db.conn.commit()

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            f.write("name,vat_number\nAlice,RO001\nBob,RO002\n")
            f.flush()
            path = f.name
        try:
            stats = service.import_data(path, ImportFormat.CSV, EntityType.CLIENT, dedup_action="skip")
            assert stats.committed == 1  # Bob only
            assert stats.duplicates_skipped == 1
            assert stats.total_rows == 2
        finally:
            os.unlink(path)

    def test_import_data_with_progress_callback(self, service, db):
        callback = MagicMock()
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            f.write("name\nTest\n")
            f.flush()
            path = f.name
        try:
            stats = service.import_data(path, ImportFormat.CSV, EntityType.CLIENT, progress_cb=callback)
            assert stats.committed == 1
            callback.assert_called()
        finally:
            os.unlink(path)

    def test_import_data_all_invalid_returns_early(self, service, db):
        """When all rows are invalid, no commit happens."""
        # Use space-only rows: CSV parses them, but validator rejects empty names
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            f.write("name\n \n \n")
            f.flush()
            path = f.name
        try:
            stats = service.import_data(path, ImportFormat.CSV, EntityType.CLIENT)
            assert stats.committed == 0
            assert stats.total_rows == 2
        finally:
            os.unlink(path)

    def test_import_data_json(self, service, db):
        data = [{"name": "Alice"}, {"name": "Bob"}]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            path = f.name
        try:
            stats = service.import_data(path, ImportFormat.JSON, EntityType.CLIENT)
            assert stats.committed == 2
        finally:
            os.unlink(path)

    def test_import_data_returns_import_stats(self, service, db):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            f.write("name\nClient1\n")
            f.flush()
            path = f.name
        try:
            stats = service.import_data(path, ImportFormat.CSV, EntityType.CLIENT)
            assert isinstance(stats, ImportStats)
            assert stats.total_rows >= 1
        finally:
            os.unlink(path)

