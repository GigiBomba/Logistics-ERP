"""Tests for MaintenanceEngine."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.operations.alert_manager import AlertType, Severity
from services.operations.maintenance_engine import MaintenanceEngine


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def engine(db_mock):
    eng = MaintenanceEngine(db_mock)
    eng._alert_mgr = MagicMock()
    # Default: no existing active alert → alerts CAN be created.
    eng._alert_mgr.get_active_by_type_and_entity.return_value = None
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
    with patch("services.operations.maintenance_engine.FleetRepository") as mock_fleet_repo:
        mock_fleet_repo_instance = MagicMock()
        mock_fleet_repo.return_value = mock_fleet_repo_instance
        mock_fleet_repo_instance.get_by_id.return_value = {"id": 1, "plate_number": "AB-123"}
        with patch.object(engine, "_evaluate_single", return_value=1) as mock_eval:
            count = engine.evaluate_truck(1)
            assert count == 1


def test_evaluate_truck_not_found(engine):
    with patch("services.operations.maintenance_engine.FleetRepository") as mock_fleet_repo:
        mock_fleet_repo_instance = MagicMock()
        mock_fleet_repo.return_value = mock_fleet_repo_instance
        mock_fleet_repo_instance.get_by_id.return_value = None
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


# ── Driver Hours — additional coverage ────────────────────────────────


def test_evaluate_driver_hours_daily_violation(engine):
    """A driver with violation records triggers a DRIVER_HOURS_DAILY alert."""
    engine._alert_mgr.get_active_by_type_and_entity.return_value = None
    today_str = date.today().isoformat()
    with patch("repositories.driver_repository.DriverRepository") as mock_driver:
        with patch("repositories.tacho_driver_activity_repository.TachoDriverActivityRepository") as mock_tacho:
            mock_driver_repo = MagicMock()
            mock_driver.return_value = mock_driver_repo
            mock_driver_repo.get_active_drivers.return_value = [
                {"id": 1, "name": "Test Driver"},
            ]
            mock_tacho_repo = MagicMock()
            mock_tacho.return_value = mock_tacho_repo
            mock_tacho_repo.get_by_driver.return_value = [
                {"activity_date": today_str, "driving_minutes": 300, "violations": '["Driving > 9h"]'},
            ]
            count = engine.evaluate_driver_hours()
    assert count == 1
    engine._alert_mgr.create_alert.assert_called()
    # _create_driver_alert_if_new uses keyword arguments
    call_kwargs = engine._alert_mgr.create_alert.call_args.kwargs
    assert call_kwargs["alert_type"] == AlertType.DRIVER_HOURS_DAILY


def test_evaluate_driver_hours_weekly_violation(engine):
    """A driver with >56h weekly triggers a CRITICAL DRIVER_HOURS_WEEKLY alert."""
    engine._alert_mgr.get_active_by_type_and_entity.return_value = None
    today_str = date.today().isoformat()
    with patch("repositories.driver_repository.DriverRepository") as mock_driver:
        with patch("repositories.tacho_driver_activity_repository.TachoDriverActivityRepository") as mock_tacho:
            mock_driver_repo = MagicMock()
            mock_driver.return_value = mock_driver_repo
            mock_driver_repo.get_active_drivers.return_value = [
                {"id": 1, "name": "Test Driver"},
            ]
            mock_tacho_repo = MagicMock()
            mock_tacho.return_value = mock_tacho_repo
            mock_tacho_repo.get_by_driver.return_value = [
                {"activity_date": today_str, "driving_minutes": 3420, "violations": "[]"},
            ]
            count = engine.evaluate_driver_hours()
    # 3420 min / 60 = 57h > 56h → CRITICAL
    assert count == 1
    engine._alert_mgr.create_alert.assert_called()
    # _create_driver_alert_if_new uses keyword arguments
    call_kwargs = engine._alert_mgr.create_alert.call_args.kwargs
    assert call_kwargs["alert_type"] == AlertType.DRIVER_HOURS_WEEKLY
    assert call_kwargs["severity"] == Severity.CRITICAL


def test_evaluate_driver_hours_no_violations(engine):
    """Normal driving hours produce no alerts."""
    engine._alert_mgr.get_active_by_type_and_entity.return_value = None
    today_str = date.today().isoformat()
    with patch("repositories.driver_repository.DriverRepository") as mock_driver:
        with patch("repositories.tacho_driver_activity_repository.TachoDriverActivityRepository") as mock_tacho:
            mock_driver_repo = MagicMock()
            mock_driver.return_value = mock_driver_repo
            mock_driver_repo.get_active_drivers.return_value = [
                {"id": 1, "name": "Normal Driver"},
            ]
            mock_tacho_repo = MagicMock()
            mock_tacho.return_value = mock_tacho_repo
            mock_tacho_repo.get_by_driver.return_value = [
                {"activity_date": today_str, "driving_minutes": 480, "violations": "[]"},
            ]
            count = engine.evaluate_driver_hours()
    assert count == 0


# ── Inactive Truck ─────────────────────────────────────────────────────


def test_inactive_truck_triggers_alert(engine):
    """A truck with last activity older than inactive_truck_days → alert created."""
    engine._rules.get.side_effect = lambda key, default=0: {"inactive_truck_days": 30}.get(key, default)
    old_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    truck = {"id": 1, "plate_number": "AB-123"}
    with patch.object(engine, "_ALERT_TYPES_EVALUATED", {AlertType.INACTIVE_TRUCK}):
        with patch("services.operations.maintenance_engine.TripRepository") as mock_trip_repo_cls:
            mock_trip_repo = MagicMock()
            mock_trip_repo_cls.return_value = mock_trip_repo
            mock_trip_repo.get_last_activity_by_truck_id.return_value = f"{old_date} 10:00:00"
            count = engine._evaluate_single(truck)
    assert count == 1
    engine._alert_mgr.create_alert.assert_called_once()
    args = engine._alert_mgr.create_alert.call_args.args
    assert args[0] == AlertType.INACTIVE_TRUCK


# ── Maintenance Schedule Overdue / Due Soon ────────────────────────────


def test_evaluate_single_maintenance_schedule_overdue(engine):
    """A maintenance schedule with overdue flag → CRITICAL alert created."""
    engine._rules.get.side_effect = lambda key, default=0: {"service_km_buffer": 5000}.get(key, default)
    truck = {"id": 1, "plate_number": "AB-123"}
    with patch.object(engine, "_ALERT_TYPES_EVALUATED", set()):
        with patch("services.operations.maintenance_engine.FleetMaintenanceService") as mock_fms_cls:
            mock_fms = MagicMock()
            mock_fms_cls.return_value = mock_fms
            mock_fms.get_schedules.return_value = [{"maintenance_type": "oil_change"}]
            mock_fms.predict_next_service.return_value = {
                "type": "oil_change",
                "overdue": True,
                "due_by_km": 0,
                "remaining_days": -5,
                "remaining_km": 0,
            }
            count = engine._evaluate_single(truck)
    assert count == 1
    engine._alert_mgr.create_alert.assert_called_once()
    args = engine._alert_mgr.create_alert.call_args.args
    assert args[0] == AlertType.MAINTENANCE
    assert args[1] == Severity.CRITICAL


def test_evaluate_single_maintenance_schedule_due_soon(engine):
    """A maintenance schedule with remaining_km < buffer → WARNING alert created."""
    engine._rules.get.side_effect = lambda key, default=0: {"service_km_buffer": 5000}.get(key, default)
    truck = {"id": 1, "plate_number": "AB-123"}
    with patch.object(engine, "_ALERT_TYPES_EVALUATED", set()):
        with patch("services.operations.maintenance_engine.FleetMaintenanceService") as mock_fms_cls:
            mock_fms = MagicMock()
            mock_fms_cls.return_value = mock_fms
            mock_fms.get_schedules.return_value = [{"maintenance_type": "oil_change"}]
            mock_fms.predict_next_service.return_value = {
                "type": "oil_change",
                "overdue": False,
                "remaining_km": 1000,
                "remaining_days": 10,
            }
            count = engine._evaluate_single(truck)
    assert count == 1
    engine._alert_mgr.create_alert.assert_called_once()
    args = engine._alert_mgr.create_alert.call_args.args
    assert args[0] == AlertType.MAINTENANCE
    assert args[1] == Severity.WARNING


# ── Tachograph Calibration Expired ──────────────────────────────────────


def test_tachograph_calibration_expired_creates_alert(engine):
    """Tachograph calibration expired → CRITICAL alert created."""
    old_date = (date.today() - timedelta(days=30)).isoformat()
    truck = {"id": 1, "plate_number": "AB-123"}
    with patch("repositories.tacho_vehicle_data_repository.TachoVehicleDataRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_latest_by_truck.return_value = {
            "calibration_expiry": old_date,
        }
        count = engine.evaluate_tachograph_calibration_for_truck(truck)
    assert count == 1
    engine._alert_mgr.create_alert.assert_called_once()
    args = engine._alert_mgr.create_alert.call_args.args
    assert args[0] == AlertType.TACHOGRAPH_EXPIRY
    assert args[1] == Severity.CRITICAL


# ── Document Expiry Evaluation ─────────────────────────────────────────


def test_document_expiry_evaluation(engine):
    """_evaluate_document_expiries delegates to ExpiryService and returns its count."""
    with patch("repositories.document_repository.DocumentRepository") as mock_doc_repo_cls:
        with patch("services.document.expiry_service.ExpiryService") as mock_expiry_cls:
            mock_expiry = MagicMock()
            mock_expiry_cls.return_value = mock_expiry
            mock_expiry.evaluate_document_expiries.return_value = 3
            count = engine._evaluate_document_expiries()
    assert count == 3
    mock_expiry.evaluate_document_expiries.assert_called_once_with(alert_mgr=engine._alert_mgr)


# ── Stale Alerts Resolution ────────────────────────────────────────────


def test_stale_alerts_get_resolved(engine):
    """An existing inspection alert with no inspection_expiry field → resolved."""
    engine._alert_mgr.get_active_by_type_and_entity.return_value = MagicMock(id="alert-1")
    engine._rules.get.side_effect = lambda key, default=0: {"inspection_warning_days": 10}.get(key, default)
    truck = {"id": 1, "plate_number": "AB-123"}
    # No inspection_expiry key → condition is never added to active_conditions
    with patch.object(engine, "_ALERT_TYPES_EVALUATED", {AlertType.INSPECTION}):
        count = engine._evaluate_single(truck)
    assert count == 0
    # The stale resolution should call resolve_alert for the INSPECTION alert
    engine._alert_mgr.resolve_alert.assert_called_once_with("alert-1")


# ── Date Parsing Fallback ──────────────────────────────────────────────


def test_evaluate_truck_date_parsing_fallback(engine):
    """Malformed inspection_expiry date is caught gracefully, no alert created."""
    engine._alert_mgr.get_active_by_type_and_entity.return_value = None
    engine._rules.get.side_effect = lambda key, default=0: {"inspection_warning_days": 10}.get(key, default)
    truck = {"id": 1, "plate_number": "AB-123", "inspection_expiry": "not-a-date"}
    with patch.object(engine, "_ALERT_TYPES_EVALUATED", set()):
        count = engine._evaluate_single(truck)
    assert count == 0
    engine._alert_mgr.create_alert.assert_not_called()
