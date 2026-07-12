"""Truck and driver availability checks for dispatch."""

from __future__ import annotations

import logging
from typing import Any

from services.dispatch_service.models import DriverAvailability, TruckAvailability

logger = logging.getLogger(__name__)


class AvailabilityChecker:
    """Checks truck and driver availability for dispatch assignments."""

    def __init__(self, fleet_repo, driver_repo, conflict_service, tacho_repo=None):
        self._fleet_repo = fleet_repo
        self._driver_repo = driver_repo
        self._conflict_service = conflict_service
        self._tacho_repo = tacho_repo

    def check_truck(self, truck: dict, trip_data: dict) -> TruckAvailability:
        """
        Check a truck's availability for a specific trip.

        Checks: conflicts, insurance expiry, inspection expiry, maintenance due, 'In Service' status.
        """
        from datetime import date

        blocks: list[str] = []
        conflicts: list[dict] = []

        # 1. Status check: trucks "In Service" are unavailable
        status = (truck.get("status") or "").lower()
        if status == "in service":
            blocks.append("Truck is in service/repair")

        # 2. Insurance expiry check
        insurance = truck.get("insurance_expiry") or truck.get("insurance_valid_until")
        if insurance:
            try:
                insurance_date = self._parse_date(insurance)
                if insurance_date and insurance_date < date.today():
                    blocks.append("Insurance expired")
            except (ValueError, TypeError):
                pass

        # 3. Inspection expiry check
        inspection = truck.get("inspection_expiry") or truck.get("itp_expiry")
        if inspection:
            try:
                inspection_date = self._parse_date(inspection)
                if inspection_date and inspection_date < date.today():
                    blocks.append("Inspection (ITP) expired")
            except (ValueError, TypeError):
                pass

        # 4. Maintenance due check
        maintenance = truck.get("next_maintenance_date") or truck.get("maintenance_due")
        if maintenance:
            try:
                maint_date = self._parse_date(maintenance)
                if maint_date and maint_date < date.today():
                    blocks.append("Maintenance overdue")
            except (ValueError, TypeError):
                pass

        # 5. Conflict check
        try:
            conflicts = self._conflict_service.check_conflicts(trip_data) or []
            if conflicts:
                blocks.append(f"Conflict: {len(conflicts)} overlapping trips")
        except Exception:
            logger.debug("Conflict check failed for truck %s", truck.get("id"), exc_info=True)

        available = len(blocks) == 0
        status_text = "; ".join(blocks) if blocks else "Available"

        return TruckAvailability(
            available=available,
            blocks=blocks,
            conflicts=conflicts,
            status_text=status_text,
        )

    def check_driver(self, driver: dict, trip_data: dict) -> DriverAvailability:
        """
        Check a driver's availability for a specific trip.

        Checks: conflicts, license expiry, medical expiry, tacho weekly hours.
        """
        from datetime import date

        blocks: list[str] = []
        conflicts: list[dict] = []
        weekly_hours = 0.0
        violations = 0

        # 1. License expiry
        license_expiry = driver.get("license_expiry") or driver.get("driving_license_expiry")
        if license_expiry:
            try:
                lic_date = self._parse_date(license_expiry)
                if lic_date and lic_date < date.today():
                    blocks.append("Driving license expired")
            except (ValueError, TypeError):
                pass

        # 2. Medical certificate expiry
        medical = driver.get("medical_cert_expiry") or driver.get("medical_expiry")
        if medical:
            try:
                med_date = self._parse_date(medical)
                if med_date and med_date < date.today():
                    blocks.append("Medical certificate expired")
            except (ValueError, TypeError):
                pass

        # 3. Tacho weekly hours (if tacho_repo available)
        driver_id = driver.get("id")
        if self._tacho_repo and driver_id:
            try:
                activities = self._tacho_repo.get_by_driver(driver_id)
                if activities:
                    # Sum hours for current week
                    from datetime import datetime, timedelta

                    now = datetime.now()
                    week_start = now - timedelta(days=now.weekday())
                    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

                    for activity in activities:
                        act_time = activity.get("start_time") or activity.get("timestamp")
                        if act_time:
                            try:
                                act_dt = self._parse_datetime(act_time)
                                if act_dt and act_dt >= week_start:
                                    hours = float(activity.get("duration_hours", 0) or 0)
                                    weekly_hours += hours
                            except (ValueError, TypeError):
                                pass

                    # EU limit: 56 hours per week
                    if weekly_hours > 56:
                        blocks.append(f"Hours exceeded ({weekly_hours:.0f}/56/week)")

                    violations = sum(1 for a in activities if a.get("violation"))
                    if violations > 3:
                        blocks.append(f"Excessive violations ({violations})")
            except Exception:
                logger.debug("Tacho check failed for driver %s", driver_id, exc_info=True)

        # 4. Status check
        status = (driver.get("status") or "").lower()
        if status == "inactive":
            blocks.append("Driver is inactive")

        # 5. Conflict check
        try:
            conflicts = self._conflict_service.check_conflicts(trip_data) or []
            if conflicts:
                blocks.append(f"Conflict: {len(conflicts)} overlapping trips")
        except Exception:
            logger.debug("Conflict check failed for driver %s", driver.get("id"), exc_info=True)

        available = len(blocks) == 0
        status_text = "; ".join(blocks) if blocks else "Available"

        return DriverAvailability(
            available=available,
            blocks=blocks,
            conflicts=conflicts,
            weekly_hours=weekly_hours,
            violations=violations,
            status_text=status_text,
        )

    def _parse_date(self, value: Any):
        """Parse a date string or date object."""
        from datetime import date, datetime

        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
                try:
                    return datetime.strptime(value.strip()[:10], fmt).date()
                except ValueError:
                    continue
        return None

    def _parse_datetime(self, value: Any):
        """Parse a datetime string or object."""
        from datetime import datetime

        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        return None
