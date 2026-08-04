"""Trans.eu event sync service.

Processes webhook events and updates internal Operion models.
Each handler maps a Trans.eu event_name to local model mutations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class FreightSyncService:
    """Synchronizes Trans.eu freight events with local FreightOffer records.

    Processes events from the trans_eu_webhook_events table and updates
    the corresponding trans_eu_freight_offers row. Also syncs linked
    Trips when status transitions affect them.
    """

    def __init__(self, db):
        self.db = db

    # ── Event Processing ──────────────────────────────────────────

    async def process_freight_event(
        self, company_id: int, event_name: str, occurred_at: str, data: dict,
        freight_id: int | None = None,
    ) -> dict:
        """Route a freight event to the appropriate handler.

        Args:
            company_id: Operion company ID
            event_name: Trans.eu event name (e.g., "freights.freight.create")
            occurred_at: ISO timestamp of the event
            data: Event data payload
            freight_id: Override for the freight ID (from event payload)

        Returns: {"status": "synced"|"skipped", "freight_id": int, ...}
        """
        fid = freight_id or data.get("freight_id") or data.get("id")
        if fid is None:
            logger.warning("No freight_id in event %s data: %s", event_name, data)
            return {"status": "skipped", "reason": "no_freight_id"}

        try:
            fid = int(fid)
        except (ValueError, TypeError):
            logger.warning("Invalid freight_id in event %s: %s", event_name, fid)
            return {"status": "skipped", "reason": "invalid_freight_id"}

        handler_map = {
            "freights.freight.create": self._handle_freight_create,
            "freights.freight.update": self._handle_freight_update,
            "freights.publication.activated": self._handle_publication_activated,
            "freights.publication.canceled": self._handle_publication_canceled,
            "freights.publication.finished": self._handle_publication_finished,
            "freights.publication.accepted": self._handle_publication_accepted,
            "freights.proposal_request.accepted": self._handle_offer_accepted,
            "freights.proposal_request.created": self._handle_offer_created,
            "freights.proposal_request.negotiated": self._handle_offer_negotiated,
            "freights.proposal_request.rejected": self._handle_offer_rejected,
            "freights.proposal_request.renounced": self._handle_offer_rejected,
            "freights.proposal_request.withdrawn": self._handle_offer_withdrawn,
        }

        handler = handler_map.get(event_name)
        if handler is None:
            logger.debug("Unhandled freight event: %s", event_name)
            return {"status": "skipped", "reason": f"unhandled_event:{event_name}"}

        return handler(company_id, fid, occurred_at, data)

    # ── Freight Lifecycle Handlers ─────────────────────────────────

    def _handle_freight_create(
        self, company_id: int, freight_id: int, occurred_at: str, data: dict,
    ) -> dict:
        """A freight was created on Trans.eu — no local action needed
        unless we want to track all freights proactively.
        """
        logger.debug("Freight %d created — not tracked locally", freight_id)
        return {"status": "skipped", "freight_id": freight_id, "reason": "not_tracked"}

    def _handle_freight_update(
        self, company_id: int, freight_id: int, occurred_at: str, data: dict,
    ) -> dict:
        """A freight was updated externally — mark as externally modified."""
        try:
            self.db.conn.execute(
                """UPDATE trans_eu_freight_offers
                   SET externally_modified_at = ?, updated_at = ?
                   WHERE trans_eu_freight_id = ? AND company_id = ?""",
                (occurred_at, datetime.now(timezone.utc).isoformat(),
                 freight_id, company_id),
            )
            self.db.conn.commit()
            logger.info("Freight %d marked as externally modified", freight_id)
            return {"status": "synced", "freight_id": freight_id, "action": "marked_externally_modified"}
        except Exception as e:
            logger.error("Failed to update freight %d: %s", freight_id, e)
            return {"status": "failed", "freight_id": freight_id, "error": str(e)}

    def _handle_publication_activated(
        self, company_id: int, freight_id: int, occurred_at: str, data: dict,
    ) -> dict:
        return self._update_local_freight(
            company_id, freight_id,
            {"publication_status": "active", "status": "published", "updated_at": datetime.now(timezone.utc).isoformat()},
        )

    def _handle_publication_canceled(
        self, company_id: int, freight_id: int, occurred_at: str, data: dict,
    ) -> dict:
        return self._update_local_freight(
            company_id, freight_id,
            {"publication_status": "finished", "status": "unsuccessful_publication", "updated_at": datetime.now(timezone.utc).isoformat()},
        )

    def _handle_publication_finished(
        self, company_id: int, freight_id: int, occurred_at: str, data: dict,
    ) -> dict:
        return self._update_local_freight(
            company_id, freight_id,
            {"publication_status": "finished", "updated_at": datetime.now(timezone.utc).isoformat()},
        )

    def _handle_publication_accepted(
        self, company_id: int, freight_id: int, occurred_at: str, data: dict,
    ) -> dict:
        """Freight was accepted — update local status and linked trip."""
        result = self._update_local_freight(
            company_id, freight_id,
            {"status": "accepted", "publication_status": "finished", "updated_at": datetime.now(timezone.utc).isoformat()},
        )
        # Update linked trip if exists
        self._sync_linked_trip(company_id, freight_id, "Planned")
        return result

    # ── Offer Handlers ─────────────────────────────────────────────

    def _handle_offer_accepted(
        self, company_id: int, freight_id: int, occurred_at: str, data: dict,
    ) -> dict:
        price = data.get("price", data.get("value"))
        self._update_local_freight(
            company_id, freight_id,
            {
                "status": "accepted",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"status": "synced", "freight_id": freight_id, "action": "offer_accepted"}

    def _handle_offer_created(
        self, company_id: int, freight_id: int, occurred_at: str, data: dict,
    ) -> dict:
        return {"status": "synced", "freight_id": freight_id, "action": "offer_tracked"}

    def _handle_offer_negotiated(
        self, company_id: int, freight_id: int, occurred_at: str, data: dict,
    ) -> dict:
        return {"status": "synced", "freight_id": freight_id, "action": "negotiation_updated"}

    def _handle_offer_rejected(
        self, company_id: int, freight_id: int, occurred_at: str, data: dict,
    ) -> dict:
        return {"status": "synced", "freight_id": freight_id, "action": "offer_rejected"}

    def _handle_offer_withdrawn(
        self, company_id: int, freight_id: int, occurred_at: str, data: dict,
    ) -> dict:
        return {"status": "synced", "freight_id": freight_id, "action": "offer_withdrawn"}

    # ── Helpers ────────────────────────────────────────────────────

    def _update_local_freight(
        self, company_id: int, freight_id: int, updates: dict,
    ) -> dict:
        """Update a local FreightOffer record."""
        try:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [freight_id, company_id]
            self.db.conn.execute(
                f"UPDATE trans_eu_freight_offers SET {set_clause} "
                f"WHERE trans_eu_freight_id = ? AND company_id = ?",
                values,
            )
            self.db.conn.commit()
            rows = self.db.conn.execute(
                "SELECT changes()",
            ).fetchone()
            if rows and rows[0] == 0:
                logger.debug("Freight %d not found in local DB — skipping update", freight_id)
                return {"status": "skipped", "freight_id": freight_id, "reason": "not_found_locally"}
            return {"status": "synced", "freight_id": freight_id, "action": "updated"}
        except Exception as e:
            logger.error("Failed to update local freight %d: %s", freight_id, e)
            return {"status": "failed", "freight_id": freight_id, "error": str(e)}

    def _sync_linked_trip(
        self, company_id: int, freight_id: int, new_status: str,
    ) -> None:
        """Update the linked Operion trip status when freight status changes."""
        try:
            row = self.db.conn.execute(
                "SELECT operion_trip_id FROM trans_eu_freight_offers "
                "WHERE trans_eu_freight_id = ? AND company_id = ? AND operion_trip_id IS NOT NULL",
                (freight_id, company_id),
            ).fetchone()
            if row:
                trip_id = row[0]
                self.db.conn.execute(
                    "UPDATE trips SET status = ? WHERE id = ? AND company_id = ?",
                    (new_status, trip_id, company_id),
                )
                self.db.conn.commit()
                logger.info("Synced trip %d status to '%s' from freight %d", trip_id, new_status, freight_id)
        except Exception as e:
            logger.error("Failed to sync trip for freight %d: %s", freight_id, e)


class OrderSyncService:
    """Synchronizes Trans.eu order events with local FreightOrder records."""

    def __init__(self, db):
        self.db = db

    async def process_order_event(
        self, company_id: int, event_name: str, occurred_at: str, data: dict,
    ) -> dict:
        """Process a freight_orders.* webhook event."""
        freight_id = data.get("freight_id")
        status = data.get("status")

        if event_name == "freight_orders.order.created":
            logger.info("Order created for freight %s", freight_id)
            return {"status": "synced", "action": "order_created"}

        if event_name == "freight_orders.order.delivery_was_confirmed":
            return self._update_linked_trip(company_id, freight_id, "Delivered")

        if event_name == "freight_orders.order.order_was_cancelled":
            return self._update_linked_trip(company_id, freight_id, "Cancelled")

        if event_name == "freight_orders.order.transports_was_finished":
            return self._update_linked_trip(company_id, freight_id, "Delivered")

        return {"status": "skipped", "reason": f"unhandled_event:{event_name}"}

    def _update_linked_trip(
        self, company_id: int, freight_id: int | None, new_status: str,
    ) -> dict:
        if freight_id is None:
            return {"status": "skipped", "reason": "no_freight_id"}
        try:
            row = self.db.conn.execute(
                "SELECT operion_trip_id FROM trans_eu_freight_offers "
                "WHERE trans_eu_freight_id = ? AND company_id = ?",
                (int(freight_id), company_id),
            ).fetchone()
            if row and row[0]:
                self.db.conn.execute(
                    "UPDATE trips SET status = ? WHERE id = ? AND company_id = ?",
                    (new_status, row[0], company_id),
                )
                self.db.conn.commit()
                logger.info("Order sync: trip %d → %s", row[0], new_status)
                return {"status": "synced", "trip_id": row[0], "new_status": new_status}
            return {"status": "skipped", "reason": "no_linked_trip"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
