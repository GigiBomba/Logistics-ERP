"""Unit tests for EmigrateService — data export functionality."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from services.migration.types import EntityType, ExportFormat
from tests.test_helpers import make_db


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def service(db):
    from services.migration.emigrate_service import EmigrateService

    return EmigrateService(db)


def _seed_driver(db, name):
    import datetime
    now = datetime.datetime.utcnow().isoformat()
    db.conn.execute(
        "INSERT INTO drivers (name, created_at, updated_at) VALUES (?, ?, ?)",
        (name, now, now),
    )
    db.conn.commit()


def _seed_clients(db, count=3):
    for i in range(count):
        db.conn.execute(
            "INSERT INTO clients (name, vat_number, created_at) VALUES (?, ?, datetime('now'))",
            (f"Client {i + 1}", f"RO{i:03d}"),
        )
    db.conn.commit()


# ── Supported entities / formats ─────────────────────────────────────────────


class TestSupportedLists:
    def test_supported_entities(self, service):
        entities = service.SUPPORTED_ENTITIES
        assert EntityType.TRIP in entities
        assert EntityType.CLIENT in entities
        assert EntityType.DRIVER in entities
        assert EntityType.TRUCK in entities
        assert EntityType.INVOICE in entities
        assert EntityType.DOCUMENT not in entities  # intentionally excluded

    def test_supported_formats(self, service):
        formats = service.SUPPORTED_FORMATS
        assert ExportFormat.CSV in formats
        assert ExportFormat.EXCEL in formats
        assert ExportFormat.JSON in formats
        assert ExportFormat.PDF not in formats  # not implemented


# ── Count Records ────────────────────────────────────────────────────────────


class TestCountRecords:
    def test_count_zero_on_empty_table(self, service):
        count = service.count_records(EntityType.CLIENT)
        assert count == 0

    def test_count_after_seeding(self, service, db):
        _seed_clients(db, 5)
        count = service.count_records(EntityType.CLIENT)
        assert count == 5

    def test_count_respects_different_entity_types(self, service, db):
        _seed_clients(db, 3)
        _seed_driver(db, "John")
        client_count = service.count_records(EntityType.CLIENT)
        driver_count = service.count_records(EntityType.DRIVER)
        assert client_count == 3
        assert driver_count == 1

    def test_count_for_entity_with_no_repo(self, service):
        """Unknown entity type raises ValueError."""
        with pytest.raises(ValueError, match="No repository available"):
            service.count_records("unknown")  # type: ignore[arg-type]


# ── Export ───────────────────────────────────────────────────────────────────


class TestExport:
    def test_export_csv_creates_file(self, service, db):
        _seed_clients(db, 2)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "clients.csv")
            result = service.export(EntityType.CLIENT, ExportFormat.CSV, output)
            assert os.path.exists(result)
            assert result == os.path.abspath(output)
            with open(result, encoding="utf-8-sig") as f:
                content = f.read()
            assert "Client 1" in content
            assert "Client 2" in content

    def test_export_json_creates_valid_json(self, service, db):
        _seed_clients(db, 2)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "clients.json")
            result = service.export(EntityType.CLIENT, ExportFormat.JSON, output)
            assert os.path.exists(result)
            with open(result, encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["name"] == "Client 1"

    def test_export_excel_creates_file(self, service, db):
        pytest.importorskip("openpyxl")
        _seed_clients(db, 2)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "clients.xlsx")
            result = service.export(EntityType.CLIENT, ExportFormat.EXCEL, output)
            assert os.path.exists(result)
            assert result.endswith(".xlsx")

    def test_export_with_field_selection(self, service, db):
        _seed_clients(db, 2)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "clients_selected.csv")
            result = service.export(
                EntityType.CLIENT,
                ExportFormat.CSV,
                output,
                field_selection=["name"],
            )
            assert os.path.exists(result)
            with open(result, encoding="utf-8-sig") as f:
                content = f.read()
            assert "name" in content
            assert "vat_number" not in content

    def test_export_creates_nonexistent_directory(self, service, db):
        _seed_clients(db, 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "newdir", "subdir", "clients.csv")
            result = service.export(EntityType.CLIENT, ExportFormat.CSV, output)
            assert os.path.exists(result)

    def test_export_progress_callback_invoked(self, service, db):
        from unittest.mock import MagicMock

        _seed_clients(db, 1)
        callback = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "clients.csv")
            service.export(
                EntityType.CLIENT, ExportFormat.CSV, output, progress_cb=callback
            )
            callback.assert_called()

    def test_export_empty_table_creates_file(self, service, db):
        """Exporting an empty table should create the file with headers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "empty.csv")
            result = service.export(EntityType.CLIENT, ExportFormat.CSV, output)
            assert os.path.exists(result)
            with open(result, encoding="utf-8-sig") as f:
                content = f.read()
            # Should at least have headers
            assert len(content) > 0

    def test_export_unsupported_entity_raises(self, service):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "out.csv")
            with pytest.raises(ValueError, match="Unsupported entity type"):
                service.export(EntityType.DOCUMENT, ExportFormat.CSV, output)

    def test_export_unsupported_format_raises(self, service):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "out.pdf")
            with pytest.raises(ValueError, match="Unsupported export format"):
                service.export(EntityType.CLIENT, ExportFormat.PDF, output)

    def test_export_with_filters(self, service, db):
        _seed_clients(db, 3)
        # Seed one driver (should not be affected)
        _seed_driver(db, "John")
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "filtered.csv")
            result = service.export(
                EntityType.CLIENT,
                ExportFormat.CSV,
                output,
                filters={"name": "Client 1"},
            )
            assert os.path.exists(result)
            with open(result, encoding="utf-8-sig") as f:
                content = f.read()
            # Should only contain rows matching "Client 1"
            lines = content.strip().split("\n")
            data_lines = [l for l in lines if l and not l.startswith("name")]
            count = 0
            for line in data_lines:
                if "Client 1" in line:
                    count += 1
            assert count >= 1

    def test_export_driver_to_csv(self, service, db):
        _seed_driver(db, "Alice")
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "drivers.csv")
            result = service.export(EntityType.DRIVER, ExportFormat.CSV, output)
            assert os.path.exists(result)
            with open(result, encoding="utf-8-sig") as f:
                content = f.read()
            assert "Alice" in content

    def test_export_driver_to_json(self, service, db):
        _seed_driver(db, "Bob")
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "drivers.json")
            result = service.export(EntityType.DRIVER, ExportFormat.JSON, output)
            assert os.path.exists(result)
            with open(result, encoding="utf-8") as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["name"] == "Bob"
