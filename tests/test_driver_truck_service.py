"""Tests for DriverTruckService."""
from unittest.mock import MagicMock, patch

import pytest

from services.driver_truck_service import DriverTruckService
from services.operations.event_bus import TRUCK_UPDATED


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock):
    svc = DriverTruckService(db_mock)
    svc._repo = MagicMock()
    svc._fleet_repo = MagicMock()
    svc._driver_repo = MagicMock()
    svc._event_bus = MagicMock()
    return svc


def test_assign_driver_to_truck_fresh(service):
    service._repo.get_by_driver.return_value = None
    service._repo.get_by_truck.return_value = None

    result = service.assign_driver_to_truck(1, 10)

    assert result["action"] == "assigned"
    assert result["swapped_driver"] is None
    service._repo.assign.assert_called_with(1, 10)
    service._event_bus.publish.assert_called_once()


def test_assign_driver_to_truck_reassign(service):
    service._repo.get_by_driver.return_value = {"driver_id": 1, "truck_id": 5}
    service._repo.get_by_truck.return_value = None

    result = service.assign_driver_to_truck(1, 10)

    assert result["action"] == "reassigned"
    service._repo.unassign_driver.assert_called_with(1)


def test_assign_driver_to_truck_swap(service):
    service._repo.get_by_driver.return_value = None
    service._repo.get_by_truck.return_value = {"driver_id": 2, "truck_id": 10}

    result = service.assign_driver_to_truck(1, 10)

    assert result["action"] == "swapped"
    assert result["swapped_driver"] == 2
    service._repo.unassign_truck.assert_called_with(10)


def test_assign_driver_publishes_event(service):
    service._repo.get_by_driver.return_value = None
    service._repo.get_by_truck.return_value = None
    service.assign_driver_to_truck(1, 10)
    service._event_bus.publish.assert_called_with(TRUCK_UPDATED, {
        "truck_id": 10, "driver_id": 1, "action": "assigned",
    })


def test_unassign_driver_exists(service):
    service._repo.get_by_driver.return_value = {"driver_id": 1, "truck_id": 10}
    result = service.unassign_driver(1)
    assert result == 10
    service._repo.unassign_driver.assert_called_with(1)
    service._event_bus.publish.assert_called_once()


def test_unassign_driver_not_found(service):
    service._repo.get_by_driver.return_value = None
    result = service.unassign_driver(1)
    assert result is None
    service._repo.unassign_driver.assert_not_called()


def test_unassign_truck_exists(service):
    service._repo.get_by_truck.return_value = {"driver_id": 1, "truck_id": 10}
    result = service.unassign_truck(10)
    assert result == 1
    service._repo.unassign_truck.assert_called_with(10)


def test_unassign_truck_not_found(service):
    service._repo.get_by_truck.return_value = None
    result = service.unassign_truck(10)
    assert result is None


def test_get_truck_for_driver(service):
    service._repo.get_by_driver.return_value = {"driver_id": 1, "truck_id": 10}
    service._fleet_repo.get_by_id.return_value = {"id": 10, "plate_number": "AB-123"}
    result = service.get_truck_for_driver(1)
    assert result["plate_number"] == "AB-123"


def test_get_truck_for_driver_no_assignment(service):
    service._repo.get_by_driver.return_value = None
    assert service.get_truck_for_driver(1) is None


def test_get_driver_for_truck(service):
    service._repo.get_by_truck.return_value = {"driver_id": 1, "truck_id": 10}
    service._driver_repo.get_by_id.return_value = {"id": 1, "name": "John"}
    result = service.get_driver_for_truck(10)
    assert result["name"] == "John"


def test_get_driver_for_truck_no_assignment(service):
    service._repo.get_by_truck.return_value = None
    assert service.get_driver_for_truck(10) is None


def test_get_truck_plate_for_driver(service):
    service._repo.get_truck_plate_for_driver.return_value = "AB-123"
    assert service.get_truck_plate_for_driver(1) == "AB-123"


def test_get_driver_name_for_truck(service):
    service._repo.get_driver_name_for_truck.return_value = "John"
    assert service.get_driver_name_for_truck(10) == "John"


def test_on_driver_deleted(service):
    service._repo.get_by_driver.return_value = {"driver_id": 1, "truck_id": 10}
    service.on_driver_deleted(1)
    service._repo.unassign_driver.assert_called_with(1)


def test_on_truck_deleted(service):
    service._repo.get_by_truck.return_value = {"driver_id": 1, "truck_id": 10}
    service.on_truck_deleted(10)
    service._repo.unassign_truck.assert_called_with(10)
