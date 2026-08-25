"""Tests for FleetService — covers both typed (Pydantic) and deprecated dict-returning methods."""
from __future__ import annotations


from datetime import date, datetime
from unittest.mock import ANY, MagicMock, patch

import pytest

from models.common import ErrorDetail, ServiceResult
from models.vehicle_models import (
    VehicleCreate,
    VehicleCreateResult,
    VehicleHealthScore,
    VehicleResult,
    VehicleSearchRequest,
    VehicleUpdate,
)
from services.fleet_service import FleetService
from services.operations.event_bus import TRUCK_CREATED, TRUCK_DELETED, TRUCK_UPDATED
from services.permission_service import PermissionCheckResult


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock):
    svc = FleetService(db_mock)
    svc._fleet_repo = MagicMock()
    svc._assignment_repo = MagicMock()
    svc._event_bus = MagicMock()
    svc._perm = MagicMock()
    # By default allow all permission checks
    svc._perm.can_create_vehicle.return_value = PermissionCheckResult(True)
    svc._perm.can_update_vehicle.return_value = PermissionCheckResult(True)
    svc._perm.can_delete_vehicle.return_value = PermissionCheckResult(True)
    return svc


@pytest.fixture
def sample_repo_row():
    return {
        "id": 1,
        "plate_number": "AB-123-CD",
        "manufacturer": "Volvo",
        "model": "FH",
        "year": 2022,
        "vin": "YV2R1A1A9LA123456",
        "max_payload_kg": 24000,
        "fuel_consumption": 30.5,
        "insurance_expiry": "2026-12-31",
        "inspection_expiry": "2026-06-30",
        "tachograph_expiry": "2026-03-15",
        "status": "active",
        "active_status": 1,
    }


# ── Backward-compatible deprecated methods ────────────────────────────────


def test_get_trucks_deprecated(service):
    service._fleet_repo.get_all.return_value = [{"id": 1}]
    with pytest.warns(DeprecationWarning):
        result = service.get_trucks()
    assert result == [{"id": 1}]


def test_get_truck_deprecated(service):
    service._fleet_repo.get_by_id.return_value = {"id": 1, "plate": "AB-123"}
    with pytest.warns(DeprecationWarning):
        result = service.get_truck(1)
    assert result == {"id": 1, "plate": "AB-123"}


def test_get_truck_not_found_deprecated(service):
    service._fleet_repo.get_by_id.return_value = None
    with pytest.warns(DeprecationWarning):
        assert service.get_truck(999) is None


def test_add_truck_deprecated(service):
    service._fleet_repo.create.return_value = 42
    data = {"plate_number": "AB-123", "model": "Volvo"}
    with pytest.warns(DeprecationWarning):
        truck_id = service.add_truck(data)
    assert truck_id == 42
    service._fleet_repo.create.assert_called_with(data)
    service._event_bus.publish.assert_called_once()
    args = service._event_bus.publish.call_args
    assert args[0][0] == TRUCK_CREATED
    assert args[0][1]["truck_id"] == 42


def test_update_truck_deprecated(service):
    with pytest.warns(DeprecationWarning):
        service.update_truck(1, {"plate_number": "CD-456"})
    # update_truck forwards the tenant-scoped company_id (defaults to None).
    service._fleet_repo.update.assert_called_with(
        1, {"plate_number": "CD-456"}, company_id=None
    )
    service._event_bus.publish.assert_called_with(
        TRUCK_UPDATED, {"truck_id": 1, "changes": {"plate_number": "CD-456"}}
    )


def test_delete_truck_deprecated(service):
    with pytest.warns(DeprecationWarning):
        service.delete_truck(1)
    # delete_truck forwards the tenant-scoped company_id (defaults to None).
    service._fleet_repo.delete.assert_called_with(1, company_id=None)
    service._event_bus.publish.assert_called_with(TRUCK_DELETED, {"truck_id": 1})


def test_get_assigned_routes(service):
    service._assignment_repo.get_by_truck.return_value = [{"id": 1}]
    assert service.get_assigned_routes(1) == [{"id": 1}]


def test_ensure_expenses_table(service):
    service.ensure_expenses_table()
    service.db.ensure_expenses_table.assert_called_once()


def test_get_expenses(service):
    service.db.get_expenses.return_value = [{"id": 1, "amount": 100}]
    result = service.get_expenses(1)
    assert isinstance(result, ServiceResult)
    assert result.success is True
    assert result.data == [{"id": 1, "amount": 100}]
    service.db.get_expenses.assert_called_with(1, company_id=ANY)


def test_add_expense(service):
    service.db.add_expense.return_value = 42
    result = service.add_expense(1, "2026-06-01", "fuel", "Diesel", 150.0)
    assert result == 42
    service.db.add_expense.assert_called_with(1, "2026-06-01", "fuel", "Diesel", 150.0)


# ── New typed methods ─────────────────────────────────────────────────────


def test_get_vehicle_found(service, sample_repo_row):
    service._fleet_repo.get_by_id.return_value = sample_repo_row
    result = service.get(1)
    assert result.success is True
    assert isinstance(result.data, VehicleResult)
    assert result.data.id == 1
    assert result.data.plate == "AB-123-CD"
    assert result.data.brand == "Volvo"
    assert result.data.model == "FH"


def test_get_vehicle_not_found(service):
    service._fleet_repo.get_by_id.return_value = None
    result = service.get(999)
    assert result.success is False
    assert len(result.errors) == 1
    assert result.errors[0].code == "NOT_FOUND"


def test_list_all(service, sample_repo_row):
    service._fleet_repo.get_all.return_value = [sample_repo_row]
    result = service.list_all()
    assert result.success is True
    assert len(result.data) == 1
    assert result.data[0].plate == "AB-123-CD"


def test_list_all_empty(service):
    service._fleet_repo.get_all.return_value = []
    result = service.list_all()
    assert result.success is True
    assert result.data == []


def test_list_all_error(service):
    service._fleet_repo.get_all.side_effect = Exception("DB down")
    result = service.list_all()
    assert result.success is False
    assert result.errors[0].code == "LIST_ERROR"


def test_search_by_query(service, sample_repo_row):
    service._fleet_repo.get_all.return_value = [sample_repo_row]
    req = VehicleSearchRequest(query="Volvo")
    result = service.search(req)
    assert result.success is True
    assert len(result.data) == 1


def test_search_by_status(service, sample_repo_row):
    service._fleet_repo.get_all.return_value = [sample_repo_row]
    req = VehicleSearchRequest(status="active")
    result = service.search(req)
    assert result.success is True
    assert len(result.data) == 1


def test_search_no_match(service, sample_repo_row):
    service._fleet_repo.get_all.return_value = [sample_repo_row]
    req = VehicleSearchRequest(query="Nonexistent")
    result = service.search(req)
    assert result.success is True
    assert result.data == []


def test_find_available(service, sample_repo_row):
    service._fleet_repo.get_active_trucks.return_value = [sample_repo_row]
    req = VehicleSearchRequest()
    result = service.find_available(req)
    assert result.success is True
    assert len(result.data) == 1
    assert result.data[0].plate == "AB-123-CD"
    service._fleet_repo.get_active_trucks.assert_called_once()


def test_create_vehicle_success(service, sample_repo_row):
    service._fleet_repo.get_by_plate.return_value = None
    service._fleet_repo.create.return_value = 1
    service._fleet_repo.get_by_id.return_value = sample_repo_row

    request = VehicleCreate(
        plate="AB-123-CD",
        brand="Volvo",
        model="FH",
        year=2022,
        vin="YV2R1A1A9LA123456",
        max_weight_kg=24000,
        consumption_l_per_100km=30.5,
        insurance_expiry=date(2026, 12, 31),
        technical_inspection_expiry=date(2026, 6, 30),
        tachograph_calibration_expiry=date(2026, 3, 15),
        status="active",
    )
    result = service.create(request, user_id=10)
    assert result.success is True
    assert isinstance(result.data, VehicleResult)
    assert result.data.plate == "AB-123-CD"
    service._perm.can_create_vehicle.assert_called_with(10)
    service._fleet_repo.create.assert_called_once()
    service._event_bus.publish.assert_called_once()


def test_create_vehicle_permission_denied(service):
    service._perm.can_create_vehicle.return_value = PermissionCheckResult(False, "Not allowed")
    request = VehicleCreate(plate="XX-999")
    result = service.create(request, user_id=10)
    assert result.success is False
    assert result.errors[0].code == "PERMISSION_DENIED"
    service._fleet_repo.create.assert_not_called()


def test_create_vehicle_duplicate_plate(service):
    service._perm.can_create_vehicle.return_value = (
        service._perm.PermissionCheckResult(True)
    )
    service._fleet_repo.get_by_plate.return_value = {"id": 5, "plate_number": "AB-123-CD"}
    request = VehicleCreate(plate="AB-123-CD")
    result = service.create(request, user_id=10)
    assert result.success is False
    assert result.errors[0].code == "DUPLICATE_PLATE"
    service._fleet_repo.create.assert_not_called()


def test_update_vehicle_success(service, sample_repo_row):
    service._fleet_repo.get_by_id.side_effect = [sample_repo_row, sample_repo_row]
    service._fleet_repo.get_by_plate.return_value = None

    request = VehicleUpdate(model="FH16", year=2023)
    result = service.update(1, request, user_id=10)
    assert result.success is True
    assert isinstance(result.data, VehicleResult)
    service._perm.can_update_vehicle.assert_called_with(10)
    service._fleet_repo.update.assert_called_once()
    args = service._fleet_repo.update.call_args
    assert args[0][0] == 1
    assert "model" in args[0][1]
    assert args[0][1]["model"] == "FH16"
    assert "year" in args[0][1]
    assert args[0][1]["year"] == 2023


def test_update_vehicle_permission_denied(service):
    service._perm.can_update_vehicle.return_value = PermissionCheckResult(False, "Not allowed")
    request = VehicleUpdate(model="FH16")
    result = service.update(1, request, user_id=10)
    assert result.success is False
    assert result.errors[0].code == "PERMISSION_DENIED"
    service._fleet_repo.update.assert_not_called()


def test_update_vehicle_not_found(service):
    service._fleet_repo.get_by_id.return_value = None
    request = VehicleUpdate(model="FH16")
    result = service.update(999, request, user_id=10)
    assert result.success is False
    assert result.errors[0].code == "NOT_FOUND"


def test_update_vehicle_duplicate_plate(service, sample_repo_row):
    service._fleet_repo.get_by_id.return_value = sample_repo_row
    service._fleet_repo.get_by_plate.return_value = {"id": 2, "plate_number": "NEW-PLATE"}

    request = VehicleUpdate(plate="NEW-PLATE")
    result = service.update(1, request, user_id=10)
    assert result.success is False
    assert result.errors[0].code == "DUPLICATE_PLATE"


def test_delete_vehicle_success(service, sample_repo_row):
    service._fleet_repo.get_by_id.return_value = sample_repo_row

    result = service.delete(1, user_id=10)
    assert result.success is True
    assert isinstance(result.data, VehicleResult)
    assert result.data.id == 1
    service._perm.can_delete_vehicle.assert_called_with(10)
    service._fleet_repo.delete.assert_called_with(1)
    service._event_bus.publish.assert_called_with(TRUCK_DELETED, {"truck_id": 1})


def test_delete_vehicle_permission_denied(service):
    service._perm.can_delete_vehicle.return_value = PermissionCheckResult(False, "Admins only")
    result = service.delete(1, user_id=10)
    assert result.success is False
    assert result.errors[0].code == "PERMISSION_DENIED"
    service._fleet_repo.delete.assert_not_called()


def test_delete_vehicle_not_found(service):
    service._fleet_repo.get_by_id.return_value = None
    result = service.delete(999, user_id=10)
    assert result.success is False
    assert result.errors[0].code == "NOT_FOUND"


def test_health_score_with_data(service, sample_repo_row):
    service._fleet_repo.get_by_id.return_value = sample_repo_row
    service._fleet_repo.get_truck_health.return_value = {
        "truck_id": 1,
        "score": 85,
        "compliance_pct": 90.0,
        "overdue_count": 2,
        "recurring_issues": 1,
        "downtime_days": 3,
        "last_updated": "2026-07-01",
    }

    result = service.health_score(1)
    assert result.success is True
    assert isinstance(result.data, VehicleHealthScore)
    assert result.data.overall_score == 85.0
    assert result.data.maintenance_alerts == 2


def test_health_score_no_data(service, sample_repo_row):
    service._fleet_repo.get_by_id.return_value = sample_repo_row
    service._fleet_repo.get_truck_health.return_value = None

    result = service.health_score(1)
    assert result.success is True
    assert result.data.overall_score == 100.0
    assert result.data.maintenance_alerts == 0


def test_health_score_vehicle_not_found(service):
    service._fleet_repo.get_by_id.return_value = None

    result = service.health_score(999)
    assert result.success is False
    assert result.errors[0].code == "NOT_FOUND"


def test_get_expenses_returns_service_result(service):
    service.db.get_expenses.return_value = [{"id": 1, "amount": 100}]
    result = service.get_expenses(1)
    assert isinstance(result, ServiceResult)
    assert result.success is True
    assert len(result.data) == 1
    assert result.data[0]["amount"] == 100


def test_get_expenses_error(service):
    service.db.get_expenses.side_effect = Exception("DB error")
    result = service.get_expenses(1)
    assert result.success is False
    assert result.errors[0].code == "EXPENSES_ERROR"
