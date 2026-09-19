"""Trans.eu event sync service.

Processes webhook events and updates internal Operion models.
Each handler maps a Trans.eu event_name to local model mutations.
"""

from __future__ import annotations

import json
import logging
import uuid
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

        if event_name == "freight_orders.order.created":
            return self._handle_order_created(company_id, data)

        if event_name == "freight_orders.order.delivery_was_confirmed":
            return self._update_linked_trip(company_id, freight_id, "Delivered")

        if event_name == "freight_orders.order.order_was_cancelled":
            return self._update_linked_trip(company_id, freight_id, "Cancelled")

        if event_name == "freight_orders.order.transports_was_finished":
            return self._update_linked_trip(company_id, freight_id, "Delivered")

        return {"status": "skipped", "reason": f"unhandled_event:{event_name}"}

    def _handle_order_created(self, company_id: int, data: dict) -> dict:
        """Persist a Trans.eu ``freight_orders.order.created`` event locally.

        Maps the Trans.eu order payload onto the ``freight_orders`` table::

            trans_eu_order_id   ← data.id / data.order_id
            trans_eu_freight_id ← data.freight_id
            order_number        ← data.order_number / freight_reference_number
                                  / shipment_external_id
            price_amount        ← data.price.amount (or scalar data.price)
            price_currency      ← data.price.currency (default EUR)
            payment_type        ← data.payment_type
            execution_data      ← full event data serialized as JSON

        Dedupe relies on ``UNIQUE(company_id, trans_eu_order_id)``: an existing
        row is updated, otherwise a new row is created.  When the linked
        freight offer has an ``operion_trip_id`` the order is linked to that
        trip via :meth:`FreightOrderRepository.link_trip`.

        Errors are logged and returned as ``{"status": "failed", ...}`` — the
        ingestion pipeline keeps the always-200 webhook contract and routes
        any unhandled exception to the dead letter queue.
        """
        from repositories.trans_eu_domain_repository import FreightOrderRepository

        order_id = data.get("id") or data.get("order_id")
        freight_id = data.get("freight_id")

        if not order_id or freight_id is None:
            logger.warning(
                "Order sync skipped: missing order_id/freight_id (company=%s data=%s)",
                company_id, data,
            )
            return {"status": "skipped", "reason": "missing_order_id_or_freight_id"}

        try:
            freight_id = int(freight_id)
        except (ValueError, TypeError):
            logger.warning("Order sync skipped: invalid freight_id %r", freight_id)
            return {"status": "skipped", "reason": "invalid_freight_id"}

        order_number = (
            data.get("order_number")
            or data.get("freight_reference_number")
            or data.get("shipment_external_id")
            or ""
        )
        price_amount, price_currency = self._extract_price(data.get("price"))
        payment_type = data.get("payment_type") or ""
        execution_data = json.dumps(data, default=str)
        status = data.get("status") or "created"

        repo = FreightOrderRepository(self.db)
        try:
            existing = repo.get_by_trans_eu_order_id(company_id, str(order_id))
            if existing:
                repo.update_status(company_id, str(order_id), status)
                self.db.conn.execute(
                    """UPDATE freight_orders
                       SET trans_eu_freight_id = ?, order_number = ?,
                           price_amount = ?, price_currency = ?,
                           payment_type = ?, execution_data = ?, updated_at = ?
                       WHERE company_id = ? AND trans_eu_order_id = ?""",
                    (freight_id, order_number, price_amount, price_currency,
                     payment_type, execution_data,
                     datetime.now(timezone.utc).isoformat(),
                     company_id, str(order_id)),
                )
                self.db.conn.commit()
                action = "updated"
            else:
                repo.create({
                    "id": str(uuid.uuid4()),
                    "company_id": company_id,
                    "trans_eu_order_id": str(order_id),
                    "trans_eu_freight_id": freight_id,
                    "order_number": order_number,
                    "status": status,
                    "price_amount": price_amount,
                    "price_currency": price_currency,
                    "payment_type": payment_type,
                    "execution_data": execution_data,
                })
                action = "created"
        except Exception as e:
            logger.exception(
                "Order sync failed for order %s (company=%s)", order_id, company_id,
            )
            return {"status": "failed", "order_id": str(order_id), "error": str(e)}

        # Trip linking via trans_eu_freight_offers.operion_trip_id
        try:
            row = self.db.conn.execute(
                "SELECT operion_trip_id FROM trans_eu_freight_offers "
                "WHERE trans_eu_freight_id = ? AND company_id = ? "
                "AND operion_trip_id IS NOT NULL",
                (freight_id, company_id),
            ).fetchone()
            if row and row[0]:
                repo.link_trip(company_id, str(order_id), int(row[0]))
                # Trans.eu owns the dispatch assignment for order-linked trips
                # (TransEU_Architecture.md §10.1: "Trans.eu (for Trans.eu-managed
                # orders) | Depends on externally_managed flag").  Stamped via
                # raw SQL so the manual dispatch gate in TripService.update
                # starts rejecting Operion-side assignment edits.
                self.db.conn.execute(
                    "UPDATE trips SET externally_managed = 1, updated_at = ? "
                    "WHERE id = ? AND company_id = ?",
                    (datetime.now(timezone.utc).isoformat(), int(row[0]), company_id),
                )
                self.db.conn.commit()
                logger.info("Order %s linked to trip %s", order_id, row[0])
        except Exception as e:
            logger.warning(
                "Order sync: failed to link trip for order %s (company=%s): %s",
                order_id, company_id, e,
            )

        return {
            "status": "synced",
            "order_id": str(order_id),
            "freight_id": freight_id,
            "action": action,
        }

    @staticmethod
    def _extract_price(price: Any) -> tuple[Any, str]:
        """Normalize a Trans.eu price value into ``(amount, currency)``.

        Accepts a plain scalar (``price=560.20``) or a mapping with
        ``amount`` / ``currency`` keys (``{"amount": 560.20, "currency": "EUR"}``).
        """
        if isinstance(price, dict):
            amount = price.get("amount", price.get("value"))
            currency = price.get("currency") or "EUR"
        else:
            amount = price
            currency = "EUR"
        if amount is None:
            return None, currency
        try:
            return float(amount), currency
        except (TypeError, ValueError):
            return None, currency

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


class TransportSyncService:
    """Synchronizes Trans.eu transport events with local trip assignments.

    TransEU_Architecture.md §9.3::

        - When Trans.eu reports ``devices_set_changed`` (truck/driver
          assigned on Trans.eu Platform), sync to trip assignment
        ...
        **Sync flow:** Webhook → update trip truck_id/driver_id →
        dispatch board refreshes.

    The assignment is written via raw SQL (bypassing ``TripService.update``)
    because the trip is *externally managed* — Trans.eu owns the dispatch
    assignment (TransEU_Architecture.md §10.1).  ``externally_managed`` is
    stamped to 1 so the manual dispatch gate (``TripService.update``)
    rejects subsequent Operion-side assignment edits.
    """

    def __init__(self, db):
        self.db = db

    async def process_transport_event(
        self, company_id: int, event_name: str, occurred_at: str, data: dict,
    ) -> dict:
        """Route a Trans.eu transport event to the appropriate handler."""
        if event_name == "transports.transport.devices_set_changed":
            return self._handle_devices_set_changed(company_id, data)
        return {"status": "skipped", "reason": f"unhandled_event:{event_name}"}

    def _handle_devices_set_changed(self, company_id: int, data: dict) -> dict:
        """Sync the Trans.eu-assigned truck/driver onto the linked trip.

        Payload fields (TransEU_KnowledgeBase.md §8.5): ``carrier_id``,
        ``carrier_name``, ``executor_name``, ``executor_phone``,
        ``freight_id``, ``order_id``, ``truck_plate_number``,
        ``semitrailer_plate_number``, ``shipment_external_id``.

        The trip is resolved exactly like the freight/order handlers do:
        ``freight_id`` → ``trans_eu_freight_offers.operion_trip_id``,
        falling back to ``order_id`` → ``freight_orders.linked_trip_id``.
        """
        try:
            trip_id = self._resolve_trip_id(company_id, data)
            if trip_id is None:
                logger.info(
                    "Transport sync skipped: no linked trip for devices_set_changed "
                    "(company=%s data=%s)", company_id, data,
                )
                return {"status": "skipped", "reason": "no_linked_trip"}

            updates = self._build_trip_updates(company_id, data)
            updates["externally_managed"] = 1
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            self.db.conn.execute(
                f"UPDATE trips SET {set_clause} WHERE id = ? AND company_id = ?",
                tuple(updates.values()) + (trip_id, company_id),
            )
            self.db.conn.commit()
            logger.info(
                "Transport sync: trip %d assignment updated from Trans.eu (%s)",
                trip_id, sorted(updates),
            )
            return {"status": "synced", "trip_id": trip_id, "action": "assignment_synced"}
        except Exception as e:
            logger.exception(
                "Transport sync failed for devices_set_changed (company=%s)", company_id,
            )
            return {"status": "failed", "error": str(e)}

    def _resolve_trip_id(self, company_id: int, data: dict) -> int | None:
        """Resolve the local trip linked to a Trans.eu transport event.

        Mirrors ``OrderSyncService._update_linked_trip`` /
        ``FreightSyncService._sync_linked_trip``: the freight link
        (``operion_trip_id``) is tried first, then the order link
        (``freight_orders.linked_trip_id``).
        """
        freight_id = data.get("freight_id")
        if freight_id is not None:
            try:
                row = self.db.conn.execute(
                    "SELECT operion_trip_id FROM trans_eu_freight_offers "
                    "WHERE trans_eu_freight_id = ? AND company_id = ? "
                    "AND operion_trip_id IS NOT NULL",
                    (int(freight_id), company_id),
                ).fetchone()
                if row and row[0]:
                    return int(row[0])
            except (ValueError, TypeError):
                logger.debug("Transport sync: invalid freight_id %r", freight_id)

        order_id = data.get("order_id")
        if order_id is not None:
            try:
                row = self.db.conn.execute(
                    "SELECT linked_trip_id FROM freight_orders "
                    "WHERE trans_eu_order_id = ? AND company_id = ? "
                    "AND linked_trip_id IS NOT NULL",
                    (str(order_id), company_id),
                ).fetchone()
                if row and row[0]:
                    return int(row[0])
            except Exception:
                logger.debug("Transport sync: order_id lookup failed", exc_info=True)
        return None

    def _build_trip_updates(self, company_id: int, data: dict) -> dict:
        """Map the Trans.eu devices payload onto trips assignment columns.

        ``truck_plate_number`` → ``trips.truck_number`` (plate) plus the
        resolved ``trucks.id`` (plate match on ``trucks.plate_number``).
        ``executor_name`` → ``trips.driver_name`` plus the resolved
        ``drivers.id`` (name match).  ``semitrailer_plate_number`` /
        ``carrier_name`` have no trip column — they are intentionally
        dropped (transient monitoring fields, TransEU_KnowledgeBase §7.3).
        """
        updates: dict[str, Any] = {}

        plate = data.get("truck_plate_number")
        if plate:
            updates["truck_number"] = plate
            truck_row = self.db.conn.execute(
                "SELECT id FROM trucks WHERE plate_number = ? AND company_id = ?",
                (plate, company_id),
            ).fetchone()
            if truck_row:
                updates["truck_id"] = int(truck_row[0])

        executor = data.get("executor_name")
        if executor:
            updates["driver_name"] = executor
            driver_row = self.db.conn.execute(
                "SELECT id FROM drivers WHERE name = ? AND company_id = ? LIMIT 1",
                (executor, company_id),
            ).fetchone()
            if driver_row:
                updates["driver_id"] = int(driver_row[0])

        return updates


class DockSyncService:
    """Synchronizes Trans.eu dock-scheduler events with local dock tables.

    Event inventory (TransEU_KnowledgeBase.md §8.6)::

        time_slot_management.announcement.{created,updated,deleted}
        time_slot_management.time_window.{created,updated,deleted}
        time_slot_management.time_window.matching_result_with_freight_order_operations

    Created/updated events upsert the object via the existing dock
    repositories (``repositories/trans_eu_domain_repository.py`` —
    ``DockAnnouncementRepository`` / ``DockTimeWindowRepository`` /
    ``DockWarehouseRepository``); deletion events remove the row scoped to
    ``(company_id, trans_eu_*_id)``.  The upsert key is the natural
    Trans.eu id (``trans_eu_announcement_id`` / ``trans_eu_window_id``),
    so re-delivered events REPLACE the row instead of duplicating it.
    """

    def __init__(self, db):
        self.db = db

    async def process_dock_event(
        self, company_id: int, event_name: str, occurred_at: str, data: dict,
    ) -> dict:
        """Route a Trans.eu dock-scheduler event to the appropriate handler."""
        if event_name.startswith("time_slot_management.announcement."):
            return self._handle_announcement(company_id, event_name, data)
        if event_name.startswith("time_slot_management.time_window."):
            return self._handle_time_window(company_id, event_name, data)
        return {"status": "skipped", "reason": f"unhandled_event:{event_name}"}

    # ── Announcements (TransEU_KnowledgeBase.md §7.5) ────────────────

    def _handle_announcement(
        self, company_id: int, event_name: str, data: dict,
    ) -> dict:
        """Upsert/delete a dock announcement from its Trans.eu event.

        Announcement payload (§7.5): ``id``, ``reference_number``,
        ``status``, ``stage``, ``date_from``, ``date_to``,
        ``operation_type``, ``operation_time``, ``carrier{id,legal_name}``,
        ``shipper{id}``, ``driver``, ``vehicle``, ``ramp{id}``,
        ``warehouse{id,name}``, ``route``, ``notes``,
        ``external_reference_number``.
        """
        announcement_id = data.get("id") or data.get("announcement_id")
        if announcement_id is None:
            logger.info(
                "Dock sync skipped: no announcement id in %s (company=%s data=%s)",
                event_name, company_id, data,
            )
            return {"status": "skipped", "reason": "no_announcement_id"}

        if event_name.endswith(".deleted"):
            try:
                self.db.conn.execute(
                    "DELETE FROM dock_announcements "
                    "WHERE company_id = ? AND trans_eu_announcement_id = ?",
                    (company_id, int(announcement_id)),
                )
                self.db.conn.commit()
                return {"status": "synced", "announcement_id": int(announcement_id), "action": "deleted"}
            except Exception as e:
                return {"status": "failed", "error": str(e)}

        try:
            from repositories.trans_eu_domain_repository import (
                DockAnnouncementRepository,
                DockWarehouseRepository,
            )

            # Upsert the referenced warehouse first (announcement.warehouse).
            warehouse = data.get("warehouse") or {}
            if warehouse.get("id") is not None:
                DockWarehouseRepository(self.db).upsert_by_trans_eu_id(company_id, {
                    "trans_eu_warehouse_id": int(warehouse["id"]),
                    "name": warehouse.get("name") or "",
                })

            carrier = data.get("carrier") or {}
            shipper = data.get("shipper") or {}
            ramp = data.get("ramp") or {}

            DockAnnouncementRepository(self.db).upsert_by_trans_eu_id(company_id, {
                "trans_eu_announcement_id": int(announcement_id),
                "reference_number": data.get("reference_number") or "",
                "status": data.get("status") or "",
                "stage": data.get("stage") or "",
                "date_from": data.get("date_from"),
                "date_to": data.get("date_to"),
                "operation_type": data.get("operation_type") or "",
                "operation_time": data.get("operation_time") or "",
                "carrier_id": carrier.get("id"),
                "carrier_name": carrier.get("legal_name") or "",
                "shipper_id": shipper.get("id"),
                "driver": json.dumps(data.get("driver"), default=str) if data.get("driver") else None,
                "vehicle": json.dumps(data.get("vehicle"), default=str) if data.get("vehicle") else None,
                "ramp_id": ramp.get("id"),
                "warehouse_id": warehouse.get("id"),
                "route": json.dumps(data.get("route"), default=str) if data.get("route") else None,
                "notes": json.dumps(data.get("notes"), default=str) if data.get("notes") else None,
                "external_reference_number": data.get("external_reference_number") or "",
            })
            return {"status": "synced", "announcement_id": int(announcement_id), "action": "upserted"}
        except Exception as e:
            logger.exception(
                "Dock sync failed for announcement %s (company=%s)", announcement_id, company_id,
            )
            return {"status": "failed", "error": str(e)}

    # ── Time windows (TransEU_KnowledgeBase.md §7.6) ─────────────────

    def _handle_time_window(
        self, company_id: int, event_name: str, data: dict,
    ) -> dict:
        """Upsert/delete a dock time window from its Trans.eu event.

        Time-window payload (§7.6): ``valid_from``, ``valid_to``,
        ``start_time``, ``end_time``, ``range_type``, ``external_number``,
        ``carrier{id}``, ``purchase_order``, ``route{spots[].warehouse_id}``.

        NOTE (external-spec ambiguity): §7.6 does not document the window
        ``id`` field on the object; the webhook callback
        (``POST /ext/dock-scheduler-api/v1/warehouse/timeWindow``) is
        expected to carry it, so ``id`` / ``time_window_id`` / ``window_id``
        are all accepted.  ``warehouse_id`` is taken from the route's first
        spot (``route.spots[0].warehouse_id``) with a top-level
        ``warehouse_id`` override.
        """
        window_id = data.get("id") or data.get("time_window_id") or data.get("window_id")
        if window_id is None:
            logger.info(
                "Dock sync skipped: no time-window id in %s (company=%s data=%s)",
                event_name, company_id, data,
            )
            return {"status": "skipped", "reason": "no_time_window_id"}

        if event_name.endswith(".deleted"):
            try:
                self.db.conn.execute(
                    "DELETE FROM dock_time_windows "
                    "WHERE company_id = ? AND trans_eu_window_id = ?",
                    (company_id, int(window_id)),
                )
                self.db.conn.commit()
                return {"status": "synced", "window_id": int(window_id), "action": "deleted"}
            except Exception as e:
                return {"status": "failed", "error": str(e)}

        try:
            from repositories.trans_eu_domain_repository import DockTimeWindowRepository

            route = data.get("route") or {}
            spots = route.get("spots") or []
            warehouse_id = data.get("warehouse_id")
            if warehouse_id is None and spots:
                warehouse_id = (spots[0] or {}).get("warehouse_id")
            carrier = data.get("carrier") or {}

            DockTimeWindowRepository(self.db).upsert(company_id, {
                "trans_eu_window_id": int(window_id),
                "warehouse_id": warehouse_id,
                "valid_from": data.get("valid_from"),
                "valid_to": data.get("valid_to"),
                "start_time": data.get("start_time"),
                "end_time": data.get("end_time"),
                "range_type": data.get("range_type") or "",
                "external_number": data.get("external_number") or "",
                "carrier_id": carrier.get("id"),
                "purchase_order": json.dumps(data.get("purchase_order"), default=str) if data.get("purchase_order") else None,
                "route": json.dumps(route, default=str) if route else None,
            })
            return {"status": "synced", "window_id": int(window_id), "action": "upserted"}
        except Exception as e:
            logger.exception(
                "Dock sync failed for time window %s (company=%s)", window_id, company_id,
            )
            return {"status": "failed", "error": str(e)}
