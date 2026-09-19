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


# ── Trans.eu receiver ───────────────────────────────────────────────────

@router.post("/trans-eu/{company_id}")
async def receive_trans_eu_webhook(
    company_id: int,
    request: Request,
    secret: Optional[str] = None,
    db=Depends(get_db),
):
    """Receive a Trans.eu webhook event for a specific company.

    Trans.eu requires a dedicated callback URL per company::

        POST /api/v1/webhooks/trans-eu/{company_id}?secret={company_webhook_secret}

    The ``{company_id}`` path segment identifies the tenant.  The optional
    ``secret`` query parameter is validated against the stored webhook
    secret (``webhook.trans-eu.secret`` in the settings table) when one is
    configured.  Processing failures are recorded in the dead letter queue
    by :class:`WebhookIngestionService` — the endpoint always acknowledges
    with **200** so Trans.eu does not retry indefinitely.

    Trans.eu webhook format::

        {
            "id": "87795",
            "event_name": "freights.freight.update",
            "occurred_at": "2026-01-25T11:41:11+00:00",
            "data": {"freight_id": 87795, ...}
        }
    """
    # ── Validate URL secret ────────────────────────────────────────────
    stored_secret = _get_webhook_secret(db, "trans-eu")
    if stored_secret and secret != stored_secret:
        logger.warning(
            "Trans.eu webhook rejected: invalid secret for company %s", company_id
        )
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    # ── Parse JSON payload ─────────────────────────────────────────────
    raw_body = await request.body()
    try:
        payload: dict = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")

    event_name = payload.get("event_name", "")
    trans_eu_event_id = str(payload.get("id", ""))
    occurred_at = payload.get("occurred_at", "")

    if not trans_eu_event_id or not event_name:
        logger.info(
            "Trans.eu webhook skipped: missing event_id/event_name (company=%s)",
            company_id,
        )
        return {
            "received": True,
            "company_id": company_id,
            "status": "skipped",
            "reason": "missing event_id or event_name",
        }

    # ── Process via the ingestion pipeline ─────────────────────────────
    from services.trans_eu.webhook_ingestion import WebhookIngestionService

    service = WebhookIngestionService(db)
    result = await service.process_webhook(
        company_id=company_id,
        event_id=trans_eu_event_id,
        event_name=event_name,
        occurred_at=occurred_at,
        payload=payload,
    )

    logger.info(
        "Trans.eu webhook processed: company=%s event=%s status=%s",
        company_id, trans_eu_event_id, result.get("status"),
    )

    return {
        "received": True,
        "company_id": company_id,
        "event_id": trans_eu_event_id,
        "event_name": event_name,
        "status": result.get("status"),
        "category": result.get("category", ""),
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
    }

    if partner == "trans-eu":
        # Trans.eu webhooks have a dedicated company-scoped receiver
        # (POST /webhooks/trans-eu/{company_id}) — see receive_trans_eu_webhook.
        # The generic legacy route must NOT dispatch these; emit a clear
        # "moved" marker instead of publishing a garbage webhook.trans-eu.*
        # event on the bus.
        logger.warning(
            "Trans.eu webhook received on legacy generic route POST /webhooks/%s "
            "— use POST /api/v1/webhooks/trans-eu/{company_id} (event=%s id=%s)",
            partner, event_type, event_id,
        )
        return {
            "status": "moved",
            "details": (
                "Trans.eu webhooks moved to POST /api/v1/webhooks/trans-eu/{company_id}; "
                "the generic /webhooks/{partner} route no longer handles trans-eu"
            ),
        }

    handler = HANDLERS.get(partner)
    if handler:
        return handler(db, event_type, payload)

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
    """Legacy Trans.eu webhook handler — **moved**.

    Trans.eu webhooks are now processed by the dedicated company-scoped
    receiver :func:`receive_trans_eu_webhook`
    (``POST /api/v1/webhooks/trans-eu/{company_id}``).  ``_dispatch_webhook``
    returns a ``moved`` marker for the ``trans-eu`` partner so the generic
    ``POST /webhooks/{partner}`` route never dispatches these events.

    Kept as a thin marker so any stale direct callers get an explicit
    migration signal instead of silent garbage handling.
    """
    logger.warning(
        "Legacy _handle_trans_eu_webhook called (event_id=%s) — Trans.eu "
        "webhooks moved to POST /api/v1/webhooks/trans-eu/{company_id}",
        event_id,
    )
    return {
        "status": "moved",
        "details": (
            "Trans.eu webhooks moved to POST /api/v1/webhooks/trans-eu/{company_id}; "
            "the generic /webhooks/{partner} route no longer handles trans-eu"
        ),
    }


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
            logger.warning("Failed to resolve company_id from Trans.eu freight_id lookup", exc_info=True)
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
            logger.warning("Failed to resolve company_id from Trans.eu data freight_id lookup", exc_info=True)
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
