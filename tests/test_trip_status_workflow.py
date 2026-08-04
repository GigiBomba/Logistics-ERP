"""Tests for TripStatusWorkflow."""
from unittest.mock import MagicMock, patch

import pytest

from models.trip_models import TripUpdate
from services.operations.trip_status_workflow import TripStatusWorkflow


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def workflow(db_mock):
    trip_service = MagicMock()
    event_bus = MagicMock()
    maintenance_engine = MagicMock()
    undo_stack = MagicMock()
    return TripStatusWorkflow(db_mock, trip_service, event_bus, maintenance_engine, undo_stack)


def test_get_valid_transitions(workflow):
    transitions = workflow.get_valid_transitions("Draft")
    assert isinstance(transitions, list)


def test_get_valid_transitions_unknown(workflow):
    transitions = workflow.get_valid_transitions("NonExistent")
    assert transitions == []


def test_force_trip_status_no_trip_service(workflow):
    workflow._trip_service = None
    result = workflow.force_trip_status(1, "In Transit")
    assert result is False


def test_force_trip_status_trip_not_found(workflow):
    workflow._trip_service.get_by_id.return_value = None
    result = workflow.force_trip_status(999, "In Transit")
    assert result is False


def test_force_trip_status_same_status(workflow):
    workflow._trip_service.get_by_id.return_value = {"id": 1, "status": "In Transit"}
    result = workflow.force_trip_status(1, "In Transit")
    assert result is True


@patch.object(TripStatusWorkflow, "_update_truck_odometer_on_completion")
def test_force_trip_status_valid_transition(mock_odo, workflow):
    workflow._trip_service.get_by_id.return_value = {
        "id": 1, "status": "In Transit", "truck_id": 1, "distance_km": 500,
    }
    result = workflow.force_trip_status(1, "Delivered")
    assert result is True
    workflow._trip_service.update.assert_called_with(1, TripUpdate(status="Delivered"))
    workflow._event_bus.publish.assert_called_once()
    mock_odo.assert_called_once()


def test_force_trip_status_invalid_transition(workflow):
    workflow._trip_service.get_by_id.return_value = {"id": 1, "status": "Draft"}
    result = workflow.force_trip_status(1, "Completed")
    # This depends on VALID_TRANSITIONS content, but "Draft" → "Completed" may be invalid
    # We just check it returns False if invalid
    valid = workflow.get_valid_transitions("Draft")
    if "Completed" not in valid:
        assert result is False
    else:
        assert result is True


def test_update_truck_odometer_on_completion(workflow):
    trip = {"id": 1, "truck_id": 1, "truck_number": "AB-123", "distance_km": 500}
    with patch("repositories.fleet_repository.FleetRepository") as mock_fleet_repo:
        fleet_repo_instance = MagicMock()
        mock_fleet_repo.return_value = fleet_repo_instance
        fleet_repo_instance.get_by_id.return_value = {"id": 1, "plate_number": "AB-123", "mileage": 10000}
        workflow._update_truck_odometer_on_completion(trip)
        fleet_repo_instance.update.assert_called_with(1, {"mileage": 10500})
        workflow._event_bus.publish.assert_called_once()
        publish_args = workflow._event_bus.publish.call_args[0][1]
        assert publish_args["added_km"] == 500
        assert publish_args["previous_km"] == 10000
        assert publish_args["new_total_km"] == 10500


def test_update_truck_odometer_no_distance(workflow):
    trip = {"id": 1, "distance_km": 0}
    workflow._update_truck_odometer_on_completion(trip)
    workflow._event_bus.publish.assert_not_called()


def test_update_truck_odometer_no_truck(workflow):
    trip = {"id": 1, "truck_id": 999, "distance_km": 500}
    with patch("repositories.fleet_repository.FleetRepository") as mock_fleet_repo:
        fleet_repo_instance = MagicMock()
        mock_fleet_repo.return_value = fleet_repo_instance
        fleet_repo_instance.get_by_id.return_value = None
        fleet_repo_instance.get_by_plate.return_value = None
        workflow._update_truck_odometer_on_completion(trip)
        workflow._event_bus.publish.assert_not_called()
