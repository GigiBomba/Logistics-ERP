"""Tests for TripConflictService."""
from unittest.mock import MagicMock, patch

import pytest

from services.conflict_service import TripConflictService


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock):
    svc = TripConflictService(db_mock)
    svc._trip_repo = MagicMock()
    return svc


def test_check_conflicts_no_truck_no_driver(service):
    result = service.check_conflicts({"id": 1})
    assert result == []


def test_check_conflicts_no_departure(service):
    result = service.check_conflicts({"truck_id": 1})
    assert result == []


def test_check_conflicts_overlap(service):
    service._trip_repo.get_active_for_truck.return_value = [
        {"id": 2, "start_date": "01/06/2026", "end_date": "15/06/2026",
         "truck_number": "AB-123", "driver_id": 10, "status": "Active",
         "driver_name": "John"}
    ]
    result = service.check_conflicts({
        "id": 1, "truck_id": 1, "driver_id": 10,
        "start_date": "10/06/2026", "end_date": "20/06/2026",
        "truck_number": "AB-123",
    })
    assert len(result) == 1
    assert result[0]["trip_id"] == 2
    assert result[0]["same_truck"] is True
    assert result[0]["same_driver"] is True


def test_check_conflicts_no_overlap(service):
    service._trip_repo.get_active_for_truck.return_value = [
        {"id": 2, "start_date": "01/06/2026", "end_date": "05/06/2026",
         "truck_number": "AB-123", "driver_id": 10, "status": "Active",
         "driver_name": "John"}
    ]
    result = service.check_conflicts({
        "id": 1, "truck_id": 1, "driver_id": 10,
        "start_date": "10/06/2026", "end_date": "20/06/2026",
        "truck_number": "AB-123",
    })
    assert len(result) == 0


def test_is_truck_available_empty_identifiers(service):
    assert service.is_truck_available() is True
    assert service.is_truck_available(truck_plate="", truck_id=None) is True


@patch.object(TripConflictService, "check_conflicts")
def test_is_truck_available(mock_check, service):
    mock_check.return_value = []
    assert service.is_truck_available(truck_plate="AB-123") is True

    mock_check.return_value = [{"trip_id": 2}]
    assert service.is_truck_available(truck_plate="AB-123") is False


@patch.object(TripConflictService, "check_conflicts")
def test_is_driver_available(mock_check, service):
    mock_check.return_value = []
    assert service.is_driver_available(driver_id=10) is True

    mock_check.return_value = [{"trip_id": 2}]
    assert service.is_driver_available(driver_id=10) is False


def test_is_driver_available_no_id(service):
    assert service.is_driver_available(driver_id=0) is True


def test_get_next_available_slot_no_identifiers(service):
    assert service.get_next_available_slot() is None


def test_get_next_available_slot_no_trips(service):
    service._trip_repo.get_active_for_truck.return_value = []
    result = service.get_next_available_slot(truck_plate="AB-123")
    assert result is None  # now() < now()


def test_get_next_available_slot_with_trips(service):
    from datetime import datetime, timedelta
    future = (datetime.now() + timedelta(days=5)).strftime("%d/%m/%Y")
    service._trip_repo.get_active_for_truck.return_value = [
        {"id": 2, "start_date": "01/06/2026", "end_date": future,
         "truck_number": "AB-123", "driver_id": 10, "status": "Active"}
    ]
    result = service.get_next_available_slot(truck_plate="AB-123")
    assert result is not None


def test_describe_conflict_truck(service):
    conflict = {
        "trip_id": 5, "truck_plate": "AB-123", "driver_name": "John",
        "same_truck": True, "same_driver": False,
        "overlap_description": "10/06 - 15/06",
    }
    desc = service.describe_conflict(conflict)
    assert "AB-123" in desc
    assert "TRP-5" in desc
    assert "John" not in desc


def test_describe_conflict_driver(service):
    conflict = {
        "trip_id": 5, "truck_plate": "AB-123", "driver_name": "John",
        "same_truck": False, "same_driver": True,
        "overlap_description": "10/06 - 15/06",
    }
    desc = service.describe_conflict(conflict)
    assert "John" in desc
    assert "TRP-5" in desc


def test_get_next_available_slot_for_driver(service):
    service._trip_repo.get_active_for_driver.return_value = []
    result = service.get_next_available_slot_for_driver(driver_id=10)
    assert result is None


def test_get_next_available_slot_for_driver_no_id(service):
    assert service.get_next_available_slot_for_driver(driver_id=0) is None


def test_estimate_eta_fallback_distance(service):
    from datetime import datetime
    trip = {"start_date": "01/06/2026", "distance_km": 600}
    dt = datetime(2026, 6, 1)
    eta = service._estimate_eta(trip, dt)
    # 600 / 60 = 10 hours
    assert eta == dt.replace(hour=10)


def test_estimate_eta_fallback_default(service):
    from datetime import datetime
    trip = {"start_date": "01/06/2026"}
    dt = datetime(2026, 6, 1)
    eta = service._estimate_eta(trip, dt)
    assert eta == dt.replace(hour=4)
