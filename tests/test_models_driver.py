"""Tests for driver_models.py — DriverCreate, DriverUpdate, DriverResult, etc."""
import pytest
from datetime import date, datetime
from pydantic import ValidationError
from models.driver_models import (
    DriverCreate,
    DriverUpdate,
    DriverResult,
    DriverHoursCheck,
    DriverHoursResult,
    TruckAssignment,
)


class TestDriverCreate:
    """Driver creation: name required and not empty, defaults, validators."""

    @pytest.mark.parametrize(
        "name, email, phone, license_number",
        [
            ("John Doe", "john@example.com", "+123456789", "LIC-001"),
            ("  Jane Smith  ", "", "", ""),
            ("A", "a@b.co", "+0", "X"),
            ("Driver with long name", "driver@fleet.com", "+49 1234 5678", "DL-12345"),
        ],
    )
    def test_valid_creation(self, name, email, phone, license_number):
        """Various valid driver creations."""
        d = DriverCreate(
            name=name,
            email=email,
            phone=phone,
            license_number=license_number,
        )
        assert d.name == name.strip()
        assert d.email == email

    def test_name_stripped(self):
        """Whitespace around name is stripped."""
        d = DriverCreate(name="  James Bond  ")
        assert d.name == "James Bond"

    @pytest.mark.parametrize(
        "name",
        ["", "   ", "\t\n"],
    )
    def test_empty_name_raises(self, name):
        """Blank name raises ValidationError."""
        with pytest.raises(ValidationError, match="Driver name is required"):
            DriverCreate(name=name)

    def test_default_fields(self):
        """Defaults: email='', phone='', license_number='',
        hours_worked=0.0, max_hours_per_day=9.0, status='active'."""
        d = DriverCreate(name="Test Driver")
        assert d.email == ""
        assert d.phone == ""
        assert d.license_number == ""
        assert d.hours_worked == 0.0
        assert d.max_hours_per_day == 9.0
        assert d.status == "active"

    def test_license_expiry_none_by_default(self):
        d = DriverCreate(name="Test Driver")
        assert d.license_expiry is None

    def test_explicit_license_expiry(self):
        d = DriverCreate(
            name="Test Driver",
            license_expiry=date(2028, 12, 31),
        )
        assert d.license_expiry == date(2028, 12, 31)

    def test_hours_worked_explicit(self):
        d = DriverCreate(name="Test Driver", hours_worked=40.5, max_hours_per_day=10.0)
        assert d.hours_worked == 40.5
        assert d.max_hours_per_day == 10.0

    def test_status_explicit(self):
        d = DriverCreate(name="Test Driver", status="inactive")
        assert d.status == "inactive"

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            DriverCreate()


class TestDriverUpdate:
    """All Optional, partial update supported."""

    def test_empty_update(self):
        """Empty body is valid — all fields optional."""
        du = DriverUpdate()
        assert du.name is None
        assert du.email is None
        assert du.phone is None
        assert du.license_number is None
        assert du.license_expiry is None
        assert du.hours_worked is None
        assert du.max_hours_per_day is None
        assert du.status is None

    def test_partial_update_name(self):
        du = DriverUpdate(name="New Name")
        assert du.name == "New Name"
        assert du.status is None

    def test_partial_update_multiple(self):
        du = DriverUpdate(
            name="Updated Driver",
            phone="+111",
            status="suspended",
        )
        assert du.name == "Updated Driver"
        assert du.phone == "+111"
        assert du.status == "suspended"
        assert du.email is None

    def test_update_hours(self):
        du = DriverUpdate(hours_worked=50.0, max_hours_per_day=8.0)
        assert du.hours_worked == 50.0
        assert du.max_hours_per_day == 8.0

    def test_update_license(self):
        du = DriverUpdate(
            license_number="NEW-LIC-999",
            license_expiry=date(2030, 1, 1),
        )
        assert du.license_number == "NEW-LIC-999"
        assert du.license_expiry == date(2030, 1, 1)


class TestDriverResult:
    """Driver output model."""

    def test_minimal(self):
        dr = DriverResult(
            id=1,
            name="John",
            email="",
            phone="",
            license_number="",
            hours_worked=0.0,
            max_hours_per_day=9.0,
            status="active",
        )
        assert dr.id == 1
        assert dr.license_expiry is None
        assert dr.current_truck_id is None
        assert dr.current_truck_plate == ""
        assert dr.created_at is None

    def test_with_all_fields(self):
        now = datetime.now()
        dr = DriverResult(
            id=5,
            name="Alice",
            email="alice@fleet.com",
            phone="+123",
            license_number="LIC-A99",
            license_expiry=date(2027, 6, 1),
            hours_worked=120.5,
            max_hours_per_day=10.0,
            status="active",
            current_truck_id=3,
            current_truck_plate="AB123CD",
            created_at=now,
        )
        assert dr.email == "alice@fleet.com"
        assert dr.license_expiry == date(2027, 6, 1)
        assert dr.current_truck_id == 3
        assert dr.current_truck_plate == "AB123CD"
        assert dr.created_at == now

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            DriverResult(
                name="X",
                email="",
                phone="",
                license_number="",
                hours_worked=0.0,
                max_hours_per_day=9.0,
                status="active",
            )


class TestDriverHoursCheck:
    """DriverHoursCheck model."""

    def test_valid(self):
        dhc = DriverHoursCheck(
            driver_id=1,
            check_date=date(2026, 7, 11),
        )
        assert dhc.planned_hours == 0.0

    def test_with_planned_hours(self):
        dhc = DriverHoursCheck(
            driver_id=1,
            check_date=date(2026, 7, 11),
            planned_hours=8.5,
        )
        assert dhc.planned_hours == 8.5

    def test_missing_driver_id_raises(self):
        with pytest.raises(ValidationError):
            DriverHoursCheck(check_date=date(2026, 7, 11))


class TestDriverHoursResult:
    """DriverHoursResult model."""

    def test_minimal(self):
        dhr = DriverHoursResult(
            driver_id=1,
            driver_name="John",
            hours_worked_today=4.0,
            hours_worked_week=32.0,
            max_hours_per_day=9.0,
            available_hours_today=5.0,
            is_compliant=True,
        )
        assert dhr.warnings == []

    def test_with_warnings(self):
        dhr = DriverHoursResult(
            driver_id=2,
            driver_name="Jane",
            hours_worked_today=9.0,
            hours_worked_week=50.0,
            max_hours_per_day=9.0,
            available_hours_today=0.0,
            is_compliant=False,
            warnings=["Max hours reached", "Weekly limit approaching"],
        )
        assert len(dhr.warnings) == 2
        assert dhr.is_compliant is False


class TestTruckAssignment:
    """TruckAssignment model."""

    def test_minimal(self):
        ta = TruckAssignment(driver_id=1, truck_id=5)
        assert ta.assigned_at is None
        assert ta.unassigned_at is None

    def test_with_timestamps(self):
        now = datetime.now()
        ta = TruckAssignment(
            driver_id=1,
            truck_id=5,
            assigned_at=now,
            unassigned_at=now,
        )
        assert ta.assigned_at == now
        assert ta.unassigned_at == now
