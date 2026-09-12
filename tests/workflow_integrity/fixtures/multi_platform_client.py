"""MultiPlatformClient — simulates desktop, web and mobile API calls for cross-platform sync testing.

Provides three client perspectives — 'desktop', 'web' and 'mobile' — that share the same
backend but simulate different access patterns, offline behavior, and sync timing.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from services.trip_service import TripService
from services.invoicing.service import InvoiceService
from services.operations.event_bus import EventBus

__all__ = ["DesktopClient", "WebClient", "MobileClient"]

logger = logging.getLogger("workflow_integrity.multi_platform_client")


def _model_to_dict(obj: Any) -> dict[str, Any]:
    """Best-effort conversion of a result model (pydantic v1/v2) to a plain dict."""
    for attr in ("model_dump", "dict"):
        method = getattr(obj, attr, None)
        if callable(method):
            try:
                data = method()
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    if hasattr(obj, "__dict__"):
        return dict(vars(obj))
    return {"id": getattr(obj, "id", None)}


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
        # Only *legal* transitions are applied (VALID_TRANSITIONS table) — the
        # service layer has no way to force an arbitrary status onto a trip.
        # Invalid transitions return False instead of raising.
        try:
            return TripStatusEngine(self.db).transition(
                trip_id, new_status, trigger="desktop"
            )
        except Exception as exc:
            logger.warning(
                "desktop status transition for trip %s to %r rejected: %s",
                trip_id, new_status, exc,
            )
            return False

    def create_invoice(self, **kwargs) -> int:
        from models.invoice_models import InvoiceCreate
        result = self.invoice_service.create(InvoiceCreate(**kwargs))
        return result.data.id


class WebClient:
    """Simulates the read-only web portal (customer / partner view).

    Shares the same backend as desktop and mobile but only exposes the *read*
    paths — it can inspect trips and invoices and never mutates state.
    """

    def __init__(self, trip_service: TripService, invoice_service: InvoiceService,
                 db) -> None:
        self.trip_service = trip_service
        self.invoice_service = invoice_service
        self.db = db

    def get_trip(self, trip_id: int) -> dict | None:
        """Portal view of a trip (read-only)."""
        return self.trip_service.get_by_id(trip_id)

    def get_invoice(self, invoice_id: int) -> dict | None:
        """Portal view of an invoice (read-only). Returns None when not found."""
        result = self.invoice_service.get(invoice_id)
        if result is None or not result.success or result.data is None:
            return None
        return _model_to_dict(result.data)


class MobileClient:
    """Simulates the mobile application (Flutter) — limited operations, offline-aware."""

    def __init__(self, trip_service: TripService, db) -> None:
        self.trip_service = trip_service
        self.db = db
        self._offline_queue: list[dict[str, Any]] = []
        # Idempotency keys already applied during this sync session.
        # Replays carrying one of these keys are skipped (dedup on replay).
        self._replayed_keys: set[str] = set()

    def get_trip(self, trip_id: int) -> dict | None:
        return self.trip_service.get_by_id(trip_id)

    # ── Status application (shared by online updates and offline replay) ─

    def _apply_status_update(self, trip_id: int, new_status: str, *,
                             trigger: str = "mobile_sync") -> bool:
        """Apply a trip status change through the real status engine.

        The service layer exposes no way to *force* an arbitrary status onto
        a trip — ``TripStatusEngine(db).transition(...)`` applies a status only
        when it is a legal transition from the trip's current state (per the
        ``VALID_TRANSITIONS`` table), records history, and publishes a
        ``trip.status_changed`` event.  An invalid/unknown transition returns
        ``False`` instead of raising, so a queued offline replay can never
        abort the whole sync loop.
        """
        from services.operations.trip_status_engine import TripStatusEngine
        try:
            return TripStatusEngine(self.db).transition(
                trip_id, new_status, trigger=trigger
            )
        except Exception as exc:
            logger.warning(
                "status update for trip %s to %r rejected: %s",
                trip_id, new_status, exc,
            )
            return False

    # ── Offline queueing ──────────────────────────────────────────────────

    def _enqueue(self, action: str, *, idempotency_key: str | None = None,
                 **payload: Any) -> str:
        """Append one offline action. Every queued entry carries an idempotency key."""
        key = idempotency_key or uuid4().hex
        self._offline_queue.append({"action": action, "idempotency_key": key, **payload})
        return key

    def update_status(self, trip_id: int, new_status: str, offline: bool = False,
                      idempotency_key: str | None = None) -> bool | None:
        """Update trip status. If offline, queue for later sync.

        An explicit ``idempotency_key`` may be passed so a retried action
        (same logical intent) is replayed at most once per session.
        """
        if offline:
            self._enqueue(
                "update_status",
                idempotency_key=idempotency_key,
                trip_id=trip_id,
                status=new_status,
            )
            return None
        return self._apply_status_update(trip_id, new_status)

    def queue_document_upload(self, trip_id: int, title: str, category: str = "cmr",
                              file_name: str | None = None,
                              idempotency_key: str | None = None) -> str:
        """Queue a document upload (e.g. driver photo of a CMR) for the next sync.

        Returns the idempotency key under which the upload will be replayed.
        """
        return self._enqueue(
            "document_upload",
            idempotency_key=idempotency_key,
            trip_id=trip_id,
            title=title,
            category=category,
            file_name=file_name or title,
        )

    def queue_expense(self, trip_id: int, description: str, amount: float,
                      currency: str = "EUR",
                      idempotency_key: str | None = None) -> str:
        """Queue an ad-hoc expense (fuel receipt, parking, scale ticket) for the next sync.

        Returns the idempotency key under which the expense will be replayed.
        """
        return self._enqueue(
            "expense",
            idempotency_key=idempotency_key,
            trip_id=trip_id,
            description=description,
            amount=amount,
            currency=currency,
        )

    # ── Replay ───────────────────────────────────────────────────────────

    def sync_queue(self) -> list[dict[str, Any]]:
        """Replay all queued offline actions and return one result per action.

        Every element describes the outcome of a single queued action::

            {
                "action": "update_status" | "document_upload" | "expense",
                "idempotency_key": str,
                "applied": bool,          # True if executed now
                "result": bool | None,    # outcome of the applied action
            }

        Actions whose ``idempotency_key`` was already replayed during this
        session are skipped (dedup on replay) — they are never applied twice.
        """
        results: list[dict[str, Any]] = []
        pending, self._offline_queue = self._offline_queue, []
        for item in pending:
            action = item.get("action", "unknown")
            key = item.get("idempotency_key")
            if not key:
                key = uuid4().hex
                item["idempotency_key"] = key
            if key in self._replayed_keys:
                results.append({
                    "action": action,
                    "idempotency_key": key,
                    "applied": False,
                    "result": None,
                })
                continue
            result = self._replay_action(action, item)
            self._replayed_keys.add(key)
            results.append({
                "action": action,
                "idempotency_key": key,
                "applied": True,
                "result": result,
            })
        return results

    def _replay_action(self, action: str, item: dict[str, Any]) -> bool | None:
        """Execute a single queued action against the shared backend."""
        if action == "update_status":
            return self._apply_status_update(item["trip_id"], item["status"])
        if action == "document_upload":
            # Simulated: document metadata is handed to the backend for
            # fetch + OCR once connectivity is restored.
            return True
        if action == "expense":
            # Simulated: ad-hoc expense is recorded on the backend on reconnect.
            return True
        return None

    def pending_actions(self) -> int:
        return len(self._offline_queue)

    def replayed_keys(self) -> set[str]:
        """Idempotency keys already applied during this sync session."""
        return set(self._replayed_keys)
