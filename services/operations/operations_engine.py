import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from services.operations.alert_manager import AlertManager, AlertType, Severity, Alert
from services.operations.event_bus import EventBus, SYSTEM_STARTUP, TRUCK_ODOMETER_UPDATED, TRIP_STATUS_CHANGED, VALID_TRANSITIONS, DAILY_CHECK
from services.operations.maintenance_engine import MaintenanceEngine
from services.operations.notification_center import NotificationCenter
from services.operations.rules import Rules
from services.operations.undo_stack import UndoStack, UndoCommand
from repositories.fleet_repository import FleetRepository

logger = logging.getLogger("operations.operations_engine")


class OperationsEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db=None, prefs=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db=None, prefs=None):
        if self._initialized:
            if db is not None and self._db is None:
                self._db = db
            return
        self._initialized = True
        self._db = db
        self._prefs = prefs
        self._event_bus = EventBus()
        self._alert_mgr = AlertManager(db)
        self._rules = Rules()
        from services.trip_service import TripService
        self._trip_service = TripService(db) if db else None
        self._maintenance_engine = MaintenanceEngine(db) if db else None
        self._notification_center = NotificationCenter(db) if db else None
        self._undo_stack = UndoStack()
        self._running = False
        logger.info("OperationsEngine initialized")

    def undo_last(self) -> bool:
        cmd = self._undo_stack.undo()
        if not cmd:
            return False
        return self.force_trip_status(cmd.trip_id, cmd.old_status, skip_undo=True)

    def redo_last(self) -> bool:
        cmd = self._undo_stack.redo()
        if not cmd:
            return False
        return self.force_trip_status(cmd.trip_id, cmd.new_status, skip_undo=True)

    @property
    def undo_stack(self):
        return self._undo_stack

    def start(self):
        if self._running:
            return
        self._running = True
        self._event_bus.publish(SYSTEM_STARTUP, {})
        self._schedule_daily_check()
        if self._maintenance_engine:
            self._maintenance_engine.evaluate_all()
        if self._db:
            self._configure_smtp_from_db()
            self.migrate_existing_data()
        self._event_bus.subscribe(TRIP_STATUS_CHANGED, self._on_trip_status_for_docs)
        logger.info("OperationsEngine started")

    def _schedule_daily_check(self):
        if hasattr(self, "_daily_timer"):
            self._daily_timer.cancel()
        def _publish_and_reschedule():
            if not self._running:
                return
            self._event_bus.publish(DAILY_CHECK, {})
            if self._maintenance_engine:
                self._maintenance_engine.evaluate_all()
            self._daily_timer = threading.Timer(86400, _publish_and_reschedule)
            self._daily_timer.daemon = True
            self._daily_timer.start()
        self._daily_timer = threading.Timer(86400, _publish_and_reschedule)
        self._daily_timer.daemon = True
        self._daily_timer.start()

    def _configure_smtp_from_db(self):
        if not self._prefs:
            return
        try:
            cfg = self._prefs.get_smtp_config()
            if cfg.get("smtp_server") and cfg.get("smtp_user"):
                port = int(cfg.get("smtp_port", 587))
                self._notification_center.configure_smtp(
                    cfg["smtp_server"], port, cfg["smtp_user"], cfg.get("smtp_password", "")
                )
        except Exception as e:
            logger.debug("Could not configure SMTP from settings: %s", e)

    def stop(self):
        self._running = False
        if hasattr(self, "_daily_timer"):
            self._daily_timer.cancel()
        logger.info("OperationsEngine stopped")

    def get_active_alerts(self, limit: int = 200) -> List[Alert]:
        return self._alert_mgr.get_active_alerts(limit=limit)

    def get_alerts(
        self,
        alert_type: Optional[AlertType] = None,
        severity: Optional[Severity] = None,
        truck_id: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Alert]:
        return self._alert_mgr.get_alerts(
            alert_type=alert_type,
            severity=severity,
            truck_id=truck_id,
            resolved=resolved,
            limit=limit,
        )

    def resolve_alert(self, alert_id: str) -> Optional[Alert]:
        return self._alert_mgr.resolve_alert(alert_id)

    def get_active_count(self) -> int:
        return self._alert_mgr.get_active_count()

    def get_active_alert_count(self) -> int:
        return self.get_active_count()

    def evaluate_all(self) -> int:
        if self._maintenance_engine:
            return self._maintenance_engine.evaluate_all()
        return 0

    def evaluate_truck(self, truck_id: str) -> int:
        if self._maintenance_engine:
            return self._maintenance_engine.evaluate_truck(truck_id)
        return 0

    def get_valid_transitions(self, current_status: str) -> List[str]:
        """Return list of valid next statuses based on current status."""
        return VALID_TRANSITIONS.get(current_status, [])

    def force_trip_status(self, trip_id: int, new_status: str, skip_undo: bool = False) -> bool:
        """Force a trip to a specific status, updating odometer if completed."""
        if not self._trip_service:
            logger.error("force_trip_status: TripService not available")
            return False
        try:
            trip = self._trip_service.get_by_id(trip_id)
            if not trip:
                logger.error("force_trip_status: trip %d not found", trip_id)
                return False

            old_status = trip.get("status", "")
            if old_status == new_status:
                return True

            normalized_old = {
                "InTransit": "In Transit",
                "Active": "In Transit",
                "InProgress": "In Transit",
            }.get(old_status, old_status)

            normalized_new = {
                "InTransit": "In Transit",
                "Active": "In Transit",
                "InProgress": "In Transit",
            }.get(new_status, new_status)

            valid_targets = VALID_TRANSITIONS.get(normalized_old, [])
            if normalized_new not in valid_targets:
                logger.warning(
                    "force_trip_status: invalid transition %s -> %s for trip %d",
                    old_status, new_status, trip_id,
                )
                return False

            self._trip_service.update(trip_id, {"status": new_status})
            
            # If transitioning to Delivered/Completed, update truck odometer
            if new_status in ("Delivered", "Completed"):
                self._update_truck_odometer_on_completion(trip)
            
            # Publish status change event
            self._event_bus.publish(TRIP_STATUS_CHANGED, {
                "trip_id": trip_id,
                "old_status": old_status,
                "new_status": new_status,
            })
            
            logger.info("Trip %d status changed: %s -> %s", trip_id, old_status, new_status)

            if not skip_undo:
                prev_odo = None
                if new_status in ("Delivered", "Completed"):
                    truck_id = trip.get("truck_id")
                    if truck_id:
                        from repositories.fleet_repository import FleetRepository
                        fleet_repo = FleetRepository(self._db)
                        truck = fleet_repo.get_by_id(int(truck_id))
                        if truck:
                            prev_odo = truck.get("mileage")
                self._undo_stack.push(UndoCommand(
                    trip_id=trip_id,
                    old_status=old_status,
                    new_status=new_status,
                    previous_odometer=prev_odo,
                    truck_id=trip.get("truck_id"),
                ))

            return True
        except Exception as e:
            logger.error("force_trip_status failed for trip %d: %s", trip_id, e)
            return False

    def _update_truck_odometer_on_completion(self, trip: Dict[str, Any]) -> None:
        """Update truck odometer when trip is completed, preferring truck_id FK."""
        try:
            distance_km = trip.get("distance_km")
            truck_id = trip.get("truck_id")
            truck_number = trip.get("truck_number")

            if not distance_km or distance_km <= 0:
                logger.debug("Trip %s has no distance, skipping odometer update", trip.get("id"))
                return

            fleet_repo = FleetRepository(self._db)
            truck = None

            # Prefer FK lookup (canonical)
            if truck_id:
                truck = fleet_repo.get_by_id(int(truck_id))

            # Fall back to plate_number lookup for backward compatibility
            if not truck and truck_number:
                truck = fleet_repo.get_by_plate(truck_number)

            if not truck:
                logger.warning("Truck not found (id=%s, plate=%s), cannot update odometer",
                               truck_id, truck_number)
                return

            # Update odometer
            current_odometer = truck.get("mileage", 0) or 0
            new_odometer = current_odometer + distance_km

            fleet_repo.update(truck["id"], {"mileage": new_odometer})

            logger.info("Updated truck %s odometer: %.1f -> %.1f km (+%.1f km)",
                       truck.get("plate_number", truck["id"]), current_odometer, new_odometer, distance_km)

            # Re-evaluate maintenance thresholds
            if self._maintenance_engine:
                self._maintenance_engine.evaluate_truck(truck["id"])

            # Publish odometer update event
            self._event_bus.publish(TRUCK_ODOMETER_UPDATED, {
                "truck_id": truck["id"],
                "truck_number": truck.get("plate_number", ""),
                "previous_km": current_odometer,
                "added_km": distance_km,
                "new_total_km": new_odometer,
            })
        except Exception as e:
            logger.error("Failed to update truck odometer: %s", e)

    @property
    def alert_manager(self) -> AlertManager:
        return self._alert_mgr

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def notification_center(self) -> Optional[NotificationCenter]:
        return self._notification_center

    def migrate_existing_data(self) -> Dict[str, int]:
        results = {"trucks": 0, "trips": 0, "overdue_invoices": 0}
        if not self._db:
            return results
        logger.info("migrate_existing_data: starting backfill...")
        try:
            trucks = self._db.get_all_trucks(active_only=True)
            results["trucks"] = len(trucks)
            for t in trucks:
                self._maintenance_engine._evaluate_single(t)
            logger.info("migrate_existing_data: evaluated %d trucks", results["trucks"])
        except Exception as e:
            logger.error("migrate_existing_data truck eval failed: %s", e)

        try:
            trips = self._trip_service.get_all() if self._trip_service else []
            results["trips"] = len(trips)
            today = datetime.now()
            overdue_days = self._rules.get("unpaid_invoice_days", 30)
            for t in trips:
                trip_id, price, created_at, status = t["id"], t.get("total_price_eur", 0), t.get("created_at", ""), t.get("status", "")
                if status in ("Delivered", "Livrat", "Facturat", "Invoiced"):
                    try:
                        created = datetime.strptime(created_at[:10], "%Y-%m-%d")
                        age = (today - created).days
                        if age > overdue_days:
                            self._alert_mgr.create_alert(
                                AlertType.OVERDUE_INVOICE, Severity.CRITICAL,
                                f"Overdue invoice for trip #{trip_id}",
                                f"Trip delivered but unpaid for {age} days ({created_at[:10]}), amount: {price:.2f} EUR",
                                trip_id=str(trip_id),
                            )
                            results["overdue_invoices"] += 1
                    except Exception:
                        logger.debug("migrate_existing_data: failed to evaluate trip #%d", trip_id, exc_info=True)
            logger.info("migrate_existing_data: checked %d trips, %d overdue invoices",
                        results["trips"], results["overdue_invoices"])
        except Exception as e:
            logger.error("migrate_existing_data trip eval failed: %s", e)

        logger.info("migrate_existing_data complete: %s", results)
        return results

    def _on_trip_status_for_docs(self, ev: Dict[str, Any]) -> None:
        data = ev.get("data", {})
        new_status = data.get("new_status", "")
        trip_id = data.get("trip_id")

        transit_aliases = {"In Transit", "InTransit", "Active", "InProgress"}
        if new_status not in transit_aliases or not trip_id:
            return
        t = threading.Thread(target=self._generate_cmr, args=(trip_id,), daemon=True,
                             name=f"cmr-gen-{trip_id}")
        t.start()

    def _generate_cmr(self, trip_id: int) -> None:
        if not self._db:
            return
        try:
            from services.trip_service import TripService
            from services.invoicing.cmr_generator import CMRGenerator
            from services.document_service import DocumentService
            from services.operations.alert_manager import AlertType, Severity
            ts = TripService(self._db)
            trip = ts.get_by_id(trip_id)
            if not trip:
                return
            ds = DocumentService(self._db)
            existing = ds.get_documents_for_entity("trip", trip_id)
            for d in existing:
                if "cmr" in (d.get("tags") or "[]"):
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
                        driver = self._db.conn.execute(
                            "SELECT name, adr_certificate_expiry FROM drivers WHERE id = ?",
                            (driver_id,),
                        ).fetchone()
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
                    dr = self._db.conn.execute(
                        "SELECT * FROM drivers WHERE id = ?", (trip["driver_id"],)
                    ).fetchone()
                    if dr:
                        d = dict(dr)
                        ctx["driver_license"] = d.get("license_number", "")
                        ctx["driver_name"] = d.get("name", trip.get("driver_name", ""))
                except Exception:
                    logger.debug("CMR: driver lookup failed for driver_id=%s", trip.get("driver_id"))
            if trip.get("truck_id"):
                try:
                    tr = self._db.conn.execute(
                        "SELECT * FROM trucks WHERE id = ?", (trip["truck_id"],)
                    ).fetchone()
                    if tr:
                        t = dict(tr)
                        ctx["trailer_plate"] = t.get("trailer_plate", "")
                        ctx["cmr_insurance_number"] = t.get("cmr_insurance_number", "")
                except Exception:
                    logger.debug("CMR: truck lookup failed for truck_id=%s", trip.get("truck_id"))
            if trip.get("client_id"):
                try:
                    cl = self._db.conn.execute(
                        "SELECT * FROM clients WHERE id = ?", (trip["client_id"],)
                    ).fetchone()
                    if cl:
                        c = dict(cl)
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
