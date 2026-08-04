"""MultiPlatformClient — simulates desktop and mobile API calls for cross-platform sync testing.

Provides two client perspectives — 'desktop' and 'mobile' — that share the same backend
but simulate different access patterns, offline behavior, and sync timing.
"""

from __future__ import annotations

from typing import Any
from services.trip_service import TripService
from services.invoicing.service import InvoiceService
from services.operations.event_bus import EventBus


class DesktopClient:
    """Simulates the desktop application (PySide6) using the service layer."""

    def __init__(self, trip_service: TripService, invoice_service: InvoiceService,
                 event_bus: EventBus, db) -> None:
        self.trip_service = trip_service
        self.invoice_service = invoice_service
        self.event_bus = event_bus
        self.db = db

    def create_trip(self, **kwargs) -> int:
        """Create a trip from the 'desktop' perspective."""
        from models.trip_models import TripCreate
        request = TripCreate(**kwargs)
        result = self.trip_service.create(request)
        return result.data.id

    def get_trip(self, trip_id: int) -> dict | None:
        return self.trip_service.get_by_id(trip_id)

    def transition_status(self, trip_id: int, new_status: str) -> bool:
        from services.operations.trip_status_engine import TripStatusEngine
        engine = TripStatusEngine(self.db, self.trip_service, self.event_bus)
        return engine.force_trip_status(trip_id, new_status)

    def create_invoice(self, **kwargs) -> int:
        from models.invoice_models import InvoiceCreate
        result = self.invoice_service.create(InvoiceCreate(**kwargs))
        return result.data.id


class MobileClient:
    """Simulates the mobile application (Flutter) — limited operations, offline-aware."""

    def __init__(self, trip_service: TripService, db) -> None:
        self.trip_service = trip_service
        self.db = db
        self._offline_queue: list[dict[str, Any]] = []

    def get_trip(self, trip_id: int) -> dict | None:
        return self.trip_service.get_by_id(trip_id)

    def update_status(self, trip_id: int, new_status: str, offline: bool = False) -> bool | None:
        """Update trip status. If offline, queue for later sync."""
        if offline:
            self._offline_queue.append({"action": "update_status", "trip_id": trip_id, "status": new_status})
            return None
        from services.operations.trip_status_engine import TripStatusEngine
        engine = TripStatusEngine(self.db, self.trip_service)
        return engine.force_trip_status(trip_id, new_status)

    def sync_queue(self) -> list[bool]:
        """Replay all queued offline actions."""
        results = []
        for item in self._offline_queue:
            if item["action"] == "update_status":
                from services.operations.trip_status_engine import TripStatusEngine
                engine = TripStatusEngine(self.db, self.trip_service)
                results.append(engine.force_trip_status(item["trip_id"], item["status"]))
        self._offline_queue.clear()
        return results

    def pending_actions(self) -> int:
        return len(self._offline_queue)
