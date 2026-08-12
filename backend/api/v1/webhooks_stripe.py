"""Stripe webhook receiver — signature-verified + idempotent billing events.

POST /webhooks/stripe

Security model
--------------
* Signature verification via ``stripe.Webhook.construct_event`` using the raw
  request body (preserved by ``WebhookBodyMiddleware`` under
  ``request.state.webhook_raw_body``) and the ``Stripe-Signature`` header.
* If ``OPERION_STRIPE_WEBHOOK_SECRET`` is NOT configured the endpoint returns
  **501 Not Implemented** — it never processes an unverified payload.
* Signature failure → **400** with ``integration/webhook-signature-invalid``.

Idempotency (blueprint §18b.3)
------------------------------
Stripe retries any non-2xx response and may legitimately send the same event
twice. Every processed event is persisted to ``webhook_events``
(partner='stripe') and, before handling, we check-then-skip events whose id
was already recorded — a double-delivered event is never applied twice.

Handled event types
-------------------
* ``checkout.session.completed``   — activate the subscription row.
* ``invoice.paid``                 — create a ``billing_invoices`` row.
* ``invoice.payment_failed``       — mark subscription ``past_due``.
* ``customer.subscription.deleted``— mark subscription ``canceled``.

Companies are mapped from the event object's ``customer`` id via
``subscriptions.stripe_customer_id``. Events for unknown customers are
acknowledged (200) with ``status=skipped`` so Stripe stops retrying.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.config import BackendSettings
from backend.dependencies import get_db
from backend.errors import ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/stripe", tags=["webhooks", "stripe"])

PARTNER_NAME = "stripe"
DEFAULT_PERIOD_DAYS = 30


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _iso_ts(value: Any) -> Optional[str]:
    """Coerce a Stripe epoch-seconds timestamp (or ISO string) to ISO."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(int(value)).isoformat()
    return str(value)


# ── webhook_events persistence (mirrors backend/api/v1/webhooks.py) ─────

def _store_event(db, event: dict, company_id: Optional[int], status: str = "processing") -> int:
    """Persist the raw Stripe event into ``webhook_events``. Returns row id or 0.

    The upstream Stripe event id is stored in the dedicated ``event_id``
    column (migration v6) so idempotency checks are an exact indexed lookup.
    """
    try:
        payload_json = json.dumps(event, default=str)
        cursor = db.conn.execute(
            """INSERT INTO webhook_events
               (partner, event_type, payload, event_id, signature_valid,
                processing_status, received_at, company_id)
               VALUES (?, ?, ?, ?, 1, ?, ?, ?)""",
            (
                PARTNER_NAME,
                str(event.get("type", "unknown")),
                payload_json,
                str(event.get("id", "")) or None,
                status,
                _now_iso(),
                company_id,
            ),
        )
        db.conn.commit()
        return cursor.lastrowid or 0
    except Exception as exc:
        logger.error("Failed to store Stripe webhook event: %s", exc)
        return 0


def _update_status(db, event_id: int, status: str) -> None:
    try:
        db.conn.execute(
            "UPDATE webhook_events SET processing_status = ?, processed_at = ? WHERE id = ?",
            (status, _now_iso(), event_id),
        )
        db.conn.commit()
    except Exception as exc:
        logger.warning("Failed to update Stripe webhook event %d status: %s", event_id, exc)


def _already_processed(db, event_id: str) -> bool:
    """Return True when a Stripe event with this id was already handled.

    Primary lookup is an exact, indexed equality match against the
    dedicated ``webhook_events.event_id`` column (migration v6) — no
    payload scanning for the common path.

    Legacy rows written before migration v6 carry ``event_id = NULL``, so
    for those we fall back to a bounded scan of recent payloads. This keeps
    a Stripe retry of a pre-migration event deduplicated; every event stored
    after the migration takes the fast exact path and never reaches the
    fallback.
    """
    if not event_id:
        return False
    try:
        hit = db.conn.execute(
            "SELECT 1 FROM webhook_events WHERE partner = ? AND event_id = ? LIMIT 1",
            (PARTNER_NAME, event_id),
        ).fetchone()
        if hit:
            return True
        # Legacy fallback: only rows with NULL event_id can be old enough to
        # need a payload scan; new rows are always caught by the exact lookup.
        rows = db.conn.execute(
            "SELECT payload FROM webhook_events WHERE partner = ? AND event_id IS NULL "
            "ORDER BY id DESC LIMIT 250",
            (PARTNER_NAME,),
        ).fetchall()
        for row in rows:
            try:
                if json.loads(row["payload"]).get("id") == event_id:
                    return True
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue
    except Exception:
        logger.warning("Idempotency check query failed", exc_info=True)
    return False


# ── Company mapping ─────────────────────────────────────────────────────

def _company_from_event(db, event: dict) -> Optional[int]:
    """Map a Stripe event to a company via ``subscriptions.stripe_customer_id``."""
    obj = (event.get("data") or {}).get("object") or {}
    customer = obj.get("customer")
    if not customer:
        return None
    row = db.conn.execute(
        "SELECT company_id FROM subscriptions WHERE stripe_customer_id = ?",
        (customer,),
    ).fetchone()
    return row["company_id"] if row else None


# ── Event handlers ──────────────────────────────────────────────────────

def _handle_checkout_completed(db, obj: dict, company_id: int) -> dict:
    """Activate the subscription row from a completed Checkout Session.

    The session object carries ``customer`` and ``subscription`` ids; the
    billing period itself is refined by subsequent ``invoice.paid`` events,
    so current_period defaults to now→now+30d when the session doesn't
    include period fields.
    """
    now = _now_iso()
    period_end = _iso_ts(obj.get("current_period_end")) or (
        (datetime.utcnow() + timedelta(days=DEFAULT_PERIOD_DAYS)).isoformat()
    )
    period_start = _iso_ts(obj.get("current_period_start")) or now
    stripe_customer = obj.get("customer")
    stripe_sub = obj.get("subscription")

    row = db.conn.execute(
        "SELECT id FROM subscriptions WHERE company_id = ?", (company_id,)
    ).fetchone()
    if row is not None:
        db.conn.execute(
            """UPDATE subscriptions
               SET status = 'active',
                   stripe_customer_id = COALESCE(?, stripe_customer_id),
                   stripe_subscription_id = COALESCE(?, stripe_subscription_id),
                   current_period_start = ?,
                   current_period_end = ?,
                   updated_at = ?
               WHERE id = ?""",
            (stripe_customer, stripe_sub, period_start, period_end, now, row["id"]),
        )
        db.conn.commit()
        return {"status": "processed", "details": "subscription activated"}

    # Defensive create (only reachable when a company mapping already exists).
    truck_count = db.conn.execute(
        "SELECT COUNT(*) AS cnt FROM trucks WHERE company_id = ?", (company_id,)
    ).fetchone()
    db.conn.execute(
        """INSERT INTO subscriptions
           (company_id, billing_term, status, licensed_truck_count,
            current_period_start, current_period_end, stripe_customer_id,
            stripe_subscription_id, created_at, updated_at)
           VALUES (?, 'monthly', 'active', ?, ?, ?, ?, ?, ?, ?)""",
        (
            company_id,
            int(truck_count["cnt"]) if truck_count else 0,
            period_start,
            period_end,
            stripe_customer,
            stripe_sub,
            now,
            now,
        ),
    )
    db.conn.commit()
    return {"status": "processed", "details": "subscription row created"}


def _handle_invoice_paid(db, obj: dict, company_id: int) -> dict:
    """Record a paid invoice (with fiscal stub fields) and refresh the period."""
    now = _now_iso()
    stripe_invoice_id = obj.get("id")
    amount_cents = int(obj.get("amount_paid") or obj.get("amount_due") or 0)
    issued_at = _iso_ts(obj.get("created")) or now

    # The invoice's first line period end is the subscription's new period end.
    period_end = None
    lines = obj.get("lines") or {}
    for line in (lines.get("data") or []):
        period = line.get("period")
        if period and period.get("end"):
            period_end = _iso_ts(period.get("end"))
            break

    existing = db.conn.execute(
        "SELECT id FROM billing_invoices WHERE stripe_invoice_id = ?",
        (stripe_invoice_id,),
    ).fetchone()
    sub_row = db.conn.execute(
        "SELECT id FROM subscriptions WHERE company_id = ?", (company_id,)
    ).fetchone()
    sub_id = sub_row["id"] if sub_row else None

    if existing is not None:
        db.conn.execute(
            "UPDATE billing_invoices SET status = 'paid', paid_at = ? WHERE id = ?",
            (now, existing["id"]),
        )
    else:
        db.conn.execute(
            """INSERT INTO billing_invoices
               (company_id, subscription_id, stripe_invoice_id, amount_cents,
                status, issued_at, paid_at, created_at)
               VALUES (?, ?, ?, ?, 'paid', ?, ?, ?)""",
            (company_id, sub_id, stripe_invoice_id, amount_cents, issued_at, now, now),
        )
    if sub_row is not None:
        if period_end:
            db.conn.execute(
                "UPDATE subscriptions SET status = 'active', current_period_end = ?, "
                "updated_at = ? WHERE id = ?",
                (period_end, now, sub_row["id"]),
            )
        else:
            db.conn.execute(
                "UPDATE subscriptions SET status = 'active', updated_at = ? WHERE id = ?",
                (now, sub_row["id"]),
            )
    db.conn.commit()
    return {"status": "processed", "details": "invoice recorded"}


def _handle_payment_failed(db, obj: dict, company_id: int) -> dict:
    """Mark the subscription past_due on invoice.payment_failed."""
    now = _now_iso()
    db.conn.execute(
        "UPDATE subscriptions SET status = 'past_due', updated_at = ? WHERE company_id = ?",
        (now, company_id),
    )
    db.conn.commit()
    return {"status": "processed", "details": "subscription marked past_due"}


def _handle_subscription_deleted(db, obj: dict, company_id: int) -> dict:
    """Mark the subscription canceled on customer.subscription.deleted."""
    now = _now_iso()
    db.conn.execute(
        "UPDATE subscriptions SET status = 'canceled', updated_at = ? WHERE company_id = ?",
        (now, company_id),
    )
    db.conn.commit()
    return {"status": "processed", "details": "subscription marked canceled"}


_HANDLERS = {
    "checkout.session.completed": _handle_checkout_completed,
    "invoice.paid": _handle_invoice_paid,
    "invoice.payment_failed": _handle_payment_failed,
    "customer.subscription.deleted": _handle_subscription_deleted,
}


def _dispatch(db, event_type: str, obj: dict, company_id: Optional[int]) -> dict:
    if not company_id:
        return {
            "status": "skipped",
            "details": "No subscription maps to this Stripe customer",
        }
    handler = _HANDLERS.get(event_type)
    if handler is None:
        return {"status": "skipped", "details": f"Unhandled event type: {event_type}"}
    try:
        return handler(db, obj, company_id)
    except Exception as exc:
        logger.error("Stripe webhook handler %s failed for company %s: %s",
                     event_type, company_id, exc, exc_info=True)
        return {"status": "error", "details": str(exc)}


# ── Receiver ────────────────────────────────────────────────────────────

@router.post("")
async def receive_stripe_webhook(request: Request, db=Depends(get_db)):
    """Verify, dedupe, and apply a Stripe webhook event."""
    raw_body = await request.body()
    request.state.webhook_raw_body = raw_body

    secret = (BackendSettings().stripe_webhook_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=501,
            detail={
                "error_code": ErrorCode.NOT_IMPLEMENTED.value,
                "detail": "Stripe webhooks are not configured. Set "
                          "STRIPE_WEBHOOK_SECRET to enable them. "
                          "Unverified payloads are never processed.",
            },
        )

    # ── Verify signature via the Stripe SDK ──────────────────────────
    try:
        import stripe  # type: ignore[import-untyped]
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "detail": "Stripe SDK is not installed but a webhook secret is "
                          "configured. Install `stripe` from requirements.api.txt.",
            },
        )

    try:
        event = stripe.Webhook.construct_event(
            payload=raw_body,
            sig_header=request.headers.get("Stripe-Signature", ""),
            secret=secret,
        )
    except Exception as exc:
        if getattr(stripe, "error", None) and isinstance(
            exc, stripe.error.SignatureVerificationError
        ):
            logger.warning("Stripe webhook signature verification failed: %s", exc)
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": ErrorCode.WEBHOOK_SIGNATURE_INVALID.value,
                    "detail": "Invalid Stripe webhook signature.",
                },
            )
        logger.warning("Stripe webhook construct_event failed: %s", exc)
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.WEBHOOK_SIGNATURE_INVALID.value,
                "detail": "Could not verify Stripe webhook payload.",
            },
        )

    event_id = str(event.get("id", ""))
    event_type = str(event.get("type", ""))

    # ── Idempotency: skip already-processed events ───────────────────
    if _already_processed(db, event_id):
        logger.info("Duplicate Stripe event skipped: %s", event_id)
        return {
            "received": True,
            "event_id": event_id,
            "event_type": event_type,
            "status": "skipped",
            "duplicate": True,
        }

    company_id = _company_from_event(db, event)
    stored_id = _store_event(db, event, company_id=company_id, status="processing")

    obj = (event.get("data") or {}).get("object") or {}
    result = _dispatch(db, event_type, obj, company_id)
    if stored_id:
        _update_status(db, stored_id, result.get("status", "processed"))

    logger.info(
        "Stripe webhook processed: event=%s type=%s company=%s status=%s",
        event_id, event_type, company_id, result.get("status"),
    )

    return {
        "received": True,
        "event_id": event_id,
        "event_type": event_type,
        "status": result.get("status", "processed"),
        "details": result.get("details", ""),
    }
