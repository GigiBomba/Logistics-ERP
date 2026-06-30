"""Tachograph service — imports and parses .DDD files via dddsimple or tachograph CLI."""
import contextlib
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
from datetime import date, datetime, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta

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

# ── Event types used by TachoService ────────────────────────────────
class TruckUpdatedEvent:
    def __init__(self, truck_id):
        self.truck_id = truck_id


class TachoService:
    """Import, parse, and store tachograph .DDD files."""

    def __init__(self, db):
        self.db = db
        self.tacho_import_repository = TachoImportRepository(db)
        self.tacho_driver_activity_repository = TachoDriverActivityRepository(db)
        self.tacho_vehicle_data_repository = TachoVehicleDataRepository(db)
        self.fleet_repository = FleetRepository(db)
        self.driver_repository = DriverRepository(db)
        self.event_bus = EventBus()

    # ── Public API ────────────────────────────────────────────────────

    def _resolve_parser_path(self):
        """Return path to tachograph parser binary, or None."""
        if os.path.exists(TACHOGRAPH_PATH):
            return TACHOGRAPH_PATH
        return None

    def _run_parser(self, file_bytes: bytes):
        """Run tachograph.exe parse --raw on *file_bytes* via temp file."""
        parser = self._resolve_parser_path()
        if not parser:
            return None
        try:
            with tempfile.NamedTemporaryFile(suffix=".ddd", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            try:
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

    def import_ddd_file(self, file_path: str) -> dict:
        """Main entry point. Accepts any .DDD file path."""
        parser = self._resolve_parser_path()
        if not parser:
            return {
                "success": False,
                "error": (
                    "No tachograph parser found. "
                    "Please place dddsimple.exe or tachograph.exe in the tools/tachograph/ directory, "
                    "or set the OPERION_DDDSIMPLE_PATH / OPERION_TACHOGRAPH_PATH environment variable."
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

        file_type = "unknown"
        if "driverCard" in data or "cardActivities" in data:
            file_type = "driver_card"
        elif "vehicleUnit" in data or "calibrationRecord" in data:
            file_type = "vehicle_unit"

        file_name = os.path.basename(file_path)
        if file_type == "driver_card":
            return self._process_driver_card(
                data, file_name, file_hash, raw_json
            )
        elif file_type == "vehicle_unit":
            return self._process_vehicle_unit(
                data, file_name, file_hash, raw_json
            )
        else:
            return {
                "success": False,
                "error": "Could not determine file type. "
                         "Is this a valid tachograph file?"
            }

    def get_import_history(self, limit: int = 50) -> list:
        return self.tacho_import_repository.get_recent(limit)

    def get_driver_summary(self, driver_id: int, days: int = 28) -> dict:
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
        driver_name = self._get_nested(
            data,
            "driverCard.cardHolderName.holderSurname",
            "driverCard.holderName.holderSurname",
            "cardHolderName.holderSurname",
            default=""
        )
        driver_first = self._get_nested(
            data,
            "driverCard.cardHolderName.holderFirstNames",
            "driverCard.holderName.holderFirstNames",
            default=""
        )
        card_number = self._get_nested(
            data,
            "driverCard.cardNumber",
            "cardNumber",
            default=None
        )
        card_expiry = self._get_nested(
            data,
            "driverCard.cardExpiryDate",
            "driverCard.applicationExpiryDate",
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
            default=[]
        )
        if not activities:
            activities = (data.get("driverCard", {})
                          .get("driverActivities", {})
                          .get("activityDailyRecords", []))

        days_imported = 0
        total_violations = 0

        for day_record in activities:
            try:
                activity_date = self._parse_tacho_date(
                    day_record.get("activityRecordDate")
                    or day_record.get("date")
                )
                if not activity_date:
                    continue

                driving = 0
                work = 0
                rest = 0
                avail = 0
                distance = 0

                slots = (day_record.get("activityChangeInfo", [])
                         or day_record.get("activities", []))
                for slot in slots:
                    minutes = int(slot.get("duration", 0) or 0)
                    activity_type_raw = (slot.get("activityType")
                                         or slot.get("activity", ""))
                    atype = str(activity_type_raw).lower()
                    if activity_type_raw == 0 or "drive" in atype:
                        driving += minutes
                    elif activity_type_raw == 3 or "rest" in atype:
                        rest += minutes
                    elif activity_type_raw == 1 or "work" in atype:
                        work += minutes
                    elif activity_type_raw == 2 or "avail" in atype:
                        avail += minutes

                distance = float(
                    day_record.get("distanceDriven", 0) or 0
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
        plate = self._get_nested(
            data,
            "vehicleUnit.vehicleRegistrationIdentification.vehicleRegistrationPlate",
            "vehicleUnit.vuIdentification.vuRegistrationNumber",
            "registrationPlate",
            default=None
        )
        vin = self._get_nested(
            data,
            "vehicleUnit.vehicleRegistrationIdentification.vehicleIdentificationNumber",
            "vehicleUnit.vuIdentification.vin",
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
            default=None
        )
        odometer_km = None
        if odometer_raw is not None:
            with contextlib.suppress(ValueError, TypeError):
                odometer_km = float(odometer_raw) / 1000.0

        speed_violations = 0
        speed_data = self._get_nested(
            data,
            "vehicleUnit.vuDetailedSpeedData",
            default=[]
        )
        if isinstance(speed_data, list):
            for block in speed_data:
                speeds = block.get("speedsPerSecond", []) or []
                if isinstance(speeds, list):
                    in_violation = False
                    for s in speeds:
                        if isinstance(s, (int, float)) and s > 90:
                            if not in_violation:
                                speed_violations += 1
                                in_violation = True
                        else:
                            in_violation = False

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
        """Run maintenance evaluation in background after successful import."""
        def run():
            try:
                from services.operations.maintenance_engine import MaintenanceEngine
                engine = MaintenanceEngine(self.db)
                if truck_id:
                    engine.evaluate_truck(int(truck_id))
                if driver_id:
                    engine.evaluate_driver_hours()
                logger.info("Post-import maintenance evaluation complete.")
            except Exception as e:
                logger.error("Post-import evaluation failed: %s", e)
        threading.Thread(target=run, daemon=True).start()
