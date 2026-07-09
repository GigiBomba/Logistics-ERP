"""Auto-CMR generator — generates CMR documents when a trip enters 'In Transit' status.

Extracted from OperationsEngine to reduce its responsibilities.
Triggered via EventBus subscription to TRIP_STATUS_CHANGED.
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Any

from repositories.client_repository import ClientRepository
from repositories.driver_repository import DriverRepository
from repositories.fleet_repository import FleetRepository

logger = logging.getLogger("operations.cmr_auto_generator")


class AutoCMRGenerator:
    """Generates 4 CMR copies per trip when status transitions to 'In Transit'.

    Uses a per-trip-id lock to prevent duplicate generation when rapid status-change
    events arrive before the first generation finishes.
    """

    def __init__(self, db, prefs, alert_mgr):
        self._db = db
        self._prefs = prefs
        self._alert_mgr = alert_mgr
        self._generation_locks: dict[int, threading.Lock] = {}
        self._gen_lock_guard = threading.Lock()

    def _get_trip_lock(self, trip_id: int) -> threading.Lock:
        """Return a per-trip Lock, creating one if needed (thread-safe)."""
        with self._gen_lock_guard:
            if trip_id not in self._generation_locks:
                self._generation_locks[trip_id] = threading.Lock()
            return self._generation_locks[trip_id]

    def on_trip_in_transit(self, ev: dict[str, Any]) -> None:
        """EventBus subscriber — spawns background CMR generation thread."""
        data = ev.get("data", {})
        new_status = data.get("new_status", "")
        trip_id = data.get("trip_id")

        transit_aliases = {"In Transit", "InTransit", "Active", "InProgress"}
        if new_status not in transit_aliases or not trip_id:
            return
        t = threading.Thread(target=self.generate, args=(trip_id,), daemon=True,
                             name=f"cmr-gen-{trip_id}")
        t.start()

    def generate(self, trip_id: int) -> None:
        """Generate 4 CMR copies for a trip.

        Protected by a per-trip-id Lock so that two rapid status-change events
        do not both attempt generation for the same trip concurrently.
        """
        if not self._db:
            return
        lock = self._get_trip_lock(trip_id)
        if not lock.acquire(blocking=False):
            logger.info("Auto-CMR generation already in progress for trip %d — skipping duplicate", trip_id)
            return
        try:
            from services.invoicing.cmr_generator import CMRGenerator
            from services.operations.alert_manager import AlertType, Severity
            from services.trip_service import TripService

            ts = TripService(self._db)
            trip = ts.get_by_id(trip_id)
            if not trip:
                return
            from services.document_service import DocumentService
            ds = DocumentService(self._db)
            existing = ds.get_documents_for_entity("trip", trip_id)
            for d in existing:
                tags_raw = d.get("tags") or []
                if isinstance(tags_raw, str):
                    try:
                        tags_list = json.loads(tags_raw)
                    except (json.JSONDecodeError, TypeError):
                        tags_list = []
                elif isinstance(tags_raw, (list, tuple)):
                    tags_list = list(tags_raw)
                else:
                    tags_list = []
                if any("cmr" in str(t).lower() for t in tags_list):
                    return

            if not trip.get("cargo_description") or not trip.get("gross_weight_kg"):
                self._alert_mgr.create_alert(
                    AlertType.POLICY_VIOLATION, Severity.WARNING,
                    f"CMR blocked for trip #{trip_id}",
                    "Cargo description and gross weight are required for CMR. "
                    "Generate CMR manually via the Generators workspace.",
                    trip_id=str(trip_id),
                )
                logger.warning("Auto-CMR skipped for trip %d: missing cargo data", trip_id)
                return

            if trip.get("adr_info_json"):
                driver_id = trip.get("driver_id")
                if driver_id:
                    try:
                        driver = DriverRepository(self._db).get_by_id_with_adr(driver_id)
                        if driver and driver["adr_certificate_expiry"]:
                            expiry = datetime.strptime(driver["adr_certificate_expiry"], "%Y-%m-%d")
                            if expiry < datetime.now():
                                self._alert_mgr.create_alert(
                                    AlertType.COMPLIANCE_RISK, Severity.CRITICAL,
                                    f"ADR certificate expired for driver {driver['name']}",
                                    f"Trip #{trip_id} requires ADR transport but driver"
                                    f" ADR certificate expired {driver['adr_certificate_expiry']}.",
                                    trip_id=str(trip_id),
                                )
                                logger.warning(
                                    "Auto-CMR skipped for trip %d: expired ADR certificate", trip_id)
                                return
                    except Exception as e:
                        logger.debug("ADR cert check skipped: %s", e)

            output_dir = os.path.join("data", "documents", "trips", str(trip_id))
            os.makedirs(output_dir, exist_ok=True)

            gen = CMRGenerator(db=self._db, prefs=self._prefs)
            ctx = dict(trip)
            ctx["trip_id"] = trip_id
            ctx["truck_plate"] = trip.get("truck_number", "")
            if trip.get("driver_id"):
                try:
                    d = DriverRepository(self._db).get_by_id(trip["driver_id"])
                    if d:
                        ctx["driver_license"] = d.get("license_number", "")
                        ctx["driver_name"] = d.get("name", trip.get("driver_name", ""))
                except Exception:
                    logger.debug("CMR: driver lookup failed for driver_id=%s", trip.get("driver_id"))
            if trip.get("truck_id"):
                try:
                    t = FleetRepository(self._db).get_by_id(trip["truck_id"])
                    if t:
                        ctx["trailer_plate"] = t.get("trailer_plate", "")
                        ctx["cmr_insurance_number"] = t.get("cmr_insurance_number", "")
                except Exception:
                    logger.debug("CMR: truck lookup failed for truck_id=%s", trip.get("truck_id"))
            if trip.get("client_id"):
                try:
                    c = ClientRepository(self._db).get_by_id(trip["client_id"])
                    if c:
                        ctx["consignee_vat"] = c.get("vat_number", "")
                        ctx["consignee_eori"] = c.get("eori_number", "")
                except Exception:
                    logger.debug("CMR: client lookup failed for client_id=%s", trip.get("client_id"))

            copies = gen.generate_all_copies(ctx, output_dir)
            for suffix, path in copies.items():
                ds.register_existing(
                    path,
                    title=f"CMR #{ctx.get('cmr_number', '')} - {suffix.upper()} COPY",
                    category="trips", entity_type="trip",
                    entity_id=trip_id,
                    tags=["cmr", suffix.lower(), "auto-generated"],
                )
            logger.info("Auto-generated 4 CMR copies for trip %d: %s", trip_id, output_dir)
        except Exception as e:
            logger.error("Auto-CMR generation failed for trip %d: %s", trip_id, e)
        finally:
            lock.release()
