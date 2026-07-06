"""Tests for OperationsEngine."""
from unittest.mock import MagicMock, patch

import pytest

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
    assert engine._running is True
    engine._event_bus.publish.assert_called()
    engine._maintenance_engine.evaluate_all.assert_called_once()
    engine._dunner_engine.evaluate_all.assert_called_once()

    engine.stop()
    assert engine._running is False
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
