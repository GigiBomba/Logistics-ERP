"""Trans.eu webhook ingestion service.

Validates, stores, and routes incoming webhook events from Trans.eu.
Uses IP whitelisting + URL secret for verification (no HMAC).
Idempotent — duplicate events (by trans_eu_event_id) are skipped.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

TRANS_EU_CALLBACK_IP = "52.208.90.151"


class WebhookValidationError(Exception):
    """Webhook payload is invalid (wrong IP, bad secret, malformed JSON)."""


class WebhookAlreadyProcessed(Exception):
    """Event has already been processed (idempotency check)."""


class WebhookIngestionService:
    """Processes incoming Trans.eu webhook events.

    Usage::

        service = WebhookIngestionService(db)
        await service.process_webhook(
            company_id=1, event_id="87795",
            event_name="freights.freight.create",
            occurred_at="2026-01-25T11:41:11+00:00",
            payload={"id": "87795", "event_name": "...", "data": {...}},
        )
    """

    def __init__(self, db):
        self.db = db

    # ── Validation ────────────────────────────────────────────────────

    def validate_source_ip(self, client_ip: str) -> None:
        """Verify the request originates from Trans.eu's callback server."""
        if client_ip != TRANS_EU_CALLBACK_IP:
            raise WebhookValidationError(
                f"Invalid source IP: {client_ip}. Expected: {TRANS_EU_CALLBACK_IP}"
            )

    def validate_url_secret(self, expected_secret: str | None, actual_secret: str | None) -> None:
        """Verify the URL secret matches the company's configured secret."""
        if expected_secret is None:
            return  # secret not configured — skip check (test mode)
        if actual_secret != expected_secret:
            raise WebhookValidationError("URL secret mismatch")

    # ── Idempotency ───────────────────────────────────────────────────

    def is_duplicate(self, trans_eu_event_id: str) -> bool:
        """Check if this event has already been processed.

        Queries the trans_eu_webhook_events table for the event ID.
        """
        try:
            row = self.db.conn.execute(
                "SELECT status FROM trans_eu_webhook_events WHERE trans_eu_event_id = ?",
                (trans_eu_event_id,),
            ).fetchone()
            return row is not None
        except Exception:
            # Table may not exist in test/offline environments
            return False

    # ── Event Storage ─────────────────────────────────────────────────

    def store_event(
        self, company_id: int, trans_eu_event_id: str,
        event_name: str, occurred_at: str, payload: dict,
    ) -> str:
        """Persist raw webhook event to trans_eu_webhook_events.

        Returns the row ID.
        """
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.db.conn.execute(
            """INSERT INTO trans_eu_webhook_events
               (company_id, trans_eu_event_id, event_name, occurred_at,
                payload, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'received', ?)
               RETURNING id""",
            (company_id, trans_eu_event_id, event_name, occurred_at,
             json.dumps(payload, default=str), now),
        )
        self.db.conn.commit()
        row = cursor.fetchone()
        return row[0] if row else ""

    def mark_processed(self, event_id: str) -> None:
        """Mark event as successfully processed."""
        now = datetime.now(timezone.utc).isoformat()
        self.db.conn.execute(
            "UPDATE trans_eu_webhook_events SET status = 'processed', processed_at = ? WHERE id = ?",
            (now, event_id),
        )
        self.db.conn.commit()

    def mark_failed(self, event_id: str, error_message: str) -> None:
        """Mark event as failed."""
        self.db.conn.execute(
            "UPDATE trans_eu_webhook_events SET status = 'failed', error_message = ? WHERE id = ?",
            (str(error_message)[:500], event_id),
        )
        self.db.conn.commit()

    # ── Dead Letter Queue ────────────────────────────────────────────

    def store_to_dlq(
        self, company_id: int, trans_eu_event_id: str,
        event_name: str, payload: dict, error_message: str,
        error_type: str = "processing",
    ) -> None:
        """Store failed event in the dead letter queue for retry."""
        now = datetime.now(timezone.utc)
        next_retry = now  # retry immediately on first attempt
        self.db.conn.execute(
            """INSERT INTO trans_eu_webhook_events_failed
               (company_id, trans_eu_event_id, event_name, payload,
                error_message, error_type, attempt_count, next_retry_at,
                status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?, 'pending', ?)""",
            (company_id, trans_eu_event_id, event_name,
             json.dumps(payload, default=str), str(error_message)[:500],
             error_type, next_retry.isoformat(), now.isoformat()),
        )
        self.db.conn.commit()
        logger.info("Event %s stored in DLQ (type=%s)", trans_eu_event_id, error_type)

    # ── Routing ──────────────────────────────────────────────────────

    def route_event(self, event_name: str) -> str:
        """Determine the handler category from the event_name prefix.

        Returns one of: 'freight', 'order', 'transport', 'dock', 'unknown'.
        """
        if event_name.startswith("freights."):
            return "freight"
        if event_name.startswith("freight_orders."):
            return "order"
        if event_name.startswith("transports."):
            return "transport"
        if event_name.startswith("time_slot_management."):
            return "dock"
        return "unknown"

    # ── Full Pipeline ─────────────────────────────────────────────────

    async def process_webhook(
        self, company_id: int, event_id: str,
        event_name: str, occurred_at: str, payload: dict,
    ) -> dict:
        """Full webhook processing pipeline.

        1. Idempotency check
        2. Store raw event
        3. Route and handle
        4. On failure: store to DLQ

        Returns: {"status": "processed"|"skipped"|"failed", "event_id": str, ...}
        """
        # Idempotency
        if self.is_duplicate(event_id):
            logger.debug("Duplicate event %s — skipped", event_id)
            return {"status": "skipped", "event_id": event_id, "reason": "duplicate"}

        # Store
        try:
            row_id = self.store_event(
                company_id, event_id, event_name, occurred_at, payload,
            )
        except Exception as e:
            logger.exception("Failed to store webhook event %s", event_id)
            return {"status": "failed", "event_id": event_id, "error": str(e)}

        # Route
        category = self.route_event(event_name)
        if category == "unknown":
            self.mark_processed(row_id)
            return {"status": "skipped", "event_id": event_id, "reason": "unknown_event_type"}

        # Handle (delegates to sync service later)
        try:
            # In Phase 4.2, FreightSyncService handles the actual updates.
            # For now, mark as processed — sync service queries from
            # trans_eu_webhook_events table.
            self.mark_processed(row_id)
            logger.info(
                "Webhook event %s (%s) processed — routed to %s handler",
                event_id, event_name, category,
            )
            return {"status": "processed", "event_id": event_id, "category": category}
        except Exception as e:
            logger.exception("Failed to process webhook event %s", event_id)
            self.mark_failed(row_id, str(e))
            self.store_to_dlq(
                company_id, event_id, event_name, payload, str(e),
                error_type="processing",
            )
            return {"status": "failed", "event_id": event_id, "error": str(e)}
