"""Tests for tacho_models.py — TachoImportRequest, DriverActivity, VehicleActivity,
TachoImportResult, DriverHoursAnalysis, FleetTachoSummary, and result alias types."""
from __future__ import annotations

import pytest
from datetime import date, datetime
from pydantic import ValidationError
from models.tacho_models import (
    TachoImportRequest,
    DriverActivity,
    VehicleActivity,
    TachoImportResult,
    DriverHoursAnalysis,
    FleetTachoSummary,
    TachoImportOperationResult,
    TachoAnalysisResult,
    TachoFleetSummaryResult,
)
from models.common import ServiceResult, ErrorDetail


class TestTachoImportRequest:
    """path_must_not_be_empty validator — empty strings, whitespace, valid paths."""

    @pytest.mark.parametrize(
        "file_path",
        [
            "/data/tacho/driver_2026.ddd",
            "C:\\tacho\\cards\\driver_01.c1b",
            "relative/path/file.esm",
            "file_without_extension",
            "valid_path_123",
        ],
    )
    def test_valid_file_path(self, file_path):
        """Various valid file path strings."""
        req = TachoImportRequest(file_path=file_path)
        assert req.file_path == file_path

    def test_trailing_whitespace_stripped(self):
        """path_must_not_be_empty strips trailing whitespace."""
        req = TachoImportRequest(file_path="  /data/tacho/file.ddd  ")
        assert req.file_path == "/data/tacho/file.ddd"

    def test_leading_whitespace_stripped(self):
        """leading whitespace is also stripped."""
        req = TachoImportRequest(file_path="   \t/srv/tacho/file.c1b\n")
        assert req.file_path == "/srv/tacho/file.c1b"

    @pytest.mark.parametrize("empty_path", ["", "   ", "\t\n", " \r\n "])
    def test_empty_path_raises(self, empty_path):
        """Empty or whitespace-only paths raise ValidationError."""
        with pytest.raises(ValidationError, match="File path is required"):
            TachoImportRequest(file_path=empty_path)

    def test_missing_file_path_raises(self):
        """file_path is required — omitting it raises."""
        with pytest.raises(ValidationError):
            TachoImportRequest()

    def test_default_file_type(self):
        """Default file_type is 'ddd'."""
        req = TachoImportRequest(file_path="/data/file.ddd")
        assert req.file_type == "ddd"

    def test_explicit_file_type(self):
        """file_type can be overridden."""
        req = TachoImportRequest(file_path="/data/file.c1b", file_type="c1b")
        assert req.file_type == "c1b"

    def test_optional_driver_and_vehicle_ids(self):
        """driver_id and vehicle_id default to None."""
        req = TachoImportRequest(file_path="/data/file.ddd")
        assert req.driver_id is None
        assert req.vehicle_id is None

    def test_with_driver_and_vehicle_ids(self):
        """Both optional IDs can be set explicitly."""
        req = TachoImportRequest(
            file_path="/data/file.ddd",
            driver_id=42,
            vehicle_id=7,
        )
        assert req.driver_id == 42
        assert req.vehicle_id == 7


class TestDriverActivity:
    """Fields: driver_id, driver_name, date, activity_type, start/end_time, duration_minutes."""

    @pytest.mark.parametrize(
        "activity_type",
        ["driving", "rest", "work", "available"],
    )
    def test_valid_activity_types(self, activity_type):
        """All expected activity type strings are accepted."""
        da = DriverActivity(
            driver_name="John Doe",
            date=date(2026, 7, 15),
            activity_type=activity_type,
            start_time=datetime(2026, 7, 15, 8, 0),
            end_time=datetime(2026, 7, 15, 10, 0),
            duration_minutes=120.0,
        )
        assert da.activity_type == activity_type
        assert da.duration_minutes == 120.0

    def test_unknown_activity_type_accepted(self):
        """Model accepts any string for activity_type (no Literal constraint)."""
        da = DriverActivity(
            driver_name="Jane",
            date=date(2026, 7, 15),
            activity_type="unknown_value",
            start_time=datetime(2026, 7, 15, 8, 0),
            end_time=datetime(2026, 7, 15, 9, 0),
            duration_minutes=60.0,
        )
        assert da.activity_type == "unknown_value"

    def test_minimal_required_fields(self):
        """Only required fields provided, optionals get defaults."""
        da = DriverActivity(
            driver_name="Driver",
            date=date(2026, 7, 15),
            activity_type="driving",
            start_time=datetime(2026, 7, 15, 8, 0),
            end_time=datetime(2026, 7, 15, 12, 0),
            duration_minutes=240.0,
        )
        assert da.driver_id is None
        assert da.driver_name == "Driver"
        assert da.date == date(2026, 7, 15)
        assert da.start_time == datetime(2026, 7, 15, 8, 0)
        assert da.end_time == datetime(2026, 7, 15, 12, 0)
        assert da.duration_minutes == 240.0

    def test_with_driver_id(self):
        """driver_id can be set optionally."""
        da = DriverActivity(
            driver_id=1,
            driver_name="Alice",
            date=date(2026, 7, 15),
            activity_type="rest",
            start_time=datetime(2026, 7, 15, 12, 0),
            end_time=datetime(2026, 7, 15, 12, 45),
            duration_minutes=45.0,
        )
        assert da.driver_id == 1

    def test_duration_minutes_zero(self):
        """Zero duration is valid (e.g. an empty activity block)."""
        da = DriverActivity(
            driver_name="Bob",
            date=date(2026, 7, 15),
            activity_type="work",
            start_time=datetime(2026, 7, 15, 8, 0),
            end_time=datetime(2026, 7, 15, 8, 0),
            duration_minutes=0.0,
        )
        assert da.duration_minutes == 0.0

    def test_duration_minutes_negative(self):
        """Negative duration is allowed by the model (no constraint)."""
        da = DriverActivity(
            driver_name="Bob",
            date=date(2026, 7, 15),
            activity_type="work",
            start_time=datetime(2026, 7, 15, 10, 0),
            end_time=datetime(2026, 7, 15, 8, 0),
            duration_minutes=-120.0,
        )
        assert da.duration_minutes == -120.0

    def test_missing_date_raises(self):
        with pytest.raises(ValidationError):
            DriverActivity(
                driver_name="Test",
                activity_type="driving",
                start_time=datetime(2026, 7, 15, 8, 0),
                end_time=datetime(2026, 7, 15, 10, 0),
                duration_minutes=120.0,
            )

    def test_missing_start_time_raises(self):
        with pytest.raises(ValidationError):
            DriverActivity(
                driver_name="Test",
                date=date(2026, 7, 15),
                activity_type="driving",
                end_time=datetime(2026, 7, 15, 10, 0),
                duration_minutes=120.0,
            )

    def test_missing_end_time_raises(self):
        with pytest.raises(ValidationError):
            DriverActivity(
                driver_name="Test",
                date=date(2026, 7, 15),
                activity_type="driving",
                start_time=datetime(2026, 7, 15, 8, 0),
                duration_minutes=120.0,
            )

    def test_missing_duration_minutes_raises(self):
        with pytest.raises(ValidationError):
            DriverActivity(
                driver_name="Test",
                date=date(2026, 7, 15),
                activity_type="driving",
                start_time=datetime(2026, 7, 15, 8, 0),
                end_time=datetime(2026, 7, 15, 10, 0),
            )

    def test_timestamp_fields(self):
        """start_time and end_time store datetime precisely."""
        dt1 = datetime(2026, 7, 15, 8, 30, 45, 123456)
        dt2 = datetime(2026, 7, 15, 17, 15, 0)
        da = DriverActivity(
            driver_name="Precise",
            date=date(2026, 7, 15),
            activity_type="driving",
            start_time=dt1,
            end_time=dt2,
            duration_minutes=524.0,
        )
        assert da.start_time == dt1
        assert da.end_time == dt2


class TestVehicleActivity:
    """Fields: vehicle_id, plate, date, odometer_start/end, distance_km, max_speed."""

    def test_minimal(self):
        """Minimal required fields."""
        va = VehicleActivity(
            plate="AB123CD",
            date=date(2026, 7, 15),
            odometer_start=10000.0,
            odometer_end=10500.0,
            distance_km=500.0,
        )
        assert va.plate == "AB123CD"
        assert va.date == date(2026, 7, 15)
        assert va.odometer_start == 10000.0
        assert va.odometer_end == 10500.0
        assert va.distance_km == 500.0
        assert va.vehicle_id is None
        assert va.max_speed is None

    def test_with_all_fields(self):
        """All fields including optionals."""
        va = VehicleActivity(
            vehicle_id=5,
            plate="CD456EF",
            date=date(2026, 7, 16),
            odometer_start=20000.0,
            odometer_end=20450.0,
            distance_km=450.0,
            max_speed=88.5,
        )
        assert va.vehicle_id == 5
        assert va.max_speed == 88.5

    def test_optional_max_speed_default_none(self):
        va = VehicleActivity(
            plate="XX999YY",
            date=date(2026, 7, 17),
            odometer_start=0.0,
            odometer_end=100.0,
            distance_km=100.0,
        )
        assert va.max_speed is None

    def test_optional_vehicle_id_default_none(self):
        va = VehicleActivity(
            plate="ZZ123WW",
            date=date(2026, 7, 18),
            odometer_start=5000.0,
            odometer_end=5500.0,
            distance_km=500.0,
        )
        assert va.vehicle_id is None

    def test_zero_distance(self):
        """Zero distance is allowed (vehicle didn't move)."""
        va = VehicleActivity(
            plate="AB000CD",
            date=date(2026, 7, 15),
            odometer_start=10000.0,
            odometer_end=10000.0,
            distance_km=0.0,
        )
        assert va.distance_km == 0.0
        assert va.odometer_start == va.odometer_end

    def test_negative_odometer(self):
        """Negative odometer values are allowed by the model."""
        va = VehicleActivity(
            plate="ERR001",
            date=date(2026, 7, 15),
            odometer_start=-1.0,
            odometer_end=0.0,
            distance_km=1.0,
        )
        assert va.odometer_start == -1.0
        assert va.distance_km == 1.0

    def test_large_values(self):
        """Large float values are accepted."""
        va = VehicleActivity(
            plate="BIG001",
            date=date(2026, 7, 15),
            odometer_start=999999.999,
            odometer_end=1000500.0,
            distance_km=500.001,
        )
        assert va.odometer_start == 999999.999
        assert va.distance_km == 500.001

    def test_missing_plate_raises(self):
        with pytest.raises(ValidationError):
            VehicleActivity(
                date=date(2026, 7, 15),
                odometer_start=0,
                odometer_end=100,
                distance_km=100,
            )

    def test_missing_date_raises(self):
        with pytest.raises(ValidationError):
            VehicleActivity(
                plate="PLATE01",
                odometer_start=0,
                odometer_end=100,
                distance_km=100,
            )

    def test_max_speed_negative(self):
        """Negative max_speed is allowed by the model."""
        va = VehicleActivity(
            plate="NEG001",
            date=date(2026, 7, 15),
            odometer_start=0,
            odometer_end=100,
            distance_km=100,
            max_speed=-5.0,
        )
        assert va.max_speed == -5.0


class TestTachoImportResult:
    """Import ID, file info, status, counts, errors/warnings, timestamp."""

    @pytest.mark.parametrize(
        "status",
        ["success", "partial", "failed"],
    )
    def test_valid_status_values(self, status):
        """All expected status values are accepted."""
        res = TachoImportResult(
            import_id=1,
            file_path="/data/file.ddd",
            file_type="ddd",
            status=status,
        )
        assert res.status == status

    def test_arbitrary_status_accepted(self):
        """Model accepts any string for status (no Literal constraint)."""
        res = TachoImportResult(
            import_id=2,
            file_path="/data/file.c1b",
            file_type="c1b",
            status="pending",
        )
        assert res.status == "pending"

    def test_minimal(self):
        """Minimal required fields, defaults for the rest."""
        res = TachoImportResult(
            import_id=1,
            file_path="/data/file.ddd",
            file_type="ddd",
            status="success",
        )
        assert res.import_id == 1
        assert res.driver_activities == 0
        assert res.vehicle_activities == 0
        assert res.errors == []
        assert res.warnings == []
        assert res.imported_at is None

    def test_with_all_fields(self):
        """All fields populated."""
        now = datetime(2026, 7, 15, 14, 30, 0)
        res = TachoImportResult(
            import_id=10,
            file_path="/data/batch.esm",
            file_type="esm",
            status="partial",
            driver_activities=5,
            vehicle_activities=3,
            errors=["Corrupt block at offset 2048"],
            warnings=["Driver ID mismatch on record 7"],
            imported_at=now,
        )
        assert res.import_id == 10
        assert res.driver_activities == 5
        assert res.vehicle_activities == 3
        assert len(res.errors) == 1
        assert len(res.warnings) == 1
        assert res.imported_at == now

    def test_zero_counts(self):
        """Import with no activities parsed."""
        res = TachoImportResult(
            import_id=0,
            file_path="/data/empty.ddd",
            file_type="ddd",
            status="success",
            driver_activities=0,
            vehicle_activities=0,
        )
        assert res.driver_activities == 0
        assert res.vehicle_activities == 0

    def test_negative_import_id(self):
        """Negative import_id is allowed (no constraint)."""
        res = TachoImportResult(
            import_id=-1,
            file_path="/data/test.ddd",
            file_type="ddd",
            status="failed",
        )
        assert res.import_id == -1

    def test_multiple_errors(self):
        """Multiple error and warning strings."""
        errors = ["err1", "err2", "err3"]
        warnings = ["warn1"]
        res = TachoImportResult(
            import_id=5,
            file_path="/data/test.ddd",
            file_type="ddd",
            status="failed",
            errors=errors,
            warnings=warnings,
        )
        assert res.errors == errors
        assert res.warnings == warnings

    def test_missing_import_id_raises(self):
        with pytest.raises(ValidationError):
            TachoImportResult(
                file_path="/data/file.ddd",
                file_type="ddd",
                status="success",
            )

    def test_missing_file_path_raises(self):
        with pytest.raises(ValidationError):
            TachoImportResult(
                import_id=1,
                file_type="ddd",
                status="success",
            )


class TestDriverHoursAnalysis:
    """Compliance flag, driving hours edge cases, rest period validation."""

    def test_minimal(self):
        """Minimal required fields."""
        dha = DriverHoursAnalysis(
            driver_name="John",
            date=date(2026, 7, 15),
            total_driving_hours=8.0,
            total_rest_hours=9.0,
            total_work_hours=7.0,
            is_compliant=True,
        )
        assert dha.driver_id is None
        assert dha.driver_name == "John"
        assert dha.total_driving_hours == 8.0
        assert dha.total_rest_hours == 9.0
        assert dha.total_work_hours == 7.0
        assert dha.is_compliant is True
        assert dha.violations == []
        assert dha.warnings == []

    @pytest.mark.parametrize(
        "is_compliant",
        [True, False],
    )
    def test_is_compliant_boolean(self, is_compliant):
        """is_compliant accepts both True and False."""
        dha = DriverHoursAnalysis(
            driver_name="Alice",
            date=date(2026, 7, 15),
            total_driving_hours=4.5,
            total_rest_hours=11.0,
            total_work_hours=8.5,
            is_compliant=is_compliant,
        )
        assert dha.is_compliant is is_compliant

    @pytest.mark.parametrize(
        "driving_hours",
        [0.0, 4.5, 9.0, 10.0, 24.0, 100.0],
    )
    def test_driving_hours_various(self, driving_hours):
        """Various driving hour values — no constraint on the model."""
        dha = DriverHoursAnalysis(
            driver_name="Bob",
            date=date(2026, 7, 15),
            total_driving_hours=driving_hours,
            total_rest_hours=0.0,
            total_work_hours=0.0,
            is_compliant=True,
        )
        assert dha.total_driving_hours == driving_hours

    def test_driving_hours_negative(self):
        """Negative driving hours are allowed (no constraint)."""
        dha = DriverHoursAnalysis(
            driver_name="Edge",
            date=date(2026, 7, 15),
            total_driving_hours=-1.0,
            total_rest_hours=0.0,
            total_work_hours=0.0,
            is_compliant=False,
        )
        assert dha.total_driving_hours == -1.0

    def test_driving_hours_zero(self):
        """Zero driving hours is valid."""
        dha = DriverHoursAnalysis(
            driver_name="RestDay",
            date=date(2026, 7, 15),
            total_driving_hours=0.0,
            total_rest_hours=24.0,
            total_work_hours=0.0,
            is_compliant=True,
        )
        assert dha.total_driving_hours == 0.0

    def test_rest_hours_all_zero(self):
        """All hours zero is valid."""
        dha = DriverHoursAnalysis(
            driver_name="Off",
            date=date(2026, 7, 15),
            total_driving_hours=0.0,
            total_rest_hours=0.0,
            total_work_hours=0.0,
            is_compliant=True,
        )
        assert dha.total_rest_hours == 0.0
        assert dha.total_work_hours == 0.0

    def test_with_violations_and_warnings(self):
        """Violations and warnings lists populated."""
        dha = DriverHoursAnalysis(
            driver_name="Violator",
            date=date(2026, 7, 15),
            total_driving_hours=11.0,
            total_rest_hours=6.0,
            total_work_hours=7.0,
            is_compliant=False,
            violations=["Exceeded 10h daily driving limit"],
            warnings=["Rest period less than 9h"],
        )
        assert len(dha.violations) == 1
        assert dha.violations[0] == "Exceeded 10h daily driving limit"
        assert dha.warnings[0] == "Rest period less than 9h"

    def test_with_driver_id(self):
        """Optional driver_id can be set."""
        dha = DriverHoursAnalysis(
            driver_id=42,
            driver_name="Alice",
            date=date(2026, 7, 15),
            total_driving_hours=8.0,
            total_rest_hours=9.0,
            total_work_hours=7.0,
            is_compliant=True,
        )
        assert dha.driver_id == 42

    def test_missing_driver_name_raises(self):
        with pytest.raises(ValidationError):
            DriverHoursAnalysis(
                date=date(2026, 7, 15),
                total_driving_hours=8.0,
                total_rest_hours=9.0,
                total_work_hours=7.0,
                is_compliant=True,
            )

    def test_missing_date_raises(self):
        with pytest.raises(ValidationError):
            DriverHoursAnalysis(
                driver_name="Test",
                total_driving_hours=8.0,
                total_rest_hours=9.0,
                total_work_hours=7.0,
                is_compliant=True,
            )

    def test_missing_is_compliant_raises(self):
        with pytest.raises(ValidationError):
            DriverHoursAnalysis(
                driver_name="Test",
                date=date(2026, 7, 15),
                total_driving_hours=8.0,
                total_rest_hours=9.0,
                total_work_hours=7.0,
            )

    def test_rest_period_edge_case(self):
        """Rest hours can be any float, including greater than 24."""
        dha = DriverHoursAnalysis(
            driver_name="MultiDay",
            date=date(2026, 7, 15),
            total_driving_hours=2.0,
            total_rest_hours=48.0,
            total_work_hours=4.0,
            is_compliant=True,
        )
        assert dha.total_rest_hours == 48.0


class TestFleetTachoSummary:
    """Average speed, distance, driving hours edge cases."""

    def test_minimal(self):
        """Minimal required fields."""
        fts = FleetTachoSummary(
            plate="AB123CD",
            date=date(2026, 7, 15),
            total_distance_km=500.0,
            total_driving_hours=8.0,
            average_speed=62.5,
            max_speed=88.0,
            driver_count=1,
        )
        assert fts.plate == "AB123CD"
        assert fts.date == date(2026, 7, 15)
        assert fts.total_distance_km == 500.0
        assert fts.total_driving_hours == 8.0
        assert fts.average_speed == 62.5
        assert fts.max_speed == 88.0
        assert fts.driver_count == 1
        assert fts.vehicle_id is None

    def test_with_vehicle_id(self):
        """Optional vehicle_id can be set."""
        fts = FleetTachoSummary(
            vehicle_id=3,
            plate="CD456EF",
            date=date(2026, 7, 16),
            total_distance_km=300.0,
            total_driving_hours=5.0,
            average_speed=60.0,
            max_speed=90.0,
            driver_count=2,
        )
        assert fts.vehicle_id == 3
        assert fts.driver_count == 2

    def test_average_speed_normal(self):
        """average_speed = total_distance_km / total_driving_hours."""
        fts = FleetTachoSummary(
            plate="SPD001",
            date=date(2026, 7, 15),
            total_distance_km=500.0,
            total_driving_hours=10.0,
            average_speed=50.0,
            max_speed=80.0,
            driver_count=1,
        )
        assert fts.average_speed == 50.0
        # Verify the math holds
        assert fts.total_distance_km / fts.total_driving_hours == 50.0

    def test_average_speed_fractional(self):
        """Fractional average speed."""
        fts = FleetTachoSummary(
            plate="SPD002",
            date=date(2026, 7, 15),
            total_distance_km=123.4,
            total_driving_hours=2.5,
            average_speed=49.36,
            max_speed=65.0,
            driver_count=1,
        )
        assert fts.average_speed == 49.36

    def test_average_speed_zero_distance(self):
        """Zero distance yields zero average speed."""
        fts = FleetTachoSummary(
            plate="SPD003",
            date=date(2026, 7, 15),
            total_distance_km=0.0,
            total_driving_hours=5.0,
            average_speed=0.0,
            max_speed=0.0,
            driver_count=1,
        )
        assert fts.average_speed == 0.0

    def test_average_speed_zero_hours_zero_distance(self):
        """Both zero — average speed is zero."""
        fts = FleetTachoSummary(
            plate="SPD004",
            date=date(2026, 7, 15),
            total_distance_km=0.0,
            total_driving_hours=0.0,
            average_speed=0.0,
            max_speed=0.0,
            driver_count=0,
        )
        assert fts.average_speed == 0.0

    def test_average_speed_high_value(self):
        """High average speed (e.g. motorway)."""
        fts = FleetTachoSummary(
            plate="SPD005",
            date=date(2026, 7, 15),
            total_distance_km=800.0,
            total_driving_hours=6.0,
            average_speed=133.333,
            max_speed=95.0,
            driver_count=1,
        )
        assert fts.average_speed == 133.333

    def test_negative_distance(self):
        """Negative distance is allowed by the model."""
        fts = FleetTachoSummary(
            plate="NEGDIST",
            date=date(2026, 7, 15),
            total_distance_km=-100.0,
            total_driving_hours=5.0,
            average_speed=-20.0,
            max_speed=0.0,
            driver_count=1,
        )
        assert fts.total_distance_km == -100.0
        assert fts.average_speed == -20.0

    def test_negative_driving_hours(self):
        """Negative driving hours are allowed by the model."""
        fts = FleetTachoSummary(
            plate="NEGHRS",
            date=date(2026, 7, 15),
            total_distance_km=100.0,
            total_driving_hours=-5.0,
            average_speed=-20.0,
            max_speed=0.0,
            driver_count=1,
        )
        assert fts.total_driving_hours == -5.0

    def test_zero_driver_count(self):
        """Zero driver count is valid."""
        fts = FleetTachoSummary(
            plate="NO_DRV",
            date=date(2026, 7, 15),
            total_distance_km=0.0,
            total_driving_hours=0.0,
            average_speed=0.0,
            max_speed=0.0,
            driver_count=0,
        )
        assert fts.driver_count == 0

    def test_missing_plate_raises(self):
        with pytest.raises(ValidationError):
            FleetTachoSummary(
                date=date(2026, 7, 15),
                total_distance_km=100.0,
                total_driving_hours=5.0,
                average_speed=20.0,
                max_speed=50.0,
                driver_count=1,
            )

    def test_missing_date_raises(self):
        with pytest.raises(ValidationError):
            FleetTachoSummary(
                plate="MISSDATE",
                total_distance_km=100.0,
                total_driving_hours=5.0,
                average_speed=20.0,
                max_speed=50.0,
                driver_count=1,
            )

    def test_missing_max_speed_raises(self):
        with pytest.raises(ValidationError):
            FleetTachoSummary(
                plate="MISSMAX",
                date=date(2026, 7, 15),
                total_distance_km=100.0,
                total_driving_hours=5.0,
                average_speed=20.0,
                driver_count=1,
            )

    def test_missing_driver_count_raises(self):
        with pytest.raises(ValidationError):
            FleetTachoSummary(
                plate="MISSCNT",
                date=date(2026, 7, 15),
                total_distance_km=100.0,
                total_driving_hours=5.0,
                average_speed=20.0,
                max_speed=50.0,
            )


class TestTachoResultAliases:
    """Typed result alias types instantiation."""

    def test_import_operation_result_success(self):
        """TachoImportOperationResult wrapping a TachoImportResult."""
        inner = TachoImportResult(
            import_id=1,
            file_path="/data/file.ddd",
            file_type="ddd",
            status="success",
            driver_activities=10,
            vehicle_activities=5,
        )
        result = TachoImportOperationResult(success=True, data=inner)
        assert result.success is True
        assert result.data is not None
        assert result.data.import_id == 1
        assert result.data.status == "success"
        assert result.errors == []

    def test_import_operation_result_failure(self):
        """TachoImportOperationResult with errors and no data."""
        err = ErrorDetail(field="file_path", message="File not found", code="NOT_FOUND")
        result = TachoImportOperationResult(
            success=False,
            data=None,
            errors=[err],
        )
        assert result.success is False
        assert result.data is None
        assert len(result.errors) == 1
        assert result.errors[0].message == "File not found"

    def test_analysis_result_success(self):
        """TachoAnalysisResult wrapping a DriverHoursAnalysis."""
        inner = DriverHoursAnalysis(
            driver_name="Alice",
            date=date(2026, 7, 15),
            total_driving_hours=8.0,
            total_rest_hours=9.0,
            total_work_hours=7.0,
            is_compliant=True,
        )
        result = TachoAnalysisResult(success=True, data=inner)
        assert result.success is True
        assert result.data.is_compliant is True
        assert result.data.driver_name == "Alice"

    def test_analysis_result_failure(self):
        result = TachoAnalysisResult(
            success=False,
            data=None,
            errors=[ErrorDetail(field="date", message="Invalid date", code="INVALID")],
        )
        assert result.success is False
        assert result.data is None

    def test_fleet_summary_result_success(self):
        """TachoFleetSummaryResult wrapping a list of FleetTachoSummary."""
        items = [
            FleetTachoSummary(
                plate="AB123CD",
                date=date(2026, 7, 15),
                total_distance_km=500.0,
                total_driving_hours=8.0,
                average_speed=62.5,
                max_speed=88.0,
                driver_count=1,
            ),
            FleetTachoSummary(
                plate="CD456EF",
                date=date(2026, 7, 15),
                total_distance_km=300.0,
                total_driving_hours=5.0,
                average_speed=60.0,
                max_speed=90.0,
                driver_count=2,
            ),
        ]
        result = TachoFleetSummaryResult(success=True, data=items)
        assert result.success is True
        assert len(result.data) == 2
        assert result.data[0].plate == "AB123CD"
        assert result.data[1].average_speed == 60.0

    def test_fleet_summary_result_empty_list(self):
        """Empty list is a valid data payload."""
        result = TachoFleetSummaryResult(success=True, data=[])
        assert result.success is True
        assert result.data == []

    def test_fleet_summary_result_failure(self):
        result = TachoFleetSummaryResult(
            success=False,
            data=None,
            errors=[ErrorDetail(field="data", message="No fleet data", code="EMPTY")],
        )
        assert result.success is False
        assert result.data is None
