"""Tests for OperationsEngine."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.operations.alert_manager import Alert, AlertType, Severity
from services.operations.operations_engine import OperationsEngine


@pytest.fixture
def db_mock():
    return MagicMock()


def test_singleton(db_mock):
    e1 = OperationsEngine(db_mock)
    e2 = OperationsEngine(db_mock)
    assert e1 is e2


def test_initialized_once(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    assert engine._initialized is True
    assert engine._db is db_mock
    assert engine._event_bus is not None
    assert engine._alert_mgr is not None


def test_initialized_without_db():
    OperationsEngine._instance = None
    engine = OperationsEngine(db=None)
    assert engine._initialized is True
    assert engine._db is None
    assert engine._trip_service is None
    assert engine._maintenance_engine is None


def test_undo_redo(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    # Mock undo stack
    mock_cmd = MagicMock()
    mock_cmd.trip_id = 1
    mock_cmd.old_status = "Draft"
    mock_cmd.new_status = "In Transit"
    engine._undo_stack = MagicMock()
    engine._undo_stack.undo.return_value = mock_cmd
    engine._trip_workflow = MagicMock()
    engine._trip_workflow.force_trip_status.return_value = True

    result = engine.undo_last()
    assert result is True
    engine._trip_workflow.force_trip_status.assert_called_with(1, "Draft", skip_undo=True)

    engine._undo_stack.redo.return_value = mock_cmd
    result = engine.redo_last()
    assert result is True
    engine._trip_workflow.force_trip_status.assert_called_with(1, "In Transit", skip_undo=True)


def test_undo_no_command(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._undo_stack = MagicMock()
    engine._undo_stack.undo.return_value = None
    assert engine.undo_last() is False


def test_start_stop(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._maintenance_engine = MagicMock()
    engine._dunner_engine = MagicMock()
    engine._cmr_generator = MagicMock()

    engine._event_bus = MagicMock()
    engine.start()
    assert not engine._stop_event.is_set()
    engine._event_bus.publish.assert_called()
    engine._maintenance_engine.evaluate_all.assert_called_once()
    engine._dunner_engine.evaluate_all.assert_called_once()

    engine.stop()
    assert engine._stop_event.is_set()
    engine._dunner_engine.shutdown.assert_called_once()


def test_get_active_alerts(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._alert_mgr = MagicMock()
    engine._alert_mgr.get_active_alerts.return_value = [{"id": "1"}]
    assert engine.get_active_alerts() == [{"id": "1"}]


def test_get_alerts(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._alert_mgr = MagicMock()
    result = engine.get_alerts(limit=50)
    engine._alert_mgr.get_alerts.assert_called_with(
        alert_type=None, severity=None, truck_id=None, resolved=None, limit=50,
    )


def test_resolve_alert(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._alert_mgr = MagicMock()
    engine.resolve_alert("alert-1")
    engine._alert_mgr.resolve_alert.assert_called_with("alert-1")


def test_get_active_count(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._alert_mgr = MagicMock()
    engine._alert_mgr.get_active_count.return_value = 5
    assert engine.get_active_count() == 5
    assert engine.get_active_alert_count() == 5


def test_evaluate_all(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._maintenance_engine = MagicMock()
    engine._maintenance_engine.evaluate_all.return_value = 3
    assert engine.evaluate_all() == 3


def test_evaluate_truck(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._maintenance_engine = MagicMock()
    engine._maintenance_engine.evaluate_truck.return_value = 2
    assert engine.evaluate_truck("1") == 2


def test_get_valid_transitions(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._trip_workflow = MagicMock()
    engine._trip_workflow.get_valid_transitions.return_value = ["In Transit"]
    assert engine.get_valid_transitions("Draft") == ["In Transit"]


def test_get_valid_transitions_no_workflow(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._trip_workflow = None
    assert engine.get_valid_transitions("Draft") == []


def test_force_trip_status(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._trip_workflow = MagicMock()
    engine._trip_workflow.force_trip_status.return_value = True
    assert engine.force_trip_status(1, "In Transit") is True


def test_properties(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    assert engine.alert_manager is engine._alert_mgr
    assert engine.event_bus is engine._event_bus
    assert engine.notification_center is engine._notification_center
    assert engine.undo_stack is engine._undo_stack


def test_migrate_existing_data(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._maintenance_engine = MagicMock()
    engine._trip_service = MagicMock()
    engine._trip_service.get_by_statuses.return_value = []
    result = engine.migrate_existing_data()
    assert "trucks" in result
    assert "trips" in result


def test_force_trip_status_no_workflow(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._trip_workflow = None
    assert engine.force_trip_status(1, "In Transit") is False


def test_evaluate_all_no_maintenance():
    OperationsEngine._instance = None
    engine = OperationsEngine(db=None)
    assert engine.evaluate_all() == 0


def test_evaluate_truck_no_maintenance():
    OperationsEngine._instance = None
    engine = OperationsEngine(db=None)
    assert engine.evaluate_truck("T1") == 0


def test_start_without_db():
    OperationsEngine._instance = None
    engine = OperationsEngine(db=None)
    engine._event_bus = MagicMock()
    engine._cmr_generator = MagicMock()
    engine.start()
    assert not engine._stop_event.is_set()
    engine.stop()
    assert engine._stop_event.is_set()


def test_get_active_alerts_limit(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._alert_mgr = MagicMock()
    engine._alert_mgr.get_active_alerts.return_value = [{"id": "1"}]
    result = engine.get_active_alerts(limit=10)
    engine._alert_mgr.get_active_alerts.assert_called_with(limit=10)
    assert result == [{"id": "1"}]


def test_get_alerts_with_all_filters(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    engine._alert_mgr = MagicMock()
    engine.get_alerts(
        alert_type=AlertType.MAINTENANCE,
        severity=Severity.CRITICAL,
        truck_id="T1",
        resolved=False,
        limit=25,
    )
    engine._alert_mgr.get_alerts.assert_called_with(
        alert_type=AlertType.MAINTENANCE,
        severity=Severity.CRITICAL,
        truck_id="T1",
        resolved=False,
        limit=25,
    )


def test_migrate_existing_data_with_overdue_invoices():
    """Integration test: migrate_existing_data creates overdue invoice alerts."""
    from tests.test_helpers import make_db

    OperationsEngine._instance = None
    db = make_db()
    # Insert a truck
    db.conn.execute(
        "INSERT INTO trucks (id, plate_number) VALUES (1, 'ABC-123')"
    )
    # Insert a delivered trip with an unpaid invoice past due
    db.conn.execute(
        "INSERT INTO trips (id, status, client_name, total_price_eur, created_at) "
        "VALUES (1, 'Delivered', 'ACME', 1500.00, '2025-01-15')"
    )
    db.conn.execute(
        "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
        "VALUES (1, 'INV-001', '2025-01-15', '2025-02-14', 1500.00, 'Unpaid')"
    )
    db.conn.commit()

    engine = OperationsEngine(db)
    engine._maintenance_engine = MagicMock()
    engine._event_bus = MagicMock()

    result = engine.migrate_existing_data()
    assert result["trips"] >= 1
    # Overdue invoices alert should have been created
    active = engine.get_active_alerts()
    overdue = [a for a in active if a.type == AlertType.OVERDUE_INVOICE]
    assert len(overdue) >= 1
    assert "INV-001" in overdue[0].message or "1500" in overdue[0].message


def test_migrate_existing_data_no_db():
    OperationsEngine._instance = None
    engine = OperationsEngine(db=None)
    result = engine.migrate_existing_data()
    assert result == {"trucks": 0, "trips": 0, "overdue_invoices": 0}


def test_alert_manager_delegation(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    assert engine.alert_manager is engine._alert_mgr


def test_event_bus_delegation(db_mock):
    OperationsEngine._instance = None
    engine = OperationsEngine(db_mock)
    assert engine.event_bus is engine._event_bus
