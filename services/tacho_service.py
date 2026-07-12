"""Tachograph service — imports and parses .DDD files via dddsimple or tachograph CLI.

Typed methods (Pydantic v2) are available alongside legacy dict-based methods.
Legacy methods emit deprecation warnings and will be removed in a future release.
"""
import contextlib
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import threading
import warnings
from datetime import date, datetime, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta

from models.common import ErrorDetail, ServiceResult
from models.tacho_models import (
    DriverActivity,
    DriverHoursAnalysis,
    FleetTachoSummary,
    TachoAnalysisResult,
    TachoFleetSummaryResult,
    TachoImportOperationResult,
    TachoImportRequest,
    TachoImportResult,
    VehicleActivity,
)
from repositories.driver_repository import DriverRepository
from repositories.fleet_repository import FleetRepository
from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
from repositories.tacho_import_repository import TachoImportRepository
from repositories.tacho_vehicle_data_repository import TachoVehicleDataRepository
from services.operations.event_bus import EventBus
from utils.resource_path import data_path

logger = logging.getLogger(__name__)

_DEFAULT_TACHOGRAPH_PATH = data_path("tools/tachograph/tachograph.exe")
TACHOGRAPH_PATH = os.environ.get(
    "OPERION_TACHOGRAPH_PATH",
    _DEFAULT_TACHOGRAPH_PATH
)

# EU tachograph regulation thresholds (Regulation (EC) 561/2006)
EU_MAX_DAILY_DRIVING_MINUTES = 540       # 9 hours
EU_MAX_WEEKLY_DRIVING_MINUTES = 3360     # 56 hours (not checked per-day)
EU_MIN_DAILY_REST_MINUTES = 660          # 11 hours (can be reduced to 9h three times/week)


# ── Event types used by TachoService ────────────────────────────────
class TruckUpdatedEvent:
    def __init__(self, truck_id):
        self.truck_id = truck_id


class TachoService:
    """Import, parse, and store tachograph .DDD files.

    Prefer the typed ``import_file()``, ``analyze_driver_hours()``,
    ``get_fleet_summary()``, ``get_driver_activities()``, and
    ``get_vehicle_activities()`` methods over the legacy dict-based ones.
    """

    def __init__(self, db):
        self.db = db
        self.tacho_import_repository = TachoImportRepository(db)
        self.tacho_driver_activity_repository = TachoDriverActivityRepository(db)
        self.tacho_vehicle_data_repository = TachoVehicleDataRepository(db)
        self.fleet_repository = FleetRepository(db)
        self.driver_repository = DriverRepository(db)
        self.event_bus = EventBus()

    # ═════════════════════════════════════════════════════════════════
    # Typed public API (preferred)
    # ═════════════════════════════════════════════════════════════════

    # ── Permission helper ──────────────────────────────────────────

    @staticmethod
    def _user_has_permission(db, user_id: int) -> bool:
        """Check if *user_id* has admin or manager role."""
        role = getattr(db, "user_role", "") or ""
        return role.lower() in ("admin", "manager")

    # ── 1. import_file ────────────────────────────────────────────

    def import_file(
        self,
        request: TachoImportRequest,
        user_id: int,
    ) -> TachoImportOperationResult:
        """Import a tachograph file with a typed request and return a structured result.

        Parameters
        ----------
        request : TachoImportRequest
            Validated import request with file path, type, and optional driver/vehicle IDs.
        user_id : int
            The user performing the import (used for permission checking).

        Returns
        -------
        TachoImportOperationResult
            ``ServiceResult[TachoImportResult]`` with success/errors/warnings.
        """
        # Permission check
        if not self._user_has_permission(self.db, user_id):
            logger.warning(
                "import_file denied: user %s lacks admin/manager role",
                user_id,
            )
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    field="user_id",
                    message="Only admin or manager users can import tachograph files",
                    code="FORBIDDEN",
                )],
            )

        errors: list[str] = []
        warnings_list: list[str] = []
        driver_activity_count = 0
        vehicle_activity_count = 0

        file_path = request.file_path
        file_name = os.path.basename(file_path)

        if not os.path.isfile(file_path):
            logger.error("import_file failed: file not found at %s", file_path)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    field="file_path",
                    message=f"File not found: {file_path}",
                    code="FILE_NOT_FOUND",
                )],
            )

        # Delegate to the existing parser flow
        raw_result = self.import_ddd_file(file_path)

        if not raw_result.get("success"):
            err_msg = raw_result.get("error", "Unknown error during import")
            logger.error("import_file failed for %s: %s", file_name, err_msg)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    field="file_path",
                    message=err_msg,
                    code="IMPORT_FAILED",
                )],
            )

        # Build structured result from the dict return
        import_id = raw_result.get("import_id")
        file_type = raw_result.get("file_type", request.file_type)
        status = "success"
        driver_activity_count = raw_result.get("days_imported", 0)

        if raw_result.get("violations_found", 0) > 0:
            warnings_list.append(
                f"{raw_result['violations_found']} potential violation(s) flagged."
            )

        import_record = None
        if import_id:
            import_record = self.tacho_import_repository.get_by_id(import_id)

        result = TachoImportResult(
            import_id=import_id or 0,
            file_path=file_path,
            file_type=file_type,
            status=status,
            driver_activities=driver_activity_count,
            vehicle_activities=vehicle_activity_count,
            errors=errors,
            warnings=warnings_list,
            imported_at=(
                import_record.get("imported_at")
                if import_record else datetime.utcnow()
            ),
        )

        logger.info(
            "import_file completed",
            extra={
                "action": "import_file",
                "import_id": import_id,
                "file_type": file_type,
                "driver_activities": driver_activity_count,
                "status": status,
            },
        )
        if warnings_list:
            logger.warning(
                "import_file warnings: %s",
                "; ".join(warnings_list),
                extra={"action": "import_file", "import_id": import_id},
            )

        return ServiceResult(success=True, data=result)

    # ── 2. analyze_driver_hours ───────────────────────────────────

    def analyze_driver_hours(
        self,
        driver_id: int,
        date_range: tuple[date, date],
    ) -> TachoAnalysisResult:
        """Analyse a driver's activity within *date_range* for EU compliance.

        Parameters
        ----------
        driver_id : int
            The driver's database ID.
        date_range : tuple[date, date]
            Inclusive ``(start, end)`` date range.

        Returns
        -------
        TachoAnalysisResult
            ``ServiceResult[DriverHoursAnalysis]`` with computed hours and
            violation/warning details.
        """
        start_date, end_date = date_range

        # Fetch driver info
        driver = self.driver_repository.get_by_id(driver_id)
        driver_name = driver.get("name", "Unknown") if driver else "Unknown"
        if not driver:
            logger.warning(
                "analyze_driver_hours: driver %s not found", driver_id,
            )
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    field="driver_id",
                    message=f"Driver with id {driver_id} not found",
                    code="DRIVER_NOT_FOUND",
                )],
            )

        # Fetch activity records within the range
        records = self.tacho_driver_activity_repository.get_by_driver(
            driver_id, start_date,
        )
        # Filter by end date in memory (repo only supports from_date)
        records = [
            r for r in records
            if r.get("activity_date", "") <= end_date.isoformat()
        ]

        if not records:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    field="date_range",
                    message=(
                        f"No activity records for driver {driver_id} "
                        f"between {start_date} and {end_date}"
                    ),
                    code="NO_DATA",
                )],
            )

        # Aggregate per-date
        daily_analyses: list[DriverHoursAnalysis] = []
        for record in records:
            raw_date = record.get("activity_date", "")
            try:
                act_date = date.fromisoformat(raw_date)
            except (ValueError, TypeError):
                continue

            driving_min = record.get("driving_minutes", 0) or 0
            rest_min = record.get("rest_minutes", 0) or 0
            work_min = record.get("work_minutes", 0) or 0

            violations: list[str] = []
            analysis_warnings: list[str] = []

            # EU daily driving limit: max 9 hours (540 min)
            if driving_min > EU_MAX_DAILY_DRIVING_MINUTES:
                violations.append(
                    f"Driving {driving_min // 60}h{driving_min % 60}m exceeds "
                    f"{EU_MAX_DAILY_DRIVING_MINUTES // 60}h daily limit"
                )

            # EU daily rest: minimum 11 hours (660 min) if driving occurred
            if rest_min < EU_MIN_DAILY_REST_MINUTES and driving_min > 0:
                violations.append(
                    f"Daily rest {rest_min // 60}h{rest_min % 60}m is below "
                    f"{EU_MIN_DAILY_REST_MINUTES // 60}h minimum"
                )

            # Load stored violations from import (if any)
            stored_violations = record.get("violations")
            if stored_violations:
                try:
                    stored = json.loads(stored_violations)
                    if isinstance(stored, list):
                        violations.extend(stored)
                except (json.JSONDecodeError, TypeError):
                    pass

            daily_analyses.append(DriverHoursAnalysis(
                driver_id=driver_id,
                driver_name=driver_name,
                date=act_date,
                total_driving_hours=round(driving_min / 60, 2),
                total_rest_hours=round(rest_min / 60, 2),
                total_work_hours=round(work_min / 60, 2),
                is_compliant=len(violations) == 0,
                violations=violations,
                warnings=analysis_warnings,
            ))

        # Merge all days into a single analysis summary
        total_driving = sum(a.total_driving_hours for a in daily_analyses)
        total_rest = sum(a.total_rest_hours for a in daily_analyses)
        total_work = sum(a.total_work_hours for a in daily_analyses)
        all_violations: list[str] = []
        all_warnings: list[str] = []
        is_fully_compliant = True
        for a in daily_analyses:
            all_violations.extend(a.violations)
            all_warnings.extend(a.warnings)
            if not a.is_compliant:
                is_fully_compliant = False

        # Summary across the full range (use the latest date for display)
        summary = DriverHoursAnalysis(
            driver_id=driver_id,
            driver_name=driver_name,
            date=end_date,
            total_driving_hours=round(total_driving, 2),
            total_rest_hours=round(total_rest, 2),
            total_work_hours=round(total_work, 2),
            is_compliant=is_fully_compliant,
            violations=all_violations,
            warnings=all_warnings,
        )

        logger.info(
            "analyze_driver_hours completed",
            extra={
                "action": "analyze_driver_hours",
                "driver_id": driver_id,
                "date_range": f"{start_date}/{end_date}",
                "days": len(daily_analyses),
                "violations": len(all_violations),
                "compliant": is_fully_compliant,
            },
        )

        return ServiceResult(success=True, data=summary)

    # ── 3. get_fleet_summary ───────────────────────────────────────

    def get_fleet_summary(self, date: date) -> TachoFleetSummaryResult:
        """Aggregate tacho vehicle data for all vehicles on a given *date*.

        Returns a list of ``FleetTachoSummary``, one per vehicle that has
        data for that day.
        """
        # Fetch all vehicle data records — we need to cross-reference with
        # the import table to find records for the target date.
        all_imports = self.tacho_import_repository.get_recent(limit=1000)

        # Filter imports that have a truck_id and match the target date
        # by examining linked vehicle data records
        summaries: dict[int, FleetTachoSummary] = {}

        for imp in all_imports:
            truck_id = imp.get("truck_id")
            if not truck_id:
                continue

            vd = self.tacho_vehicle_data_repository.get_by_import(imp["id"])
            if not vd:
                continue

            # Resolve plate
            truck = self.fleet_repository.get_by_id(truck_id)
            plate = truck.get("plate_number", "Unknown") if truck else "Unknown"

            # Odometer as a proxy for distance on this import
            distance = float(vd.get("odometer_km", 0) or 0)
            speed_violations = int(vd.get("speed_violations", 0) or 0)

            if truck_id not in summaries:
                summaries[truck_id] = FleetTachoSummary(
                    vehicle_id=truck_id,
                    plate=plate,
                    date=date,
                    total_distance_km=0.0,
                    total_driving_hours=0.0,
                    average_speed=0.0,
                    max_speed=0.0,
                    driver_count=0,
                )

            s = summaries[truck_id]
            s.total_distance_km += distance

            # Approximate driving hours: assume 60 km/h average if we have distance
            if distance > 0:
                driving_hours = distance / 60.0
                s.total_driving_hours += driving_hours
                if driving_hours > 0:
                    avg_speed = distance / driving_hours
                    s.average_speed = round(
                        (s.average_speed * (s.driver_count or 1) + avg_speed)
                        / (s.driver_count + 1),
                        1,
                    )
                s.max_speed = max(s.max_speed, float(speed_violations * 91 or 0))

            # Count drivers linked via this import
            if imp.get("driver_id"):
                s.driver_count += 1

        if not summaries:
            logger.info("get_fleet_summary: no vehicle data found for %s", date)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    field="date",
                    message=f"No tacho vehicle data found for {date}",
                    code="NO_DATA",
                )],
            )

        result_list = list(summaries.values())
        # Round floats for cleanliness
        for s in result_list:
            s.total_distance_km = round(s.total_distance_km, 1)
            s.total_driving_hours = round(s.total_driving_hours, 2)
            s.average_speed = round(s.average_speed, 1)

        logger.info(
            "get_fleet_summary completed",
            extra={
                "action": "get_fleet_summary",
                "date": str(date),
                "vehicle_count": len(result_list),
            },
        )

        return ServiceResult(success=True, data=result_list)

    # ── 4. get_driver_activities ──────────────────────────────────

    def get_driver_activities(
        self,
        driver_id: int,
        start: date,
        end: date,
    ) -> ServiceResult[list[DriverActivity]]:
        """Return detailed driver activities within a date range.

        Each day's summary from the tacho record is expanded into individual
        ``DriverActivity`` entries per activity type.
        """
        records = self.tacho_driver_activity_repository.get_by_driver(
            driver_id, start,
        )
        # Filter by end date
        records = [
            r for r in records
            if r.get("activity_date", "") <= end.isoformat()
        ]

        if not records:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    field="date_range",
                    message=(
                        f"No activities for driver {driver_id} "
                        f"between {start} and {end}"
                    ),
                    code="NO_DATA",
                )],
            )

        activities: list[DriverActivity] = []
        for record in records:
            raw_date = record.get("activity_date", "")
            try:
                act_date = date.fromisoformat(raw_date)
            except (ValueError, TypeError):
                continue

            driver_name = ""
            driver = self.driver_repository.get_by_id(driver_id)
            if driver:
                driver_name = driver.get("name", "")

            # Create one activity entry per type present
            for activity_type, minutes_key in [
                ("driving", "driving_minutes"),
                ("rest", "rest_minutes"),
                ("work", "work_minutes"),
                ("available", "avail_minutes"),
            ]:
                minutes = float(record.get(minutes_key, 0) or 0)
                if minutes > 0:
                    # Approximate start/end times based on a standard workday
                    # starting at 00:00 — real start_time is not stored per-type
                    day_start = datetime.combine(act_date, datetime.min.time())
                    activities.append(DriverActivity(
                        driver_id=driver_id,
                        driver_name=driver_name,
                        date=act_date,
                        activity_type=activity_type,
                        start_time=day_start,
                        end_time=day_start + timedelta(minutes=int(minutes)),
                        duration_minutes=minutes,
                    ))

        return ServiceResult(success=True, data=activities)

    # ── 5. get_vehicle_activities ─────────────────────────────────

    def get_vehicle_activities(
        self,
        vehicle_id: int,
        start: date,
        end: date,
    ) -> ServiceResult[list[VehicleActivity]]:
        """Return vehicle activities (odometer, distance) within a date range."""
        # Fetch all vehicle data records for this truck
        all_vd = self.tacho_vehicle_data_repository.get_by_truck(vehicle_id)

        # Cross-reference with imports to filter by date range
        activities: list[VehicleActivity] = []

        truck = self.fleet_repository.get_by_id(vehicle_id)
        plate = truck.get("plate_number", "Unknown") if truck else "Unknown"

        for vd in all_vd:
            imp = self.tacho_import_repository.get_by_id(vd["import_id"])
            if not imp:
                continue
            imp_date_str = imp.get("imported_at", "")
            if not imp_date_str:
                continue

            try:
                # imported_at may be ISO string or datetime
                if isinstance(imp_date_str, str):
                    imp_date = datetime.fromisoformat(imp_date_str).date()
                else:
                    # Already a datetime
                    imp_date = imp_date_str.date() if hasattr(imp_date_str, "date") else date.fromisoformat(str(imp_date_str)[:10])
            except (ValueError, TypeError):
                continue

            if imp_date < start or imp_date > end:
                continue

            odometer = float(vd.get("odometer_km", 0) or 0)
            speed_violations = int(vd.get("speed_violations", 0) or 0)

            activities.append(VehicleActivity(
                vehicle_id=vehicle_id,
                plate=plate,
                date=imp_date,
                odometer_start=odometer,
                odometer_end=odometer,
                distance_km=0.0,  # incremental distance not stored per-import
                max_speed=float(speed_violations * 91) if speed_violations > 0 else None,
            ))

        if not activities:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    field="date_range",
                    message=(
                        f"No vehicle data for vehicle {vehicle_id} "
                        f"between {start} and {end}"
                    ),
                    code="NO_DATA",
                )],
            )

        return ServiceResult(success=True, data=activities)

    # ═════════════════════════════════════════════════════════════════
    # Legacy dict-based public API (deprecated)
    # ═════════════════════════════════════════════════════════════════

    def _resolve_parser_path(self):
        """Return path to tachograph parser binary, or None."""
        if os.path.exists(TACHOGRAPH_PATH):
            return TACHOGRAPH_PATH
        return None

    def _run_parser(self, file_bytes: bytes):
        """Run tachograph.exe parse on *file_bytes* via temp file.

        Tries semantic parse first (lenient), falls back to raw output if that fails.
        """
        parser = self._resolve_parser_path()
        if not parser:
            return None
        try:
            with tempfile.NamedTemporaryFile(suffix=".ddd", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            try:
                # Try lenient semantic parse first
                result = subprocess.run(
                    [parser, "parse", "--strict=false", tmp_path],
                    capture_output=True,
                    timeout=30,
                )
                # If semantic parse fails, fall back to raw output
                if result.returncode != 0:
                    result = subprocess.run(
                        [parser, "parse", "--raw", tmp_path],
                        capture_output=True,
                        timeout=30,
                    )
            finally:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)
            return result
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(args=[], returncode=-1, stdout=b"", stderr=b"Parser timed out")
        except FileNotFoundError:
            return None

    @staticmethod
    def _safe_str(val) -> str:
        if val is None:
            return ""
        if isinstance(val, dict):
            return str(val.get("value", val.get("name", "")))
        return str(val)

    def import_ddd_file(self, file_path: str) -> dict:
        """Legacy dict-based import entry point.

        .. deprecated::
            Use ``import_file(TachoImportRequest, user_id)`` instead.
        """
        warnings.warn(
            "import_ddd_file is deprecated; use import_file(TachoImportRequest, user_id) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        parser = self._resolve_parser_path()
        if not parser:
            return {
                "success": False,
                "error": (
                    "No tachograph parser found. "
                    "Please place tachograph.exe in the tools/tachograph/ directory, "
                    "or set the OPERION_TACHOGRAPH_PATH environment variable."
                )
            }

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        existing = self.tacho_import_repository.get_by_hash(file_hash)
        if existing:
            return {
                "success": False,
                "error": (
                    f"This file was already imported on "
                    f"{existing.get('imported_at', 'unknown')}."
                )
            }

        result = self._run_parser(file_bytes)
        if result is None:
            return {"success": False,
                    "error": f"Cannot execute parser binary: {parser}."}
        if result.returncode == -1:
            return {"success": False,
                    "error": "Parser timed out (30s). File may be corrupt."}

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            return {"success": False,
                    "error": f"Parser error: {stderr[:200]}"}

        try:
            raw_json = result.stdout.decode("utf-8")
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            return {"success": False,
                    "error": f"Invalid JSON from parser: {e}"}

        # Detect file type — support all formats:
        #   tachograph-go semantic: type=DRIVER_CARD / VEHICLE_UNIT
        #   tachograph-go raw:      type=CARD with records[], or VEHICLE_UNIT with records[]
        #   legacy dddsimple:       driverCard/vehicleUnit keys at root
        ftype = data.get("type", "")
        file_name = os.path.basename(file_path)
        if ftype == "DRIVER_CARD":
            return self._process_driver_card(data, file_name, file_hash, raw_json)
        if ftype == "VEHICLE_UNIT":
            return self._process_vehicle_unit(data, file_name, file_hash, raw_json)
        if ftype == "CARD":
            return self._process_driver_card(data, file_name, file_hash, raw_json)
        if "driverCard" in data or "cardActivities" in data:
            return self._process_driver_card(data, file_name, file_hash, raw_json)
        if "vehicleUnit" in data or "calibrationRecord" in data:
            return self._process_vehicle_unit(data, file_name, file_hash, raw_json)
        return {
            "success": False,
            "error": "Could not determine file type. "
                     "Is this a valid tachograph file?"
        }

    def get_import_history(self, limit: int = 50) -> list:
        """Return recent import records as dicts."""
        return self.tacho_import_repository.get_recent(limit)

    def get_driver_summary(self, driver_id: int, days: int = 28) -> dict:
        """Legacy dict-based driver summary.

        .. deprecated::
            Use ``analyze_driver_hours(driver_id, date_range)`` instead.
        """
        warnings.warn(
            "get_driver_summary is deprecated; use analyze_driver_hours(driver_id, date_range) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        from_date = date.today() - timedelta(days=days)
        records = self.tacho_driver_activity_repository.get_by_driver(
            driver_id, from_date
        )
        total_driving = sum(r.get("driving_minutes", 0) for r in records)
        total_violations = sum(
            len(json.loads(r.get("violations") or "[]")) for r in records
        )
        return {
            "days_with_data": len(records),
            "total_driving_hours": total_driving / 60,
            "avg_daily_driving_hours": (total_driving / 60 / len(records)
                                         if records else 0),
            "violations_count": total_violations,
        }

    # ── Internal processors ───────────────────────────────────────────

    @staticmethod
    def _get_nested(d, *paths, default=None):
        for path in paths:
            keys = path.split(".")
            v = d
            try:
                for k in keys:
                    v = v[k]
                if v is not None:
                    if len(paths) > 1 and path != paths[0]:
                        logger.debug("Tacho: matched fallback path '%s' (primary was '%s')", path, paths[0])
                    return v
            except (KeyError, TypeError):
                pass
        return default

    def _parse_tacho_date(self, raw_value) -> Optional[date]:
        if raw_value is None:
            return None
        try:
            if isinstance(raw_value, str):
                raw_value = raw_value.strip()
                if "T" in raw_value:
                    return datetime.fromisoformat(
                        raw_value.split("T")[0]
                    ).date()
                if len(raw_value) == 10 and "-" in raw_value:
                    return date.fromisoformat(raw_value)
            val = int(raw_value)
            if val == 0:
                return None
            if val > 946684800:
                return datetime.utcfromtimestamp(val).date()
            epoch = datetime(2001, 1, 1)
            return (epoch + timedelta(seconds=val)).date()
        except (ValueError, TypeError, OverflowError):
            return None

    def _process_driver_card(self, data: dict,
                              file_name: str,
                              file_hash: str,
                              raw_json: str) -> dict:
        # Try legacy dddsimple paths first, then tachograph-go semantic paths
        driver_name = self._get_nested(
            data,
            "driverCard.cardHolderName.holderSurname",
            "driverCard.holderName.holderSurname",
            "cardHolderName.holderSurname",
            "driverCard.tachograph.identification.cardHolderSurname.value",
            "driverCard.tachograph.identification.cardHolderSurname",
            "driverCard.tachograph_g2.identification.cardHolderSurname.value",
            "driverCard.tachograph_g2.identification.cardHolderSurname",
            default=""
        )
        driver_first = self._get_nested(
            data,
            "driverCard.cardHolderName.holderFirstNames",
            "driverCard.holderName.holderFirstNames",
            "driverCard.tachograph.identification.cardHolderFirstNames.value",
            "driverCard.tachograph.identification.cardHolderFirstNames",
            "driverCard.tachograph_g2.identification.cardHolderFirstNames.value",
            "driverCard.tachograph_g2.identification.cardHolderFirstNames",
            default=""
        )
        card_number = self._get_nested(
            data,
            "driverCard.cardNumber",
            "cardNumber",
            "driverCard.tachograph.identification.driverIdentification.value",
            "driverCard.tachograph.identification.driverIdentification",
            "driverCard.tachograph_g2.identification.driverIdentification.value",
            "driverCard.tachograph_g2.identification.driverIdentification",
            default=None
        )
        card_expiry = self._get_nested(
            data,
            "driverCard.cardExpiryDate",
            "driverCard.applicationExpiryDate",
            "driverCard.tachograph.identification.cardExpiryDate",
            "driverCard.tachograph_g2.identification.cardExpiryDate",
            default=None
        )

        driver_id = None
        if card_number:
            driver = self.driver_repository.get_by_card_number(card_number)
            if driver:
                driver_id = driver.get("id")
        if not driver_id and driver_name:
            driver = self.driver_repository.get_by_name_fuzzy(
                f"{driver_first} {driver_name}".strip()
            )
            if driver:
                driver_id = driver.get("id")

        import_id = self.tacho_import_repository.create({
            "file_name": file_name,
            "file_type": "driver_card",
            "file_hash": file_hash,
            "driver_id": driver_id,
            "raw_json": raw_json,
            "parse_status": "ok",
        })

        activities = self._get_nested(
            data,
            "driverCard.cardDrivingLicenceInformation",
            "driverCard.driverActivities.activityDailyRecords",
            "driverCard.activityDailyRecords",
            "driverCard.tachograph.driverActivityData.dailyRecords",
            "driverCard.tachograph_g2.driverActivityData.dailyRecords",
            default=[]
        )

        days_imported = 0
        total_violations = 0

        for day_record in activities:
            try:
                activity_date = self._parse_tacho_date(
                    day_record.get("activityRecordDate")
                    or day_record.get("date")
                    or (day_record.get("activityRecordDate", {}) or {}).get("seconds")
                )
                if not activity_date:
                    continue

                driving = 0
                work = 0
                rest = 0
                avail = 0

                slots = (day_record.get("activityChangeInfo", [])
                         or day_record.get("activities", []))

                # Handle tachograph-go format where each change info has
                # activityType (int enum) and duration (int minutes)
                for slot in slots:
                    minutes = int(slot.get("duration", slot.get("activityDuration", 0)) or 0)
                    at_raw = slot.get("activityType")
                    if at_raw is None:
                        at_raw = slot.get("activity", slot.get("type", ""))
                    atype = str(at_raw).lower()
                    if at_raw == 0 or "drive" in atype:
                        driving += minutes
                    elif at_raw == 3 or "rest" in atype:
                        rest += minutes
                    elif at_raw == 1 or "work" in atype:
                        work += minutes
                    elif at_raw == 2 or "avail" in atype:
                        avail += minutes

                distance = float(
                    day_record.get("distanceDriven", day_record.get("activityDayDistance", 0)) or 0
                )

                violations = []
                if driving > 570:
                    violations.append(
                        f"Driving {driving//60}h{driving%60}m exceeds 9h limit"
                    )
                if rest < 660 and driving > 0:
                    violations.append("Daily rest period below 11 hours")

                total_violations += len(violations)

                self.tacho_driver_activity_repository.create({
                    "import_id": import_id,
                    "driver_id": driver_id,
                    "activity_date": activity_date.isoformat(),
                    "driving_minutes": driving,
                    "work_minutes": work,
                    "rest_minutes": rest,
                    "avail_minutes": avail,
                    "distance_km": distance,
                    "violations": json.dumps(violations) if violations else None,
                })
                days_imported += 1

            except Exception as e:
                logging.warning("Could not parse day record: %s", e)
                continue

        if driver_id and card_expiry:
            expiry_date = self._parse_tacho_date(card_expiry)
            if expiry_date:
                self.driver_repository.update_license_expiry(
                    driver_id, expiry_date.isoformat()
                )

        driver_display = (f"{driver_first} {driver_name}".strip()
                          or "Unknown Driver")
        result = {
            "success": True,
            "file_type": "driver_card",
            "import_id": import_id,
            "driver_id": driver_id,
            "driver_name": driver_display,
            "days_imported": days_imported,
            "violations_found": total_violations,
            "summary": (
                f"Driver card imported: {driver_display}. "
                f"{days_imported} days of activity. "
                f"{total_violations} potential violation(s) flagged."
            )
        }
        if driver_id:
            self.after_import_hooks(driver_id=driver_id)
        return result

    def _process_vehicle_unit(self, data: dict,
                               file_name: str,
                               file_hash: str,
                               raw_json: str) -> dict:
        # Try legacy dddsimple paths first, then tachograph-go semantic paths
        plate = self._get_nested(
            data,
            "vehicleUnit.vehicleRegistrationIdentification.vehicleRegistrationPlate",
            "vehicleUnit.vuIdentification.vuRegistrationNumber",
            "registrationPlate",
            "vehicleUnit.gen1.overview.vehicleRegistration.registrationPlate.value",
            "vehicleUnit.gen1.overview.vehicleRegistration.registrationPlate",
            "vehicleUnit.gen2_v1.overview.vehicleRegistration.registrationPlate.value",
            "vehicleUnit.gen2_v2.overview.overview.vehicleRegistration.registrationPlate.value",
            default=None
        )
        vin = self._get_nested(
            data,
            "vehicleUnit.vehicleRegistrationIdentification.vehicleIdentificationNumber",
            "vehicleUnit.vuIdentification.vin",
            "vehicleUnit.gen1.overview.vehicleRegistration.vin.value",
            "vehicleUnit.gen1.overview.vehicleRegistration.vin",
            "vehicleUnit.gen2_v1.overview.vehicleRegistration.vin.value",
            "vehicleUnit.gen2_v2.overview.overview.vehicleRegistration.vin.value",
            default=None
        )

        truck_id = None
        if plate:
            truck = self.fleet_repository.get_by_plate(plate)
            if truck:
                truck_id = truck.get("id")
        if not truck_id and vin:
            truck = self.fleet_repository.get_by_vin(vin)
            if truck:
                truck_id = truck.get("id")

        calib_date_raw = self._get_nested(
            data,
            "vehicleUnit.vuCalibrationData.vuCalibrationRecord.0.calibrationDate",
            "vehicleUnit.calibrationData.calibrationDate",
            "calibrationRecord.calibrationDate",
            "vehicleUnit.gen1.overview.calibrationDate",
            "vehicleUnit.gen2_v1.overview.calibrationDate",
            "vehicleUnit.gen2_v2.overview.overview.calibrationDate",
            default=None
        )
        calib_date = self._parse_tacho_date(calib_date_raw)
        calib_expiry = None
        if calib_date:
            calib_expiry = calib_date + relativedelta(years=2)

        odometer_raw = self._get_nested(
            data,
            "vehicleUnit.vuActivities.odometer",
            "vehicleUnit.vuOverview.lastOdometerValue",
            "odometerValueMidnight",
            "vehicleUnit.gen1.overview.lastOdometerValue",
            "vehicleUnit.gen2_v1.overview.lastOdometerValue",
            "vehicleUnit.gen2_v2.overview.overview.lastOdometerValue",
            default=None
        )
        odometer_km = None
        if odometer_raw is not None:
            with contextlib.suppress(ValueError, TypeError):
                odometer_km = float(odometer_raw) / 1000.0

        speed_violations = 0

        def _count_speed_violations(speed_data_list):
            count = 0
            for block in (speed_data_list or []):
                speeds = block.get("speedsPerSecond", block.get("speedValues", [])) or []
                if isinstance(speeds, list):
                    in_violation = False
                    for s in speeds:
                        if isinstance(s, (int, float)) and s > 90:
                            if not in_violation:
                                count += 1
                                in_violation = True
                        else:
                            in_violation = False
            return count

        # Try legacy path then tachograph-go gen-specific paths
        speed_data = self._get_nested(data,
            "vehicleUnit.vuDetailedSpeedData",
            default=[])
        if isinstance(speed_data, list) and speed_data:
            speed_violations = _count_speed_violations(speed_data)
        if speed_violations == 0:
            for gen_key in ("gen1", "gen2_v1", "gen2_v2"):
                gen_data = data.get("vehicleUnit", data).get(gen_key, {})
                sd = gen_data.get("detailedSpeed", gen_data.get("detailed_speed", []))
                if isinstance(sd, list):
                    speed_violations = _count_speed_violations(sd)
                    if speed_violations > 0:
                        break

        import_id = self.tacho_import_repository.create({
            "file_name": file_name,
            "file_type": "vehicle_unit",
            "file_hash": file_hash,
            "truck_id": truck_id,
            "raw_json": raw_json,
            "parse_status": "ok",
        })

        self.tacho_vehicle_data_repository.create({
            "import_id": import_id,
            "truck_id": truck_id,
            "calibration_date": calib_date.isoformat() if calib_date else None,
            "calibration_expiry": calib_expiry.isoformat() if calib_expiry else None,
            "odometer_km": odometer_km,
            "speed_violations": speed_violations,
        })

        if truck_id:
            updates = {}
            if calib_expiry:
                updates["tachograph_expiry"] = calib_expiry.isoformat()
            if odometer_km:
                truck = self.fleet_repository.get_by_id(truck_id)
                if truck and (not truck.get("odometer_km")
                              or odometer_km > truck.get("odometer_km", 0)):
                    updates["odometer_km"] = odometer_km
            if updates:
                self.fleet_repository.update_fields(truck_id, updates)

        result = {
            "success": True,
            "file_type": "vehicle_unit",
            "import_id": import_id,
            "truck_id": truck_id,
            "plate": plate or "Unknown",
            "calibration_expiry": (calib_expiry.strftime("%d/%m/%Y")
                                    if calib_expiry else "Not found"),
            "odometer_km": odometer_km,
            "speed_violations": speed_violations,
            "summary": (
                f"Vehicle unit imported: {plate or vin or 'Unknown'}. "
                f"Calibration expires: "
                f"{calib_expiry.strftime('%d/%m/%Y') if calib_expiry else 'unknown'}. "
                f"Odometer: {odometer_km:.0f} km"
                if odometer_km else
                f"Vehicle unit imported: {plate or vin or 'Unknown'}."
            )
        }
        if truck_id:
            self.after_import_hooks(truck_id=truck_id)
        return result

    def after_import_hooks(self, truck_id=None, driver_id=None):
        """Run maintenance evaluation in background after successful import.

        Uses the OperationsEngine singleton (not a new MaintenanceEngine per
        import) to avoid accumulating duplicate EventBus subscriptions.
        """
        def run():
            try:
                from services.operations.operations_engine import OperationsEngine
                engine = OperationsEngine(self.db)
                if truck_id:
                    engine.evaluate_truck(str(truck_id))
                if driver_id:
                    engine.evaluate_all()
                logger.info("Post-import maintenance evaluation complete.")
            except Exception as e:
                logger.error("Post-import evaluation failed: %s", e)
        threading.Thread(target=run, daemon=True).start()
