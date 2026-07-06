"""Tests for AutoCMRGenerator service."""
from unittest.mock import MagicMock, call, patch

import pytest

from services.operations.cmr_auto_generator import AutoCMRGenerator


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.conn = MagicMock()
    return db


@pytest.fixture
def mock_prefs():
    return MagicMock()


@pytest.fixture
def mock_alert_mgr():
    return MagicMock()


@pytest.fixture
def generator(mock_db, mock_prefs, mock_alert_mgr):
    return AutoCMRGenerator(db=mock_db, prefs=mock_prefs, alert_mgr=mock_alert_mgr)


class TestOnTripInTransit:
    def test_in_transit_triggers_generation(self, generator):
        generator.generate = MagicMock()
        ev = {
            "data": {
                "new_status": "In Transit",
                "trip_id": 42,
            }
        }
        generator.on_trip_in_transit(ev)
        # generate should be called in a thread - wait briefly
        import time
        time.sleep(0.1)
        assert generator.generate.called

    def test_other_status_ignored(self, generator):
        generator.generate = MagicMock()
        ev = {
            "data": {
                "new_status": "Planned",
                "trip_id": 42,
            }
        }
        generator.on_trip_in_transit(ev)
        generator.generate.assert_not_called()

    def test_missing_trip_id_ignored(self, generator):
        generator.generate = MagicMock()
        ev = {"data": {"new_status": "In Transit"}}
        generator.on_trip_in_transit(ev)
        generator.generate.assert_not_called()

    def test_all_transit_aliases(self, generator):
        generator.generate = MagicMock(return_value=None)
        aliases = ["In Transit", "InTransit", "Active", "InProgress"]
        for alias in aliases:
            ev = {"data": {"new_status": alias, "trip_id": 1}}
            generator.on_trip_in_transit(ev)
        import time
        time.sleep(0.2)
        assert generator.generate.call_count == len(aliases)


class TestGenerate:
    def test_generate_no_db(self, generator):
        gen = AutoCMRGenerator(db=None, prefs=MagicMock(), alert_mgr=MagicMock())
        gen.generate(42)  # should not raise

    def test_generate_trip_not_found(self, generator):
        with patch("services.trip_service.TripService") as mock_ts_cls:
            mock_ts = MagicMock()
            mock_ts.get_by_id.return_value = None
            mock_ts_cls.return_value = mock_ts
            generator.generate(42)  # should not raise

    def test_generate_skips_if_cmr_exists(self, generator):
        with patch("services.trip_service.TripService") as mock_ts_cls, \
             patch("services.document_service.DocumentService") as mock_ds_cls:
            mock_ts = MagicMock()
            mock_ts.get_by_id.return_value = {"id": 42}
            mock_ts_cls.return_value = mock_ts

            mock_ds = MagicMock()
            mock_ds.get_documents_for_entity.return_value = [
                {"tags": ["cmr", "auto-generated"]},
            ]
            mock_ds_cls.return_value = mock_ds

            generator.generate(42)
            mock_ds.register_existing.assert_not_called()

    def test_generate_skips_if_missing_cargo_data(self, generator, mock_alert_mgr):
        with patch("services.trip_service.TripService") as mock_ts_cls:
            mock_ts = MagicMock()
            mock_ts.get_by_id.return_value = {
                "id": 42,
                "cargo_description": "",
                "gross_weight_kg": None,
            }
            mock_ts_cls.return_value = mock_ts

            generator.generate(42)
            mock_alert_mgr.create_alert.assert_called_once()

    def test_generate_success(self, generator, mock_db, mock_alert_mgr):
        trip_data = {
            "id": 42,
            "cargo_description": "Electronics",
            "gross_weight_kg": 15000,
            "truck_number": "AB123CD",
            "driver_id": 1,
            "truck_id": 1,
            "client_id": 1,
            "cmr_number": "CMR-001",
            "driver_name": "John Doe",
        }

        with patch("services.trip_service.TripService") as mock_ts_cls, \
             patch("services.document_service.DocumentService") as mock_ds_cls, \
             patch("services.invoicing.cmr_generator.CMRGenerator") as mock_cmr_cls, \
             patch("services.operations.cmr_auto_generator.DriverRepository") as mock_driver_cls, \
             patch("services.operations.cmr_auto_generator.FleetRepository") as mock_fleet_cls, \
             patch("services.operations.cmr_auto_generator.ClientRepository") as mock_client_cls, \
             patch("os.makedirs"):

            mock_ts = MagicMock()
            mock_ts.get_by_id.return_value = trip_data
            mock_ts_cls.return_value = mock_ts

            mock_ds = MagicMock()
            mock_ds.get_documents_for_entity.return_value = []
            mock_ds_cls.return_value = mock_ds

            mock_cmr = MagicMock()
            mock_cmr.generate_all_copies.return_value = {
                "original": "/tmp/cmr_original.pdf",
                "copy1": "/tmp/cmr_copy1.pdf",
                "copy2": "/tmp/cmr_copy2.pdf",
                "copy3": "/tmp/cmr_copy3.pdf",
            }
            mock_cmr_cls.return_value = mock_cmr

            # Mock DriverRepository, FleetRepository, ClientRepository lookups
            mock_driver = MagicMock()
            mock_driver.get_by_id_with_adr.return_value = {"name": "John", "adr_certificate_expiry": "2030-01-01"}
            mock_driver.get_by_id.return_value = {"id": 1, "license_number": "LIC123", "name": "Driver John"}
            mock_driver_cls.return_value = mock_driver

            mock_fleet = MagicMock()
            mock_fleet.get_by_id.return_value = {"id": 1, "trailer_plate": "TR456", "cmr_insurance_number": "INS789"}
            mock_fleet_cls.return_value = mock_fleet

            mock_client = MagicMock()
            mock_client.get_by_id.return_value = {"id": 1, "vat_number": "RO123", "eori_number": "EORI456"}
            mock_client_cls.return_value = mock_client

            generator.generate(42)

            # Should register 4 CMR copies
            assert mock_ds.register_existing.call_count == 4

    def test_generate_adr_expired_blocks(self, generator, mock_db, mock_alert_mgr):
        trip_data = {
            "id": 42,
            "cargo_description": "ADR Materials",
            "gross_weight_kg": 5000,
            "adr_info_json": "some_adr_info",
            "driver_id": 1,
        }

        with patch("services.trip_service.TripService") as mock_ts_cls, \
             patch("services.document_service.DocumentService") as mock_ds_cls, \
             patch("services.operations.cmr_auto_generator.DriverRepository") as mock_driver_cls:
            mock_ts = MagicMock()
            mock_ts.get_by_id.return_value = trip_data
            mock_ts_cls.return_value = mock_ts

            mock_ds = MagicMock()
            mock_ds.get_documents_for_entity.return_value = []
            mock_ds_cls.return_value = mock_ds

            # Expired ADR certificate
            from datetime import datetime, timedelta
            expired_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

            mock_driver = MagicMock()
            mock_driver.get_by_id_with_adr.return_value = {"name": "Driver", "adr_certificate_expiry": expired_date}
            mock_driver_cls.return_value = mock_driver

            generator.generate(42)
            mock_alert_mgr.create_alert.assert_called_once()
