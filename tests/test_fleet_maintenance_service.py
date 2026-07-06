"""Tests for FleetMaintenanceService."""
from unittest.mock import MagicMock, patch

import pytest

from services.fleet_maintenance_service import (
    FleetMaintenanceService,
    MaintType,
    TruckHealth,
)


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock):
    svc = FleetMaintenanceService(db_mock)
    svc._fleet_repo = MagicMock()
    return svc


def test_add_record(service):
    service._fleet_repo.add_maintenance_record.return_value = 42
    rid = service.add_record(truck_id=1, maint_type="oil_change",
                             date="2026-06-01", km=50000, cost=200.0,
                             notes="Regular", provider="Shop", attachment="")
    assert rid == 42
    service._fleet_repo.add_maintenance_record.assert_called_once()
    service._fleet_repo.get_maintenance_schedule.assert_called_once_with(1, "oil_change")


def test_add_record_no_schedule(service):
    service._fleet_repo.add_maintenance_record.return_value = 1
    service._fleet_repo.get_maintenance_schedule.return_value = None
    rid = service.add_record(truck_id=1, maint_type="oil_change", date="2026-06-01")
    assert rid == 1


def test_get_records(service):
    service._fleet_repo.get_maintenance_records.return_value = [{"id": 1}]
    result = service.get_records(truck_id=1, limit=10, offset=0)
    assert result == [{"id": 1}]
    service._fleet_repo.get_maintenance_records.assert_called_with(1, None, 10, 0)


def test_get_record_count(service):
    service._fleet_repo.count_maintenance_records.return_value = 5
    assert service.get_record_count(truck_id=1) == 5


def test_add_schedule(service):
    service._fleet_repo.add_maintenance_schedule.return_value = 99
    sid = service.add_schedule(truck_id=1, maint_type="oil_change",
                               interval_km=15000, interval_months=6)
    assert sid == 99


def test_get_schedules(service):
    service._fleet_repo.get_maintenance_schedules.return_value = [{"id": 1}]
    result = service.get_schedules(truck_id=1)
    assert result == [{"id": 1}]


def test_predict_next_service_no_schedule(service):
    service._fleet_repo.get_maintenance_schedule.return_value = None
    result = service.predict_next_service(1, "oil_change")
    assert result is None


def test_predict_next_service_km_based(service):
    service._fleet_repo.get_maintenance_schedule.return_value = {
        "last_done_km": 40000, "last_done_date": "2026-01-01",
        "interval_km": 15000, "interval_months": None,
        "fixed_expiry_date": "",
    }
    service._fleet_repo.get_truck_mileage.return_value = 50000
    result = service.predict_next_service(1, "oil_change")
    assert result["due_km"] == 55000
    assert result["remaining_km"] == 5000
    assert result["overdue"] is False


def test_predict_next_service_km_overdue(service):
    service._fleet_repo.get_maintenance_schedule.return_value = {
        "last_done_km": 40000, "last_done_date": "2026-01-01",
        "interval_km": 15000, "interval_months": None,
        "fixed_expiry_date": "",
    }
    service._fleet_repo.get_truck_mileage.return_value = 60000
    result = service.predict_next_service(1, "oil_change")
    assert result["overdue"] is True
    assert result["due_by_km"] == 0


def test_predict_next_service_date_based(service):
    from datetime import datetime, timedelta
    future_date = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    past_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    service._fleet_repo.get_maintenance_schedule.return_value = {
        "last_done_km": None, "last_done_date": past_date,
        "interval_km": None, "interval_months": 6,
        "fixed_expiry_date": "",
    }
    service._fleet_repo.get_truck_mileage.return_value = 0
    result = service.predict_next_service(1, "oil_change")
    assert result["overdue"] is True


def test_predict_all_upcoming(service):
    service._fleet_repo.get_maintenance_schedule.return_value = None
    results = service.predict_all_upcoming(1, days_ahead=30)
    assert results == []


def test_compute_health(service):
    service.get_schedules = MagicMock(return_value=[])
    service._fleet_repo.get_maintenance_type_counts.return_value = {}
    service._fleet_repo.get_maintenance_last_date.return_value = None
    health = service.compute_health(1)
    assert isinstance(health, TruckHealth)
    assert health.score == 100
    assert health.compliance_pct == 100.0


def test_get_health_from_cache(service):
    service._health_cache[1] = TruckHealth(truck_id=1, score=85)
    health = service.get_health(1)
    assert health.score == 85


def test_get_summary(service):
    service._fleet_repo.count_maintenance_records.return_value = 10
    service._fleet_repo.sum_maintenance_cost.return_value = 5000.0
    service._fleet_repo.count_active_maintenance_schedules.return_value = 3
    service._fleet_repo.get_all_schedules_flat.return_value = []
    service._fleet_repo.get_maintenance_cost_by_type.return_value = []
    service._fleet_repo.get_maintenance_count_by_type.return_value = []
    service._fleet_repo.get_top_maintained_trucks.return_value = []
    service._fleet_repo.get_all_truck_health.return_value = []
    summary = service.get_summary()
    assert summary["total_records"] == 10
    assert summary["total_cost"] == 5000.0


def test_update_record(service):
    service._fleet_repo.get_maintenance_record_truck_id.return_value = 1
    result = service.update_record(1, "oil_change", "2026-06-01", km=55000)
    assert result is True
    service._fleet_repo.update_maintenance_record.assert_called_once()


def test_update_record_not_found(service):
    service._fleet_repo.get_maintenance_record_truck_id.return_value = None
    result = service.update_record(999, "oil_change", "2026-06-01")
    assert result is False


def test_delete_record(service):
    service._fleet_repo.get_maintenance_record_truck_id.return_value = 1
    result = service.delete_record(1)
    assert result is True
    service._fleet_repo.delete_maintenance_record.assert_called_with(1)


def test_update_schedule(service):
    service._fleet_repo.update_maintenance_schedule.return_value = None
    service._fleet_repo.get_schedule_truck_id.return_value = 1
    result = service.update_schedule(1, interval_km=20000)
    assert result is True


def test_update_schedule_no_fields(service):
    result = service.update_schedule(1)
    assert result is False


def test_delete_schedule(service):
    service._fleet_repo.get_schedule_truck_id.return_value = 1
    result = service.delete_schedule(1)
    assert result is True
    service._fleet_repo.delete_maintenance_schedule.assert_called_with(1)


def test_maint_display_type():
    from services.fleet_maintenance_service import MaintRecord
    r = MaintRecord(maintenance_type="oil_change")
    assert r.display_type() == "Oil Change"


def test_maint_icon():
    from services.fleet_maintenance_service import MaintRecord
    r = MaintRecord(maintenance_type="brakes")
    assert r.icon() is not None
