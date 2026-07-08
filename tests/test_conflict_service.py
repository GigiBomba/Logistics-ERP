"""Tests for TripConflictService."""
from __future__ import annotations

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


def test_estimate_eta_uses_end_date(service):
    """When end_date is present, _estimate_eta should return that parsed date."""
    from datetime import datetime
    trip = {"end_date": "15/06/2026", "distance_km": 9999}
    dt = datetime(2026, 6, 1)
    eta = service._estimate_eta(trip, dt)
    assert eta == datetime(2026, 6, 15)


def test_get_departure_with_created_at_fallback(service):
    """When start_date is missing, _get_departure should fall back to created_at."""
    from datetime import datetime
    trip = {"created_at": "05/06/2026"}
    dep = service._get_departure(trip)
    assert dep == datetime(2026, 6, 5)


def test_get_departure_none_when_both_missing(service):
    """When both start_date and created_at are missing, _get_departure returns None."""
    trip = {}
    dep = service._get_departure(trip)
    assert dep is None


def test_check_conflicts_same_truck_only(service):
    """Conflict detected when only the truck matches (different driver)."""
    service._trip_repo.get_active_for_truck.return_value = [
        {"id": 2, "start_date": "01/06/2026", "end_date": "15/06/2026",
         "truck_number": "AB-123", "driver_id": 99, "status": "Active",
         "driver_name": "Other"}
    ]
    result = service.check_conflicts({
        "id": 1, "truck_id": 1, "driver_id": 10,
        "start_date": "10/06/2026", "end_date": "20/06/2026",
        "truck_number": "AB-123",
    })
    assert len(result) == 1
    assert result[0]["same_truck"] is True
    assert result[0]["same_driver"] is False


def test_check_conflicts_same_driver_only(service):
    """Conflict detected when only the driver matches (different truck)."""
    service._trip_repo.get_active_for_truck.return_value = []
    service._trip_repo.get_active_for_driver.return_value = [
        {"id": 2, "start_date": "01/06/2026", "end_date": "15/06/2026",
         "truck_number": "CD-456", "driver_id": 10, "status": "Active",
         "driver_name": "John"}
    ]
    result = service.check_conflicts({
        "id": 1, "truck_id": 1, "driver_id": 10,
        "start_date": "10/06/2026", "end_date": "20/06/2026",
        "truck_number": "AB-123",
    })
    assert len(result) == 1
    assert result[0]["same_truck"] is False
    assert result[0]["same_driver"] is True


def test_check_conflicts_self_trip_excluded(service):
    """A trip should not conflict with itself."""
    service._trip_repo.get_active_for_truck.return_value = [
        {"id": 1, "start_date": "01/06/2026", "end_date": "15/06/2026",
         "truck_number": "AB-123", "driver_id": 10, "status": "Active",
         "driver_name": "John"}
    ]
    result = service.check_conflicts({
        "id": 1, "truck_id": 1, "driver_id": 10,
        "start_date": "10/06/2026", "end_date": "20/06/2026",
        "truck_number": "AB-123",
    })
    assert len(result) == 0


def test_check_conflicts_non_overlapping_trips(service):
    """Trips that do not overlap in time should not conflict."""
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


def test_check_conflicts_truck_id_matching(service):
    """Conflict when truck_id matches (not plate)."""
    service._trip_repo.get_active_for_truck.return_value = [
        {"id": 2, "start_date": "01/06/2026", "end_date": "15/06/2026",
         "truck_number": "", "truck_id": 5, "driver_id": 10, "status": "Active",
         "driver_name": "John"}
    ]
    result = service.check_conflicts({
        "id": 1, "truck_id": 5, "driver_id": 10,
        "start_date": "10/06/2026", "end_date": "20/06/2026",
        "truck_number": "",
    })
    assert len(result) == 1
    assert result[0]["same_truck"] is True


def test_describe_conflict_both_truck_and_driver(service):
    """Description should mention both truck and driver when both match."""
    conflict = {
        "trip_id": 5, "truck_plate": "AB-123", "driver_name": "John",
        "same_truck": True, "same_driver": True,
        "overlap_description": "10/06 - 15/06",
    }
    desc = service.describe_conflict(conflict)
    assert "AB-123" in desc
    assert "John" in desc
    assert "TRP-5" in desc


def test_get_next_available_slot_for_driver_with_trips(service):
    """Next available slot for driver should return a date string when trips exist."""
    from datetime import datetime, timedelta
    future = (datetime.now() + timedelta(days=5)).strftime("%d/%m/%Y")
    service._trip_repo.get_active_for_driver.return_value = [
        {"id": 2, "start_date": "01/06/2026", "end_date": future,
         "truck_number": "AB-123", "driver_id": 10, "status": "Active"}
    ]
    result = service.get_next_available_slot_for_driver(driver_id=10)
    assert result is not None
    assert "/" in result


def test_get_next_available_slot_no_trips_returns_none(service):
    """When there are no active truck trips, next available slot is None."""
    service._trip_repo.get_active_for_truck.return_value = []
    result = service.get_next_available_slot(truck_plate="AB-123")
    assert result is None
