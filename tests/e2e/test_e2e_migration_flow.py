"""End-to-end migration flow: import clients/trips → validate → export → verify.

Tests the full round-trip pipeline of ImportService and EmigrateService
using in-memory databases and real file I/O with temporary CSV files.
"""
from __future__ import annotations

import csv
import json
import os
import tempfile
from unittest.mock import ANY, MagicMock

import pytest

from repositories.client_repository import ClientRepository
from repositories.fleet_repository import FleetRepository
from services.migration.emigrate_service import EmigrateService
from services.migration.import_service import ImportService
from services.migration.types import (
    EntityType,
    ExportFormat,
    ImportFormat,
    ImportStage,
    MappingConfig,
)
from tests.test_helpers import make_db

pytestmark = pytest.mark.e2e


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ── Helpers ────────────────────────────────────────────────────────────────

def _write_csv(path: str, headers: list[str], rows: list[list[str]]) -> str:
    """Write a CSV file and return its path."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
    return path


# ── Round-trip tests ───────────────────────────────────────────────────────

class TestRoundTrip:
    """Import → Export → verify data round-trips correctly."""

    def test_full_import_export_roundtrip_client(self, db, tmpdir):
        """Import 3 clients from CSV, export to JSON, verify same 3 records."""
        csv_path = os.path.join(tmpdir, "clients.csv")
        _write_csv(csv_path, ["name", "contact_person", "email"], [
            ["ACME Corp", "John Doe", "john@acme.com"],
            ["Globex Inc", "Jane Doe", "jane@globex.com"],
            ["Initech", "Peter Gibbons", "peter@initech.com"],
        ])

        svc = ImportService(db)
        stats = svc.import_data(
            path=csv_path,
            fmt=ImportFormat.CSV,
            entity_type=EntityType.CLIENT,
        )
        assert stats.committed == 3, f"Expected 3 committed, got {stats.committed}"

        export_path = os.path.join(tmpdir, "clients_export.json")
        export_svc = EmigrateService(db)
        export_svc.export(
            entity_type=EntityType.CLIENT,
            fmt=ExportFormat.JSON,
            output_path=export_path,
        )

        with open(export_path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 3

        exported_names = {row["name"] for row in data}
        assert exported_names == {"ACME Corp", "Globex Inc", "Initech"}

    def test_full_import_export_roundtrip_truck(self, db, tmpdir):
        """Import 2 trucks from CSV, export to JSON, verify same 2 records."""
        csv_path = os.path.join(tmpdir, "trucks.csv")
        _write_csv(csv_path, ["plate_number", "manufacturer", "model"], [
            ["TR-001", "Volvo", "FH16"],
            ["TR-002", "Scania", "R500"],
        ])

        svc = ImportService(db)
        stats = svc.import_data(
            path=csv_path,
            fmt=ImportFormat.CSV,
            entity_type=EntityType.TRUCK,
        )
        assert stats.committed == 2, f"Expected 2 committed, got {stats.committed}"

        export_path = os.path.join(tmpdir, "trucks_export.json")
        export_svc = EmigrateService(db)
        export_svc.export(
            entity_type=EntityType.TRUCK,
            fmt=ExportFormat.JSON,
            output_path=export_path,
        )

        with open(export_path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 2
        exported_plates = {row["plate_number"] for row in data}
        assert exported_plates == {"TR-001", "TR-002"}


# ── Field mapping ──────────────────────────────────────────────────────────

class TestFieldMapping:
    """Field mapping from source column names to target fields."""

    def test_import_with_field_mapping(self, db, tmpdir):
        """CSV column 'nume' mapped to target field 'name'."""
        csv_path = os.path.join(tmpdir, "mapped.csv")
        _write_csv(csv_path, ["nume", "telefon"], [
            ["ACME Corp", "+40721111111"],
            ["Globex Inc", "+40722222222"],
        ])

        mapping = MappingConfig(
            source_columns=["nume", "telefon"],
            target_fields={"nume": "name", "telefon": "phone"},
            entity_type=EntityType.CLIENT,
        )

        svc = ImportService(db)
        stats = svc.import_data(
            path=csv_path,
            fmt=ImportFormat.CSV,
            entity_type=EntityType.CLIENT,
            mapping=mapping,
        )
        assert stats.committed == 2, f"Expected 2 committed, got {stats.committed}"

        # Verify via repository that the mapped field was persisted
        repo = ClientRepository(db)
        client = repo.get_by_name("ACME Corp")
        assert client is not None
        assert client["phone"] == "+40721111111"


# ── Dedup tests ────────────────────────────────────────────────────────────

class TestDuplicateHandling:
    """Duplicate detection and skip behaviour."""

    def test_import_with_duplicate_skip(self, db, tmpdir):
        """Duplicate client is skipped; only new clients are imported."""
        # Seed one existing client
        repo = ClientRepository(db)
        repo.create({"name": "ACME Corp"})

        csv_path = os.path.join(tmpdir, "dedup.csv")
        _write_csv(csv_path, ["name"], [
            ["ACME Corp"],       # duplicate
            ["New Client A"],    # new
            ["New Client B"],    # new
        ])

        svc = ImportService(db)
        stats = svc.import_data(
            path=csv_path,
            fmt=ImportFormat.CSV,
            entity_type=EntityType.CLIENT,
            dedup_action="skip",
        )
        assert stats.committed == 2, f"Expected 2 new clients, got {stats.committed}"
        assert stats.duplicates_skipped == 1, (
            f"Expected 1 duplicate skipped, got {stats.duplicates_skipped}"
        )


# ── Validation tests ───────────────────────────────────────────────────────

class TestValidation:
    """Row-level validation during import."""

    def test_import_validation_rejects_bad_rows(self, db, tmpdir):
        """Invalid row (missing required field) is counted as validation failure."""
        csv_path = os.path.join(tmpdir, "validation.csv")
        _write_csv(csv_path, ["name"], [
            ["Valid Client"],  # valid
            [""],              # invalid: missing name
        ])

        svc = ImportService(db)
        stats = svc.import_data(
            path=csv_path,
            fmt=ImportFormat.CSV,
            entity_type=EntityType.CLIENT,
        )
        assert stats.committed == 1, f"Expected 1 committed, got {stats.committed}"
        assert stats.validation_failures == 1, (
            f"Expected 1 validation failure, got {stats.validation_failures}"
        )


# ── Export field selection ─────────────────────────────────────────────────

class TestExportOptions:
    """Export filtering and field selection."""

    def test_export_field_selection(self, db, tmpdir):
        """Export with field_selection returns only the specified fields."""
        repo = ClientRepository(db)
        for name in ["Alpha Corp", "Beta GmbH", "Gamma SA"]:
            repo.create({"name": name})

        export_path = os.path.join(tmpdir, "selected.json")
        export_svc = EmigrateService(db)
        export_svc.export(
            entity_type=EntityType.CLIENT,
            fmt=ExportFormat.JSON,
            output_path=export_path,
            field_selection=["name"],
        )

        with open(export_path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 3
        for row in data:
            assert list(row.keys()) == ["name"], (
                f"Expected only 'name' field, got {list(row.keys())}"
            )


# ── Counting ───────────────────────────────────────────────────────────────

class TestRecordCounting:
    """Record counting accuracy."""

    def test_count_records_accurate(self, db):
        """count_records returns the correct number of seeded clients."""
        repo = ClientRepository(db)
        for name in [f"Client {i}" for i in range(5)]:
            repo.create({"name": name})

        export_svc = EmigrateService(db)
        count = export_svc.count_records(EntityType.CLIENT)
        assert count == 5, f"Expected 5, got {count}"

        # Empty table should return 0
        db.conn.execute("DELETE FROM clients")
        db.conn.commit()
        count = export_svc.count_records(EntityType.CLIENT)
        assert count == 0, f"Expected 0, got {count}"


# ── Multi-entity import ────────────────────────────────────────────────────

class TestMultiEntity:
    """Importing multiple entity types in sequence."""

    def test_multiple_entity_imports(self, db, tmpdir):
        """Import clients and trucks in sequence; counts are accurate."""
        # Import clients
        csv_clients = os.path.join(tmpdir, "multi_clients.csv")
        _write_csv(csv_clients, ["name"], [
            ["Client A"],
            ["Client B"],
        ])
        svc = ImportService(db)
        stats_c = svc.import_data(
            path=csv_clients,
            fmt=ImportFormat.CSV,
            entity_type=EntityType.CLIENT,
        )
        assert stats_c.committed == 2

        # Import trucks
        csv_trucks = os.path.join(tmpdir, "multi_trucks.csv")
        _write_csv(csv_trucks, ["plate_number"], [
            ["TR-MULTI-1"],
            ["TR-MULTI-2"],
            ["TR-MULTI-3"],
        ])
        stats_t = svc.import_data(
            path=csv_trucks,
            fmt=ImportFormat.CSV,
            entity_type=EntityType.TRUCK,
        )
        assert stats_t.committed == 3

        # Verify counts
        export_svc = EmigrateService(db)
        assert export_svc.count_records(EntityType.CLIENT) == 2
        assert export_svc.count_records(EntityType.TRUCK) == 3


# ── Progress tracking ──────────────────────────────────────────────────────

class TestProgressTracking:
    """Progress callback integration."""

    def test_progress_tracking(self, db, tmpdir):
        """import_data with progress_cb invokes callback with COMPLETE stage."""
        csv_path = os.path.join(tmpdir, "progress.csv")
        _write_csv(csv_path, ["name"], [
            ["Tracker A"],
            ["Tracker B"],
        ])

        progress_cb = MagicMock()
        svc = ImportService(db)
        svc.import_data(
            path=csv_path,
            fmt=ImportFormat.CSV,
            entity_type=EntityType.CLIENT,
            progress_cb=progress_cb,
        )

        # Callback must have been called with the COMPLETE stage
        progress_cb.assert_any_call(ImportStage.COMPLETE.value, 100, ANY)


# ── JSON validity ──────────────────────────────────────────────────────────

class TestExportValidity:
    """Export output correctness."""

    def test_export_json_is_valid(self, db, tmpdir):
        """Exported JSON parses as a valid list."""
        repo = ClientRepository(db)
        for name in ["JSON Corp", "JSON Ltd", "JSON GmbH"]:
            repo.create({"name": name})

        export_path = os.path.join(tmpdir, "valid.json")
        export_svc = EmigrateService(db)
        export_svc.export(
            entity_type=EntityType.CLIENT,
            fmt=ExportFormat.JSON,
            output_path=export_path,
        )

        with open(export_path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list), "Expected JSON array at root"
        assert len(data) == 3, f"Expected 3 records, got {len(data)}"
        for row in data:
            assert "name" in row, f"Row missing 'name' field: {row}"
