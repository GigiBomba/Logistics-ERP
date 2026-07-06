"""Tests for MaintenanceEngine."""
from unittest.mock import MagicMock, patch

import pytest

from services.operations.maintenance_engine import MaintenanceEngine


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def engine(db_mock):
    eng = MaintenanceEngine(db_mock)
    eng._alert_mgr = MagicMock()
    eng._event_bus = MagicMock()
    eng._rules = MagicMock()
    return eng


def test_evaluate_all(engine):
    engine._db.get_all_trucks.return_value = [
        {"id": 1, "plate_number": "AB-123"},
    ]
    with patch.object(engine, "_evaluate_single", return_value=2) as mock_eval:
        with patch.object(engine, "evaluate_driver_hours", return_value=0):
            with patch.object(engine, "_evaluate_document_expiries", return_value=0):
                with patch.object(engine, "_evaluate_contract_expiries", return_value=0):
                    count = engine.evaluate_all()
                    assert count == 2


def test_evaluate_truck(engine):
    engine._db.get_truck_by_id.return_value = {"id": 1, "plate_number": "AB-123"}
    with patch.object(engine, "_evaluate_single", return_value=1) as mock_eval:
        count = engine.evaluate_truck(1)
        assert count == 1


def test_evaluate_truck_not_found(engine):
    engine._db.get_truck_by_id.return_value = None
    with patch.object(engine, "_evaluate_single") as mock_eval:
        count = engine.evaluate_truck(999)
        assert count == 0
        mock_eval.assert_not_called()


def test_evaluate_single_inspection_expired(engine):
    engine._rules.get.side_effect = lambda key, default=0: {"inspection_warning_days": 10}.get(key, default)
    truck = {"id": 1, "plate_number": "AB-123", "inspection_expiry": "2020-01-01"}
    with patch.object(engine, "_ALERT_TYPES_EVALUATED", set()):
        count = engine._evaluate_single(truck)
    assert count == 1
    engine._alert_mgr.create_alert.assert_called()


def test_evaluate_single_insurance_expired(engine):
    engine._rules.get.side_effect = lambda key, default=0: {"insurance_warning_days": 10}.get(key, default)
    truck = {"id": 1, "plate_number": "AB-123", "insurance_expiry": "2020-01-01"}
    with patch.object(engine, "_ALERT_TYPES_EVALUATED", set()):
        count = engine._evaluate_single(truck)
    assert count == 1
    engine._alert_mgr.create_alert.assert_called()


def test_evaluate_single_inspection_warning(engine):
    from datetime import datetime, timedelta
    future = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    engine._rules.get.side_effect = lambda key, default=0: {"inspection_warning_days": 10}.get(key, default)
    truck = {"id": 1, "plate_number": "AB-123", "inspection_expiry": future}
    with patch.object(engine, "_ALERT_TYPES_EVALUATED", set()):
        count = engine._evaluate_single(truck)
    assert count == 1


def test_event_handlers(engine):
    engine._event_bus = MagicMock()
    # Test subscribe/shutdown
    engine._subscribe()
    assert engine._event_bus.subscribe.called
    engine.shutdown()
    assert engine._event_bus.unsubscribe.called


def test_on_truck_event(engine):
    engine.evaluate_truck = MagicMock()
    engine._on_truck_event({"data": {"truck_id": 1}})
    engine.evaluate_truck.assert_called_with(1)


def test_on_maintenance_event(engine):
    engine.evaluate_truck = MagicMock()
    engine._on_maintenance_event({"data": {"truck_id": 1}})
    engine.evaluate_truck.assert_called_with(1)


def test_on_daily_check(engine):
    engine.evaluate_all = MagicMock()
    engine._on_daily_check({})
    engine.evaluate_all.assert_called_once()


def test_driver_hours_evaluation(engine):
    engine._alert_mgr.get_active_by_type_and_entity.return_value = None
    engine._db.conn.execute.return_value.fetchall.return_value = []
    with patch("repositories.tacho_driver_activity_repository.TachoDriverActivityRepository") as mock_tacho:
        with patch("repositories.driver_repository.DriverRepository") as mock_driver:
            mock_driver_repo = MagicMock()
            mock_driver.return_value = mock_driver_repo
            mock_driver_repo.get_active_drivers.return_value = []
            count = engine.evaluate_driver_hours()
            assert count == 0
