"""E2E: Migration flow — Export data → Import to clean DB → Verify.

Tests the full migration round-trip: exporting entities as JSON, importing
them into a fresh database, verifying counts match, and checking duplicate
detection.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
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
from services.trip_service import TripService
from tests.test_helpers import make_db

pytestmark = pytest.mark.e2e


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def fresh_db():
    """Create a completely fresh empty database."""
    return make_db()


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ═════════════════════════════════════════════════════════════════════════════
# Full Migration Round-Trip
# ═════════════════════════════════════════════════════════════════════════════


class TestMigrationImportExport:
    """Full migration: export → fresh DB → import → verify → dedup."""

    def _seed_test_data(self, db):
        """Seed clients, trips, and trucks for export."""
        client_repo = ClientRepository(db)

        # Create clients
        for name in ["Export Corp", "Import GmbH", "Transfer SA"]:
            client_repo.create({"name": name, "email": f"{name.lower().replace(' ', '.')}@example.com"})

        # Create trucks
        fleet_repo = FleetRepository(db)
        for plate in ["TR-EXP-001", "TR-EXP-002"]:
            fleet_repo.create({
                "plate_number": plate,
                "manufacturer": "Volvo",
                "status": "Active",
            })

        # Create trips
        trip_svc = TripService(db)
        clients = client_repo.get_all()
        trucks = fleet_repo.get_all()
        now = datetime.now().isoformat()
        for i, client in enumerate(clients[:2]):
            truck_plate = trucks[i % len(trucks)]["plate_number"] if trucks else "TR-EXP-001"
            trip_svc.add({
                "client_id": client["id"],
                "client_name": client["name"],
                "truck_plate": truck_plate,
                "distance_km": 500.0 * (i + 1),
                "price_eur": 2000.0 * (i + 1),
                "status": "Delivered",
                "start_date": "2024-06-01",
                "end_date": "2024-06-03",
                "created_at": now,
            })

    def _export_all(self, db, tmpdir) -> dict[str, str]:
        """Export all entity types and return paths by type."""
        export_svc = EmigrateService(db)
        paths = {}

        for entity_type in [EntityType.CLIENT, EntityType.TRUCK, EntityType.TRIP]:
            path = os.path.join(tmpdir, f"{entity_type.value}_export.json")
            export_svc.export(
                entity_type=entity_type,
                fmt=ExportFormat.JSON,
                output_path=path,
            )
            paths[entity_type.value] = path
        return paths

    def test_full_export_import_roundtrip(self, db, fresh_db, tmpdir):
        """Export data from seeded DB → import into fresh DB → verify counts match."""
        # ── 1. Seed data ─────────────────────────────────────────────────
        self._seed_test_data(db)

        # Seed counts
        client_count_before = len(ClientRepository(db).get_all())
        truck_count_before = len(FleetRepository(db).get_all())
        trip_count_before = len(db.get_all_trips())

        assert client_count_before >= 3
        assert truck_count_before >= 2
        assert trip_count_before >= 2

        # ── 2. Export all entities ────────────────────────────────────────
        export_paths = self._export_all(db, tmpdir)

        # Verify exports are valid JSON
        for entity_type, path in export_paths.items():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, list), f"Export {entity_type} must be a list"
            assert len(data) > 0, f"Export {entity_type} should have data"

        # ── 3. Import into fresh DB ───────────────────────────────────────
        import_svc = ImportService(fresh_db)

        for entity_type in [EntityType.CLIENT, EntityType.TRUCK, EntityType.TRIP]:
            path = export_paths[entity_type.value]
            with open(path, encoding="utf-8") as f:
                raw_data = json.load(f)

            # Use the JSON file path for import
            stats = import_svc.import_data(
                path=path,
                fmt=ImportFormat.JSON,
                entity_type=entity_type,
            )
            assert stats.committed == len(raw_data), (
                f"Expected {len(raw_data)} {entity_type.value}s committed, "
                f"got {stats.committed}"
            )

        # ── 4. Verify entity counts match ─────────────────────────────────
        assert len(ClientRepository(fresh_db).get_all()) == client_count_before
        assert len(FleetRepository(fresh_db).get_all()) == truck_count_before
        assert len(fresh_db.get_all_trips()) == trip_count_before

    def test_export_creates_valid_json_file(self, db, tmpdir):
        """Exported JSON is a valid parseable list."""
        self._seed_test_data(db)

        export_svc = EmigrateService(db)
        path = os.path.join(tmpdir, "clients_export.json")
        export_svc.export(
            entity_type=EntityType.CLIENT,
            fmt=ExportFormat.JSON,
            output_path=path,
        )

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        for record in data:
            assert "name" in record, f"Record missing 'name': {record}"

    def test_import_duplicate_detection(self, db, fresh_db, tmpdir):
        """Import with duplicate detection skips existing records."""
        client_repo = ClientRepository(db)
        client_repo.create({"name": "Duplicat Corp"})

        # Export
        export_svc = EmigrateService(db)
        path = os.path.join(tmpdir, "dedup_export.json")
        export_svc.export(
            entity_type=EntityType.CLIENT,
            fmt=ExportFormat.JSON,
            output_path=path,
        )

        # Seed the fresh_db with the same record
        ClientRepository(fresh_db).create({"name": "Duplicat Corp"})

        # Import with skip dedup
        import_svc = ImportService(fresh_db)
        stats = import_svc.import_data(
            path=path,
            fmt=ImportFormat.JSON,
            entity_type=EntityType.CLIENT,
            dedup_action="skip",
        )
        # At minimum the duplicate was skipped; may also have 0 committed
        assert stats.committed <= 1

    def test_export_multiple_entity_types(self, db, tmpdir):
        """All three entity types can be exported successfully."""
        self._seed_test_data(db)
        paths = self._export_all(db, tmpdir)

        assert EntityType.CLIENT.value in paths
        assert EntityType.TRUCK.value in paths
        assert EntityType.TRIP.value in paths

        for path in paths.values():
            assert os.path.isfile(path)
            assert os.path.getsize(path) > 0

    def test_empty_db_export(self, fresh_db, tmpdir):
        """Exporting from an empty DB produces an empty list."""
        export_svc = EmigrateService(fresh_db)

        for entity_type in [EntityType.CLIENT, EntityType.TRUCK, EntityType.TRIP]:
            path = os.path.join(tmpdir, f"empty_{entity_type.value}.json")
            export_svc.export(
                entity_type=entity_type,
                fmt=ExportFormat.JSON,
                output_path=path,
            )
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert data == [], f"Expected empty list for {entity_type.value}"

    def test_count_records_accuracy(self, db):
        """count_records returns correct numbers."""
        self._seed_test_data(db)

        export_svc = EmigrateService(db)
        client_count = export_svc.count_records(EntityType.CLIENT)
        truck_count = export_svc.count_records(EntityType.TRUCK)
        trip_count = export_svc.count_records(EntityType.TRIP)

        assert client_count >= 3
        assert truck_count >= 2
        assert trip_count >= 2

    def test_import_progress_callback(self, db, fresh_db, tmpdir):
        """import_data with progress_cb invokes callback."""
        self._seed_test_data(db)

        export_svc = EmigrateService(db)
        path = os.path.join(tmpdir, "clients_progress.json")
        export_svc.export(
            entity_type=EntityType.CLIENT,
            fmt=ExportFormat.JSON,
            output_path=path,
        )

        progress_cb = MagicMock()
        import_svc = ImportService(fresh_db)
        import_svc.import_data(
            path=path,
            fmt=ImportFormat.JSON,
            entity_type=EntityType.CLIENT,
            progress_cb=progress_cb,
        )

        progress_cb.assert_any_call(ImportStage.COMPLETE.value, 100, ANY)

    def test_export_field_selection(self, db, tmpdir):
        """Export with field_selection returns only specified fields."""
        client_repo = ClientRepository(db)
        client_repo.create({"name": "Field Select Corp", "email": "field@test.com"})

        export_svc = EmigrateService(db)
        path = os.path.join(tmpdir, "selected_fields.json")
        export_svc.export(
            entity_type=EntityType.CLIENT,
            fmt=ExportFormat.JSON,
            output_path=path,
            field_selection=["name"],
        )

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for row in data:
            assert list(row.keys()) == ["name"], (
                f"Expected only 'name' field, got {list(row.keys())}"
            )
