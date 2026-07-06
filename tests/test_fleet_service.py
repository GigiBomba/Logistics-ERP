"""Tests for FleetService."""
from unittest.mock import MagicMock, patch

import pytest

from services.fleet_service import FleetService
from services.operations.event_bus import TRUCK_CREATED, TRUCK_DELETED, TRUCK_UPDATED


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock):
    svc = FleetService(db_mock)
    svc._fleet_repo = MagicMock()
    svc._assignment_repo = MagicMock()
    svc._event_bus = MagicMock()
    return svc


def test_get_trucks(service):
    service._fleet_repo.get_all.return_value = [{"id": 1}]
    assert service.get_trucks() == [{"id": 1}]


def test_get_truck(service):
    service._fleet_repo.get_by_id.return_value = {"id": 1, "plate": "AB-123"}
    assert service.get_truck(1) == {"id": 1, "plate": "AB-123"}


def test_get_assigned_routes(service):
    service._assignment_repo.get_by_truck.return_value = [{"id": 1}]
    assert service.get_assigned_routes(1) == [{"id": 1}]


def test_add_truck(service):
    service._fleet_repo.create.return_value = 42
    data = {"plate_number": "AB-123", "model": "Volvo"}
    truck_id = service.add_truck(data)
    assert truck_id == 42
    service._fleet_repo.create.assert_called_with(data)
    service._event_bus.publish.assert_called_once()
    args = service._event_bus.publish.call_args
    assert args[0][0] == TRUCK_CREATED
    assert args[0][1]["truck_id"] == 42


def test_update_truck(service):
    service.update_truck(1, {"plate_number": "CD-456"})
    service._fleet_repo.update.assert_called_with(1, {"plate_number": "CD-456"})
    service._event_bus.publish.assert_called_with(TRUCK_UPDATED, {"truck_id": 1, "changes": {"plate_number": "CD-456"}})


def test_delete_truck(service):
    service.delete_truck(1)
    service._fleet_repo.delete.assert_called_with(1)
    service._event_bus.publish.assert_called_with(TRUCK_DELETED, {"truck_id": 1})


def test_ensure_expenses_table(service):
    service.ensure_expenses_table()
    service.db.ensure_expenses_table.assert_called_once()


def test_get_expenses(service):
    service.db.get_expenses.return_value = [{"id": 1, "amount": 100}]
    result = service.get_expenses(1)
    assert result == [{"id": 1, "amount": 100}]
    service.db.get_expenses.assert_called_with(1)


def test_add_expense(service):
    service.db.add_expense.return_value = 42
    result = service.add_expense(1, "2026-06-01", "fuel", "Diesel", 150.0)
    assert result == 42
    service.db.add_expense.assert_called_with(1, "2026-06-01", "fuel", "Diesel", 150.0)


def test_get_truck_not_found(service):
    service._fleet_repo.get_by_id.return_value = None
    assert service.get_truck(999) is None
