"""Webhook receiver for external partner integrations.

Partners such as TIMOCOM, Wialon, Frotcom push events (shipment status,
document availability, GPS telemetry) to Operion via HTTP POST webhooks.
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

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
        cursor = db.conn.execute(
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
        db.conn.commit()
        return cursor.lastrowid or 0
    except Exception as exc:
        logger.error("Failed to store webhook event: %s", exc)
        return 0


def _update_webhook_status(db, event_id: int, status: str) -> None:
    """Update the processing status of a stored webhook event."""
    try:
        db.conn.execute(
            "UPDATE webhook_events SET processing_status = ?, processed_at = ? WHERE id = ?",
            (status, datetime.now().isoformat(), event_id),
        )
        db.conn.commit()
    except Exception as exc:
        logger.warning("Failed to update webhook event %d status: %s", event_id, exc)


def _get_webhook_secret(db, partner: str) -> str:
    """Look up the webhook signing secret for *partner* from the settings table.

    The secret is stored as ``webhook.<partner>.secret`` in the global
    settings (company_id IS NULL).
    """
    try:
        from repositories.settings_repository import SettingsRepository

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
    handler_result = _dispatch_webhook(db, partner, event_type, payload)

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

def _dispatch_webhook(db, partner: str, event_type: str, payload: dict) -> dict:
    """Route the webhook event to the appropriate partner-specific handler.

    Falls back to publishing a ``webhook.<partner>.<event_type>`` event
    on the internal :class:`EventBus`.
    """
    if partner == "timocom":
        return _handle_timocom_webhook(db, event_type, payload)

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
    from services.feature_flags import FeatureFlagService

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
            rows = db.conn.execute(
                "SELECT * FROM webhook_events WHERE partner = ?"
                " AND webhook_events.company_id = ?"
                " ORDER BY received_at DESC LIMIT ?",
                (partner, company_id, limit),
            ).fetchall()
        else:
            rows = db.conn.execute(
                "SELECT * FROM webhook_events"
                " WHERE webhook_events.company_id = ?"
                " ORDER BY received_at DESC LIMIT ?",
                (company_id, limit),
            ).fetchall()

        return {"events": [dict(r) for r in rows], "total": len(rows)}
    except Exception as exc:
        logger.error("Failed to list webhook events: %s", exc)
        return {"events": [], "error": str(exc)}
