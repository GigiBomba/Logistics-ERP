"""Webhook receiver for external partner integrations.

Partners such as TIMOCOM, Wialon, Frotcom push events (shipment status,
document availability, GPS telemetry) to Operion via HTTP POST webhooks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.dependencies import get_db
from backend.dependencies_security import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Signature verification ───────────────────────────────────────────────

def verify_webhook_signature(request: Request, secret: str) -> bool:
    """Verify HMAC-SHA256 webhook signature.

    Expects header::

        X-Webhook-Signature: sha256=<hex-digest>

    Returns ``True`` when the computed digest matches the provided header.
    """
    signature_header = request.headers.get("X-Webhook-Signature", "")
    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("Webhook: missing or invalid signature header")
        return False

    expected_sig = signature_header[7:]  # Remove "sha256=" prefix

    # Raw body must have been preserved by WebhookBodyMiddleware.
    body: bytes = getattr(request.state, "webhook_raw_body", b"")
    if not body:
        logger.warning("Webhook: no raw body available for signature verification")
        return False

    computed_sig = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_sig, expected_sig)


# ── Event persistence ────────────────────────────────────────────────────

def store_webhook_event(
    db,
    partner: str,
    event_type: str,
    payload: dict,
    signature_valid: bool,
    processing_status: str = "received",
) -> int:
    """Insert an incoming webhook event into ``webhook_events``.

    Returns the new row id, or ``0`` on failure.
    """
    try:
        payload_json = json.dumps(payload, default=str)
        cursor = db.execute(
            """INSERT INTO webhook_events
               (partner, event_type, payload, signature_valid,
                processing_status, received_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                partner,
                event_type,
                payload_json,
                int(signature_valid),
                processing_status,
                datetime.now().isoformat(),
            ),
        )
        db.commit()
        return cursor.lastrowid or 0
    except Exception as exc:
        logger.error("Failed to store webhook event: %s", exc)
        return 0


def _update_webhook_status(db, event_id: int, status: str) -> None:
    """Update the processing status of a stored webhook event."""
    try:
        db.execute(
            "UPDATE webhook_events SET processing_status = ?, processed_at = ? WHERE id = ?",
            (status, datetime.now().isoformat(), event_id),
        )
        db.commit()
    except Exception as exc:
        logger.warning("Failed to update webhook event %d status: %s", event_id, exc)


def _get_webhook_secret(db, partner: str) -> str:
    """Look up the webhook signing secret for *partner* from the settings table.

    The secret is stored as ``webhook.<partner>.secret`` in the global
    settings (company_id IS NULL).
    """
    try:
        from backend.repositories.settings_repository import SettingsRepository

        repo = SettingsRepository(db)
        return repo.get_setting_value(f"webhook.{partner}.secret") or ""
    except Exception as exc:
        logger.debug("Could not load webhook secret for %s: %s", partner, exc)
        return ""


# ── Main receiver ────────────────────────────────────────────────────────

@router.post("/{partner}")
async def receive_webhook(partner: str, request: Request, db=Depends(get_db)):
    """Receive a webhook payload from *partner*.

    The route accepts any partner identifier (``timocom``, ``wialon``,
    ``frotcom``, …).  When a signing secret is configured for the partner
    the payload signature is verified; requests with invalid signatures
    receive a **403** and the event is recorded with
    ``processing_status='signature_failed'``.

    Returns a JSON summary including the assigned ``event_id`` and the
    dispatch result.
    """
    # ── Read and preserve raw body ────────────────────────────────────
    raw_body = await request.body()
    request.state.webhook_raw_body = raw_body

    # ── Parse JSON payload ────────────────────────────────────────────
    try:
        payload: dict = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")

    # ── Extract event type (partners use different key names) ─────────
    event_type: str = (
        payload.get("event")
        or payload.get("type")
        or payload.get("event_type")
        or "unknown"
    )

    # ── Signature verification ────────────────────────────────────────
    partner_secret = _get_webhook_secret(db, partner)
    signature_valid = True

    if partner_secret:
        signature_valid = verify_webhook_signature(request, partner_secret)
        if not signature_valid:
            store_webhook_event(
                db, partner, event_type, payload, False, "signature_failed"
            )
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    # ── Persist event ─────────────────────────────────────────────────
    event_id = store_webhook_event(db, partner, event_type, payload, signature_valid)

    # ── Dispatch to handler ───────────────────────────────────────────
    handler_result = await _dispatch_webhook(db, partner, event_type, payload, event_id)

    # ── Update event status ───────────────────────────────────────────
    _update_webhook_status(db, event_id, handler_result.get("status", "processed"))

    logger.info(
        "Webhook processed: partner=%s event=%s id=%d status=%s",
        partner,
        event_type,
        event_id,
        handler_result.get("status"),
    )

    return {
        "received": True,
        "event_id": event_id,
        "partner": partner,
        "event_type": event_type,
        "status": handler_result.get("status", "processed"),
        "details": handler_result.get("details", ""),
    }


# ── Dispatch ─────────────────────────────────────────────────────────────

async def _dispatch_webhook(
    db, partner: str, event_type: str, payload: dict, event_id: int = 0
) -> dict:
    """Route the webhook event to the appropriate partner-specific handler.

    Falls back to publishing a ``webhook.<partner>.<event_type>`` event
    on the internal :class:`EventBus`.
    """
    HANDLERS: dict[str, Callable] = {
        "timocom": _handle_timocom_webhook,
        "trans-eu": _handle_trans_eu_webhook,
    }

    handler = HANDLERS.get(partner)
    if handler:
        if partner == "timocom":
            return handler(db, event_type, payload)
        # trans-eu handler is async and requires different arguments
        return await handler(payload=payload, db=db, event_id=event_id)

    # Generic fallback — publish to the internal event bus
    return _publish_event_bus_event(db, f"webhook.{partner}.{event_type}", payload)


def _handle_timocom_webhook(db, event_type: str, payload: dict) -> dict:
    """Handle TIMOCOM-specific webhook events.

    Known TIMOCOM event types
        * ``shipment.created``     — New shipment available
        * ``shipment.updated``     — Shipment status changed
        * ``shipment.cancelled``   — Shipment was cancelled
        * ``offer.accepted``       — Our freight offer was accepted
        * ``offer.rejected``       -- Our freight offer was rejected
        * ``document.available``   — Document (CMR, invoice) ready
    """
    # Feature flag guard — TIMOCOM integration must be enabled per company
    from backend.services.feature_flags_service import FeatureFlagService

    company_id = payload.get("company_id", 0)
    ff = FeatureFlagService(db)
    if not ff.is_enabled("timocom_integration", company_id=company_id):
        logger.info(
            "TIMOCOM webhook skipped: integration disabled for company %s",
            company_id,
        )
        return {
            "status": "disabled",
            "details": "TIMOCOM integration is not enabled for this company",
        }

    handled_types = {
        "shipment.created",
        "shipment.updated",
        "shipment.cancelled",
        "offer.accepted",
        "offer.rejected",
        "document.available",
    }

    if event_type not in handled_types:
        logger.info("Unhandled TIMOCOM event type: %s", event_type)
        return {"status": "skipped", "details": f"Unknown event type: {event_type}"}

    return _publish_event_bus_event(db, f"timocom.{event_type}", payload)


async def _handle_trans_eu_webhook(payload: dict, db, event_id: int) -> dict:
    """Handle a Trans.eu webhook event.

    Trans.eu webhook format:
    {
        "id": "87795",
        "event_name": "freights.proposal_request.accepted",
        "occurred_at": "2026-01-25T11:41:11+00:00",
        "data": {"price": 560.20}
    }

    Trans.eu doesn't include company_id in the webhook payload.
    We look up the company from the freight_id/order_id in the
    event data by querying our local FreightOffer table.
    """
    from services.trans_eu.webhook_ingestion import WebhookIngestionService

    event_name = payload.get("event_name", "")
    trans_eu_event_id = str(payload.get("id", ""))
    occurred_at = payload.get("occurred_at", "")
    data = payload.get("data", {})

    if not trans_eu_event_id or not event_name:
        return {"status": "skipped", "reason": "missing event_id or event_name"}

    # Extract company_id from the event data
    # Trans.eu doesn't send company_id — derive it from freight_id lookups
    company_id = _extract_company_from_trans_eu_event(payload, db)
    if company_id is None:
        # Try to find from the freight_id or order_id in event data
        freight_id = payload.get("id")  # "id" is freight_id for freight events
        if freight_id:
            try:
                row = db.conn.execute(
                    "SELECT company_id FROM trans_eu_freight_offers WHERE trans_eu_freight_id = ?",
                    (int(freight_id),),
                ).fetchone()
                if row:
                    company_id = row[0]
            except Exception:
                pass

    if company_id is None:
        logger.warning("Cannot determine company_id for Trans.eu event %s", trans_eu_event_id)
        return {"status": "skipped", "reason": "unknown_company"}

    service = WebhookIngestionService(db)
    return await service.process_webhook(
        company_id=company_id,
        event_id=trans_eu_event_id,
        event_name=event_name,
        occurred_at=occurred_at,
        payload=payload,
    )


def _extract_company_from_trans_eu_event(payload: dict, db) -> int | None:
    """Try to extract company_id from a Trans.eu webhook event.

    Looks up freight_id, order_id, or announcement_id in our
    local tracking tables (trans_eu_freight_offers, freight_orders, etc.)
    """
    # Try freight_id (field "id" in freight events)
    freight_id = payload.get("id")
    if freight_id:
        try:
            row = db.conn.execute(
                "SELECT company_id FROM trans_eu_freight_offers WHERE trans_eu_freight_id = ?",
                (int(freight_id),),
            ).fetchone()
            if row:
                return row[0]
        except Exception:
            pass

    # Try from data section (some events embed freight_id there)
    data = payload.get("data", {})
    data_freight_id = data.get("freight_id") or data.get("id")
    if data_freight_id:
        try:
            row = db.conn.execute(
                "SELECT company_id FROM trans_eu_freight_offers WHERE trans_eu_freight_id = ?",
                (int(data_freight_id),),
            ).fetchone()
            if row:
                return row[0]
        except Exception:
            pass

    return None


def _publish_event_bus_event(db, event_name: str, payload: dict) -> dict:
    """Publish *event_name* on the internal :class:`EventBus`."""
    try:
        from services.operations.event_bus import EventBus

        bus = EventBus.get_instance(db)
        bus.publish(event_name, payload)
        logger.info("EventBus event published: %s", event_name)
        return {"status": "dispatched", "details": f"Event {event_name} queued"}
    except Exception as exc:
        logger.error("EventBus publish failed for %s: %s", event_name, exc)
        return {"status": "error", "details": str(exc)}


# ── Admin: event history ─────────────────────────────────────────────────

@router.get("/events")
async def list_webhook_events(
    partner: Optional[str] = None,
    limit: int = 50,
    db=Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_admin),
):
    """Return the most recent webhook events (admin only).

    Optionally filter by *partner*. Results are scoped to the admin's
    company_id for multi-tenant isolation.
    """
    company_id = current_user.get("company_id", 0)
    try:
        if partner:
            rows = db.execute(
                "SELECT * FROM webhook_events WHERE partner = ?"
                " AND webhook_events.company_id = ?"
                " ORDER BY received_at DESC LIMIT ?",
                (partner, company_id, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM webhook_events"
                " WHERE webhook_events.company_id = ?"
                " ORDER BY received_at DESC LIMIT ?",
                (company_id, limit),
            ).fetchall()

        return {"events": [dict(r) for r in rows], "total": len(rows)}
    except Exception as exc:
        logger.error("Failed to list webhook events: %s", exc)
        return {"events": [], "error": str(exc)}
