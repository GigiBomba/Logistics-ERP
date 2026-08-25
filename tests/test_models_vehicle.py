"""Tests for vehicle_models.py — Vehicle create/update, plate validation, fuel type, consumption rate."""
from __future__ import annotations

import pytest
from datetime import date, datetime
from pydantic import ValidationError
from models.vehicle_models import (
    VehicleCreate,
    VehicleUpdate,
    VehicleSearchRequest,
    VehicleHealthScore,
    VehicleResult,
)


class TestVehicleCreate:
    @pytest.mark.parametrize(
        "plate, brand, model, year, fuel_type, consumption",
        [
            ("AB123CD", "Volvo", "FH", 2020, "diesel", 33.5),
            ("BC-234-DE", "Mercedes", "Actros", 2021, "diesel", 30.0),
            ("  xyz789  ", "MAN", "TGX", 2019, "diesel", None),
            ("DE1234FG", "", "", None, "electric", 15.2),
            ("TR-123-XX", "Iveco", "Stralis", 2022, "diesel", 28.7),
        ],
    )
    def test_vehicle_create_valid(self, plate, brand, model, year, fuel_type, consumption):
        v = VehicleCreate(
            plate=plate,
            brand=brand,
            model=model,
            year=year,
            fuel_type=fuel_type,
            consumption_l_per_100km=consumption,
        )
        assert v.plate == plate.strip().upper()
        assert v.brand == brand
        assert v.fuel_type == fuel_type
        assert v.consumption_l_per_100km == consumption

    @pytest.mark.parametrize(
        "plate",
        ["", "   ", "\t\n"],
    )
    def test_plate_empty_raises(self, plate):
        with pytest.raises(ValidationError, match="Plate number is required"):
            VehicleCreate(plate=plate)

    @pytest.mark.parametrize(
        "plate, expected",
        [
            ("ab123cd", "AB123CD"),
            (" Bc-234-de ", "BC-234-DE"),
            ("  xyz-789  ", "XYZ-789"),
        ],
    )
    def test_plate_normalized_to_upper_stripped(self, plate, expected):
        v = VehicleCreate(plate=plate)
        assert v.plate == expected

    def test_vehicle_create_defaults(self):
        v = VehicleCreate(plate="AB123CD")
        assert v.brand == ""
        assert v.model == ""
        assert v.year is None
        assert v.vin == ""
        assert v.max_weight_kg is None
        assert v.fuel_type == "diesel"
        assert v.consumption_l_per_100km is None
        assert v.status == "active"

    def test_vehicle_create_dates_accepted(self):
        v = VehicleCreate(
            plate="TM01ABC",
            insurance_expiry=date(2026, 12, 31),
            technical_inspection_expiry=date(2026, 6, 15),
            tachograph_calibration_expiry=date(2026, 3, 1),
        )
        assert v.insurance_expiry == date(2026, 12, 31)
        assert v.technical_inspection_expiry == date(2026, 6, 15)
        assert v.tachograph_calibration_expiry == date(2026, 3, 1)


class TestVehicleUpdate:
    def test_vehicle_update_all_optional(self):
        u = VehicleUpdate()
        assert u.plate is None

    def test_vehicle_update_partial(self):
        u = VehicleUpdate(brand="Scania", status="maintenance")
        assert u.brand == "Scania"
        assert u.status == "maintenance"
        assert u.plate is None

    def test_vehicle_update_plate_not_required(self):
        u = VehicleUpdate(consumption_l_per_100km=31.2)
        assert u.consumption_l_per_100km == 31.2
        assert u.plate is None


class TestVehicleSearchRequest:
    @pytest.mark.parametrize(
        "query, status, fuel_type, page, per_page",
        [
            ("", None, None, 1, 20),
            ("AB123", "active", "diesel", 2, 50),
            ("XYZ", "inactive", "electric", 3, 10),
        ],
    )
    def test_search_params(self, query, status, fuel_type, page, per_page):
        r = VehicleSearchRequest(
            query=query,
            status=status,
            fuel_type=fuel_type,
            page=page,
            per_page=per_page,
        )
        assert r.query == query
        assert r.status == status
        assert r.page == page
        assert r.per_page == per_page

    def test_search_with_availability_window(self):
        from_ = datetime(2026, 1, 1, 8, 0)
        to_ = datetime(2026, 1, 10, 18, 0)
        r = VehicleSearchRequest(available_between=(from_, to_))
        assert r.available_between == (from_, to_)
        assert r.min_capacity_kg is None


class TestVehicleHealthScore:
    def test_health_score_defaults(self):
        h = VehicleHealthScore(
            vehicle_id=1,
            plate="AB123CD",
            overall_score=85.5,
            insurance_status="valid",
            technical_inspection_status="valid",
            tachograph_status="expired",
            maintenance_alerts=2,
        )
        assert h.vehicle_id == 1
        assert h.overall_score == 85.5
        assert h.next_maintenance_due is None

    def test_health_score_with_next_maintenance(self):
        h = VehicleHealthScore(
            vehicle_id=2,
            plate="BC234DE",
            overall_score=92.0,
            insurance_status="valid",
            technical_inspection_status="valid",
            tachograph_status="valid",
            maintenance_alerts=0,
            next_maintenance_due=date(2026, 8, 1),
        )
        assert h.next_maintenance_due == date(2026, 8, 1)


class TestVehicleResult:
    def test_vehicle_result_minimal(self):
        r = VehicleResult(
            id=10,
            plate="TM01ABC",
            brand="Volvo",
            model="FH",
            fuel_type="diesel",
            status="active",
        )
        assert r.id == 10
        assert r.health_score is None
        assert r.current_location is None
        assert r.created_at is None

    def test_vehicle_result_with_health_score(self):
        hs = VehicleHealthScore(
            vehicle_id=10,
            plate="TM01ABC",
            overall_score=75.0,
            insurance_status="valid",
            technical_inspection_status="valid",
            tachograph_status="expired",
            maintenance_alerts=1,
        )
        r = VehicleResult(
            id=10,
            plate="TM01ABC",
            brand="Volvo",
            model="FH",
            fuel_type="diesel",
            status="active",
            health_score=hs,
        )
        assert r.health_score is not None
        assert r.health_score.overall_score == 75.0

    def test_vehicle_result_defaults_optional_str(self):
        r = VehicleResult(
            id=1,
            plate="PLATE",
            brand="B",
            model="M",
            fuel_type="diesel",
            status="active",
        )
        assert r.vin == ""
        assert r.year is None
