"""Subscription plan and billing endpoints (per-truck model, blueprint §4).

GET  /api/v1/subscriptions/current      — Current subscription state (+ billing breakdown + trial).
GET  /api/v1/subscriptions/plans        — Available pricing tiers (per-truck).
GET  /api/v1/subscriptions/invoices     — Real invoice history (billing_invoices table).
POST /api/v1/subscriptions/checkout     — Stripe Checkout session (real when configured, mock otherwise).
POST /api/v1/subscriptions/portal       — Stripe Customer Portal session (real/mock).
POST /api/v1/subscriptions/trucks/add   — Add a truck to the subscription (desktop ERP / website).
POST /api/v1/subscriptions/trucks/remove— Remove a truck from the subscription.
POST /api/v1/subscriptions/billing-term — Switch monthly <-> annual.
POST /api/v1/subscriptions/cancel       — Cancel at term end (trucks stay usable until current_period_end).
POST /api/v1/subscriptions/reactivate   — Re-activate a canceled subscription.
POST /api/v1/subscriptions/toggle-addon — Toggle AI Copilot / priority support / API access.

Pricing is read from the ``subscriptions`` row (stored as data, never
hardcoded here) so future price changes don't require a deploy.

Billing model notes
-------------------
* Monthly add/remove: licensed_truck_count changes immediately (truck usable/
  unusable now) and pending_truck_count mirrors the next-cycle count. No
  charge today — the price change lands on the next invoice.
* Annual add: prorated charge (price_per_truck × remaining full months)
  recorded in a ``subscription_truck_events`` row with billed_immediately=1.
  The Stripe charge is attempted only when STRIPE_SECRET_KEY is configured;
  otherwise the amount is recorded and marked as un-billed (an admin/batch
  can reconcile it later).
* Annual remove: deactivates immediately with no refund; the unused term
  value becomes service_credit_cents (a ledger balance), redeemable against
  a future annual truck add in the same term.
* Term switch: monthly→annual prorates the remaining days of the current
  month into service_credit_cents; annual→monthly is rejected mid-term
  (per blueprint §4.4 the switch only takes effect at the term's natural end).

Stripe is strictly env-gated: nothing here requires live keys. Tests always
monkeypatch the ``stripe`` module — no live calls are ever made by the test
suite.
"""
from __future__ import annotations


import logging
import math
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.config import BackendSettings
from backend.dependencies import get_db
from backend.dependencies_security import require_admin, require_dispatcher
from backend.db import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# Defaults used ONLY when seeding a fresh subscription row (the row then
# becomes the source of truth for pricing).
DEFAULT_PRICE_PER_TRUCK_ERP_CENTS = 1000
DEFAULT_PRICE_PER_TRUCK_AI_CENTS = 1000
DEFAULT_PRIORITY_SUPPORT_PRICE_CENTS = 5000
DEFAULT_API_ACCESS_PRICE_CENTS = 10000
DEFAULT_ANNUAL_DISCOUNT_PCT = 15.00
DEFAULT_PERIOD_DAYS = 30

VALID_ADDONS = ("ai_copilot", "priority_support", "api_access")

FREE_TIERS = ("starter", "free", None, "")

_SUBSCRIPTION_COLUMNS = (
    "id", "company_id", "billing_term", "status", "licensed_truck_count",
    "pending_truck_count", "ai_copilot_enabled", "priority_support_enabled",
    "api_access_enabled", "price_per_truck_erp_cents",
    "price_per_truck_ai_cents", "priority_support_price_cents",
    "api_access_price_cents", "annual_discount_pct", "current_period_start",
    "current_period_end", "trial_ends_at", "payment_deferred_until",
    "service_credit_cents", "stripe_customer_id", "stripe_subscription_id",
    "created_at", "updated_at",
)


# ── Small helpers ────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Unparseable timestamp: %r", value)
        return None


def _trial_is_expired(trial_ends: Optional[str]) -> bool:
    """Return True when *trial_ends* is an ISO timestamp in the past.

    Missing/unparseable values are treated as NOT expired so enforcement
    never locks a company on malformed data.
    """
    end = _parse_ts(trial_ends)
    if end is None:
        return False
    if end.tzinfo is not None:
        return end.astimezone().replace(tzinfo=None) < datetime.utcnow()
    return end < datetime.utcnow()


def _is_free_tier(tier: Optional[str]) -> bool:
    return (tier or "").strip().lower() in ("starter", "free", "")


def _compute_status(subscription: Dict[str, Any]) -> str:
    """Derive an honest status from the row + company trial data.

    A provisioned trial that lapsed with no paid tier is 'locked', never
    silently 'active' (audit F1 behavior preserved from the old builder).
    """
    trial_ends = subscription.get("trial_ends_at")
    if trial_ends and not _trial_is_expired(trial_ends):
        return "trialing"
    if trial_ends and _trial_is_expired(trial_ends):
        return "locked"
    return "active"


def _get_company_id(current_user: Dict[str, Any]) -> int:
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User has no company")
    return int(company_id)


def _get_stripe_module():
    """Return the ``stripe`` module, or None when not installed."""
    try:
        import stripe  # type: ignore[import-untyped]
        return stripe
    except ImportError:
        return None


def _stripe_secret_key() -> str:
    return (BackendSettings().stripe_secret_key or "").strip()


def _audit(db: DatabaseManager, event_type: str, entity_id: str, data: dict, company_id: int) -> None:
    """Best-effort write to the operation_events audit trail."""
    try:
        from repositories.audit_repository import AuditRepository
        AuditRepository(db).log_event(
            event_type=event_type,
            entity_type="subscription",
            entity_id=entity_id,
            data=data,
            company_id=company_id,
        )
    except Exception:
        logger.warning("Audit write failed for %s", event_type, exc_info=True)


# ── Subscription row access / lazy seed ─────────────────────────────────

def _get_or_create_subscription(company_id: int, db: DatabaseManager) -> Dict[str, Any]:
    """Return the company's subscription row, lazily seeding one if missing.

    Seed strategy: a fresh row is derived from ``companies`` (trial_ends_at,
    subscription_tier, created_at) plus the current truck count. The row then
    becomes the single source of truth for pricing/flags. This runs on
    GET /current and on every mutating endpoint, so a brand-new company gets
    a row on first billing-touch without a one-off migration script.
    """
    row = db.conn.execute(
        "SELECT * FROM subscriptions WHERE company_id = ?", (company_id,)
    ).fetchone()
    if row is not None:
        return dict(row)

    company = db.conn.execute(
        "SELECT subscription_tier, trial_ends_at, created_at "
        "FROM companies WHERE id = ?",
        (company_id,),
    ).fetchone()
    now = _now_iso()
    trial_ends = company["trial_ends_at"] if company else None
    tier = company["subscription_tier"] if company else None
    created_at = company["created_at"] if company else now

    truck_count = db.conn.execute(
        "SELECT COUNT(*) AS cnt FROM trucks WHERE company_id = ?",
        (company_id,),
    ).fetchone()
    licensed_count = int(truck_count["cnt"]) if truck_count else 0

    trial_row = {
        "company_id": company_id,
        "billing_term": "monthly",
        "status": "trialing",
        "licensed_truck_count": licensed_count,
        "pending_truck_count": None,
        "ai_copilot_enabled": 0,
        "priority_support_enabled": 0,
        "api_access_enabled": 0,
        "price_per_truck_erp_cents": DEFAULT_PRICE_PER_TRUCK_ERP_CENTS,
        "price_per_truck_ai_cents": DEFAULT_PRICE_PER_TRUCK_AI_CENTS,
        "priority_support_price_cents": DEFAULT_PRIORITY_SUPPORT_PRICE_CENTS,
        "api_access_price_cents": DEFAULT_API_ACCESS_PRICE_CENTS,
        "annual_discount_pct": DEFAULT_ANNUAL_DISCOUNT_PCT,
        "current_period_start": now,
        "current_period_end": (datetime.utcnow() + timedelta(days=DEFAULT_PERIOD_DAYS)).isoformat(),
        "trial_ends_at": trial_ends,
        "payment_deferred_until": None,
        "service_credit_cents": 0,
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "created_at": created_at,
        "updated_at": now,
    }
    # Honest initial status (matches _compute_status for a fresh trial).
    if trial_ends and not _trial_is_expired(trial_ends):
        trial_row["status"] = "trialing"
    elif trial_ends and _trial_is_expired(trial_ends) and _is_free_tier(tier):
        trial_row["status"] = "locked"
    else:
        trial_row["status"] = "active"

    cols = ", ".join(_SUBSCRIPTION_COLUMNS[1:])  # exclude id (autoincrement)
    placeholders = ", ".join("?" for _ in _SUBSCRIPTION_COLUMNS[1:])
    values = tuple(trial_row[k] for k in _SUBSCRIPTION_COLUMNS[1:])
    try:
        db.conn.execute(
            f"INSERT INTO subscriptions ({cols}) VALUES ({placeholders})",
            values,
        )
        db.conn.commit()
    except Exception:
        # Lost a race with another request — re-read the winning row.
        db.conn.rollback()
        row = db.conn.execute(
            "SELECT * FROM subscriptions WHERE company_id = ?", (company_id,)
        ).fetchone()
        if row is not None:
            return dict(row)
        logger.error("Failed to seed subscription for company %s", company_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initialise subscription")

    row = db.conn.execute(
        "SELECT * FROM subscriptions WHERE company_id = ?", (company_id,)
    ).fetchone()
    return dict(row)


def _load_subscription(company_id: int, db: DatabaseManager) -> Dict[str, Any]:
    row = db.conn.execute(
        "SELECT * FROM subscriptions WHERE company_id = ?", (company_id,)
    ).fetchone()
    if row is None:
        return _get_or_create_subscription(company_id, db)
    return dict(row)


def _save_subscription(db: DatabaseManager, subscription_id: int, updates: Dict[str, Any]) -> None:
    if not updates:
        return
    sets = ", ".join(f"{k} = ?" for k in updates)
    values = tuple(updates[k] for k in updates) + (_now_iso(), subscription_id)
    db.conn.execute(
        f"UPDATE subscriptions SET {sets}, updated_at = ? WHERE id = ?",
        values,
    )
    db.conn.commit()


def _record_truck_event(
    db: DatabaseManager,
    subscription_id: int,
    truck_id: Any,
    event_type: str,
    billed_immediately: bool,
    amount_cents: Optional[int],
    source: str,
    user_id: Optional[int],
) -> None:
    db.conn.execute(
        """INSERT INTO subscription_truck_events
           (subscription_id, truck_id, event_type, billed_immediately,
            amount_cents, source, created_by_user_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            subscription_id, truck_id, event_type,
            int(billed_immediately), amount_cents, source, user_id, _now_iso(),
        ),
    )
    db.conn.commit()


def _remaining_full_months(period_end: Optional[str]) -> int:
    """Full months remaining in the current term, clamped to [1, 12].

    Proration simplification: a calendar month is approximated as 30 days
    and rounded up to the next full month, so any add mid-term is charged
    for at least one month (never zero).
    """
    end = _parse_ts(period_end)
    if end is None:
        return 1
    if end.tzinfo is not None:
        end = end.astimezone().replace(tzinfo=None)
    days = (end - datetime.utcnow()).days
    if days <= 0:
        return 1
    return max(1, min(12, (days + 29) // 30))


def _monthly_erp_total(sub: Dict[str, Any]) -> int:
    """Monthly ERP + AI per-truck total at the current licensed count."""
    count = int(sub.get("licensed_truck_count") or 0)
    total = count * int(sub.get("price_per_truck_erp_cents") or 0)
    if sub.get("ai_copilot_enabled"):
        total += count * int(sub.get("price_per_truck_ai_cents") or 0)
    return total


def _billing_breakdown(sub: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the price breakdown shown on the subscription page."""
    count = int(sub.get("licensed_truck_count") or 0)
    erp_monthly = int(sub.get("price_per_truck_erp_cents") or 0)
    ai_monthly = int(sub.get("price_per_truck_ai_cents") or 0)
    discount = float(sub.get("annual_discount_pct") or 0.0)
    ai_enabled = bool(sub.get("ai_copilot_enabled"))
    priority = int(sub.get("priority_support_price_cents") or 0)
    api = int(sub.get("api_access_price_cents") or 0)

    erp_month_cents = count * erp_monthly
    erp_year_cents = round(erp_month_cents * 12 * (1 - discount / 100))
    ai_month_cents = count * ai_monthly if ai_enabled else 0
    ai_year_cents = round(ai_month_cents * 12 * (1 - discount / 100)) if ai_enabled else 0
    priority_month_cents = priority if sub.get("priority_support_enabled") else 0
    api_month_cents = api if sub.get("api_access_enabled") else 0

    if sub.get("billing_term") == "annual":
        total_cents = erp_year_cents + ai_year_cents + priority_month_cents * 12 + api_month_cents * 12
    else:
        total_cents = erp_month_cents + ai_month_cents + priority_month_cents + api_month_cents

    return {
        "licensed_truck_count": count,
        "erp_month_cents": erp_month_cents,
        "erp_year_cents": erp_year_cents,
        "ai_copilot_month_cents": ai_month_cents,
        "ai_copilot_year_cents": ai_year_cents,
        "priority_support_month_cents": priority_month_cents,
        "api_access_month_cents": api_month_cents,
        "annual_discount_pct": discount,
        "billing_term": sub.get("billing_term"),
        "total_cents": total_cents,
        "total_eur": round(total_cents / 100, 2),
    }


def _trial_status(sub: Dict[str, Any]) -> Dict[str, Any]:
    trial_ends = sub.get("trial_ends_at")
    expired = _trial_is_expired(trial_ends) if trial_ends else False
    days_remaining = None
    if trial_ends and not expired:
        end = _parse_ts(trial_ends)
        if end is not None:
            if end.tzinfo is not None:
                end = end.astimezone().replace(tzinfo=None)
            days_remaining = max(0, (end - datetime.utcnow()).days)
    return {
        "is_trialing": bool(trial_ends) and not expired,
        "trial_ends_at": trial_ends,
        "is_expired": expired,
        "days_remaining": days_remaining,
    }


def _build_subscription(company_id: int, db: DatabaseManager) -> Dict[str, Any]:
    """Build the full per-truck subscription object (from the DB row)."""
    sub = _load_subscription(company_id, db)
    status = sub.get("status") or _compute_status(sub)
    return {
        "id": f"sub-{company_id}",
        "company_id": str(company_id),
        "billing_term": sub.get("billing_term", "monthly"),
        "status": status,
        "licensed_truck_count": sub.get("licensed_truck_count", 0),
        "pending_truck_count": sub.get("pending_truck_count"),
        "ai_copilot_enabled": bool(sub.get("ai_copilot_enabled")),
        "priority_support_enabled": bool(sub.get("priority_support_enabled")),
        "api_access_enabled": bool(sub.get("api_access_enabled")),
        "price_per_truck_erp_cents": sub.get("price_per_truck_erp_cents"),
        "price_per_truck_ai_cents": sub.get("price_per_truck_ai_cents"),
        "priority_support_price_cents": sub.get("priority_support_price_cents"),
        "api_access_price_cents": sub.get("api_access_price_cents"),
        "annual_discount_pct": sub.get("annual_discount_pct"),
        "current_period_start": sub.get("current_period_start"),
        "current_period_end": sub.get("current_period_end"),
        "trial_ends_at": sub.get("trial_ends_at"),
        "payment_deferred_until": sub.get("payment_deferred_until"),
        "service_credit_cents": sub.get("service_credit_cents", 0),
        "stripe_customer_id": sub.get("stripe_customer_id"),
        "stripe_subscription_id": sub.get("stripe_subscription_id"),
        "created_at": sub.get("created_at"),
        "updated_at": sub.get("updated_at"),
        "billing_breakdown": _billing_breakdown(sub),
        "trial": _trial_status(sub),
    }


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/current")
def get_current_subscription(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return the current company's subscription (per-truck model).

    Lazily seeds the ``subscriptions`` row from company trial data on first
    access, then returns state + billing breakdown + trial status.
    """
    company_id = _get_company_id(current_user)
    return _build_subscription(company_id, db)


@router.get("/plans")
def get_plans():
    """Return available per-truck pricing tiers."""
    return [
        {
            "id": "plan-per-truck",
            "name": "Per-Truck Billing",
            "description": "Pay per active truck per month. Includes all ERP features.",
            "price_per_truck_monthly_cents": DEFAULT_PRICE_PER_TRUCK_ERP_CENTS,
            "price_per_truck_annual_cents": round(
                DEFAULT_PRICE_PER_TRUCK_ERP_CENTS * 12 * (1 - DEFAULT_ANNUAL_DISCOUNT_PCT / 100)
            ),
            "ai_copilot_monthly_cents": DEFAULT_PRICE_PER_TRUCK_AI_CENTS,
            "ai_copilot_annual_cents": round(
                DEFAULT_PRICE_PER_TRUCK_AI_CENTS * 12 * (1 - DEFAULT_ANNUAL_DISCOUNT_PCT / 100)
            ),
            "annual_discount_pct": DEFAULT_ANNUAL_DISCOUNT_PCT,
            "features": [
                "Route planning & optimisation",
                "Fleet management dashboard",
                "Digital CMR generation",
                "Dispatch console",
                "Analytics & reporting",
                "Driver management",
                "Document management",
                "Email & chat support",
            ],
        },
    ]


@router.get("/invoices")
def get_invoices(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return real invoice history from ``billing_invoices`` (not a mock).

    Rows are created by the Stripe webhook (invoice.paid) and by annual
    proration events. Shape is a superset of the old static mock so the
    existing website invoice list keeps working.
    """
    company_id = _get_company_id(current_user)
    rows = db.conn.execute(
        "SELECT * FROM billing_invoices WHERE company_id = ? "
        "ORDER BY issued_at DESC, id DESC",
        (company_id,),
    ).fetchall()
    invoices = []
    for r in rows:
        row = dict(r)
        invoices.append({
            "id": f"inv-{row['id']}",
            "number": row.get("fiscal_invoice_id") or f"INV-{row['id']:06d}",
            "amount_cents": row.get("amount_cents"),
            "amount": round((row.get("amount_cents") or 0) / 100, 2),
            "currency": row.get("currency", "EUR"),
            "status": row.get("status"),
            "issued_at": row.get("issued_at"),
            "due_at": row.get("issued_at"),
            "paid_at": row.get("paid_at"),
            "stripe_invoice_id": row.get("stripe_invoice_id"),
            "fiscal_invoice_id": row.get("fiscal_invoice_id"),
            "fiscal_invoice_pdf_url": row.get("fiscal_invoice_pdf_url"),
            "subscription_id": row.get("subscription_id"),
        })
    return invoices


@router.post("/trucks/add")
def add_truck_to_subscription(
    body: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Add *truck_id* to the company's subscription.

    Monthly: licensed + pending increment, no charge today.
    Annual: licensed increments and a prorated charge is recorded
    (billed_immediately=1); the Stripe charge is only attempted when a key
    is configured — otherwise the amount is recorded as un-billed.
    """
    company_id = _get_company_id(current_user)
    truck_id = body.get("truck_id")
    source = body.get("source", "website")
    if source not in ("desktop_erp", "website"):
        raise HTTPException(status_code=400, detail="source must be 'desktop_erp' or 'website'")

    truck = db.conn.execute(
        "SELECT id FROM trucks WHERE id = ? AND company_id = ?",
        (truck_id, company_id),
    ).fetchone()
    if truck is None:
        raise HTTPException(status_code=404, detail="Truck not found for this company")

    # Pre-check: reject re-adding a truck that is already licensed (an 'added'
    # event exists with no later 'removed' event). Prevents double-billing /
    # licensed_truck_count inflation.
    already_licensed = db.conn.execute(
        """SELECT 1 FROM subscription_truck_events
           WHERE truck_id = ? AND event_type = 'added'
             AND NOT EXISTS (
                 SELECT 1 FROM subscription_truck_events t2
                 WHERE t2.truck_id = subscription_truck_events.truck_id
                   AND t2.event_type = 'removed'
                   AND t2.id > subscription_truck_events.id
             )
           LIMIT 1""",
        (truck_id,),
    ).fetchone()
    if already_licensed is not None:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": f"Truck {truck_id} is already licensed on this subscription",
                "error_code": "truck/already-licensed",
            },
        )

    sub = _get_or_create_subscription(company_id, db)
    billing_term = sub.get("billing_term", "monthly")
    new_licensed = int(sub.get("licensed_truck_count") or 0) + 1

    billed_immediately = False
    amount_cents = None
    service_credit_cents = int(sub.get("service_credit_cents") or 0)
    pending = None

    if billing_term == "annual":
        # Prorate: price_per_truck × remaining full months, credit applied first.
        months = _remaining_full_months(sub.get("current_period_end"))
        charge = months * int(sub.get("price_per_truck_erp_cents") or 0)
        if sub.get("ai_copilot_enabled"):
            charge += months * int(sub.get("price_per_truck_ai_cents") or 0)
        applied = min(service_credit_cents, charge)
        service_credit_cents -= applied
        amount_cents = charge - applied
        billed_immediately = True
        # Real charge only when Stripe is configured; otherwise recorded as un-billed.
        if _stripe_secret_key() and _get_stripe_module():
            try:
                _stripe_charge_proration(company_id, sub, amount_cents, f"Truck add #{truck_id}")
            except Exception as exc:
                logger.error("Stripe proration charge failed for company %s: %s", company_id, exc)
    else:
        # Monthly: no charge now; pending_truck_count tracks the next cycle.
        pending = new_licensed

    updates = {
        "licensed_truck_count": new_licensed,
        "pending_truck_count": pending,
        "service_credit_cents": service_credit_cents,
    }
    _save_subscription(db, sub["id"], updates)

    _record_truck_event(
        db, sub["id"], truck_id, "added", billed_immediately, amount_cents,
        source, current_user.get("id"),
    )
    _audit(db, "subscription.truck.added", str(sub["id"]), {
        "truck_id": truck_id, "billing_term": billing_term,
        "billed_immediately": billed_immediately, "amount_cents": amount_cents,
        "source": source,
    }, company_id)

    return _build_subscription(company_id, db)


@router.post("/trucks/remove")
def remove_truck_from_subscription(
    body: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Remove *truck_id* from the company's subscription.

    Monthly: licensed/pending decrement, no charge (invoice just drops).
    Annual: deactivates immediately with no refund — the unused term value
    becomes service_credit_cents (redeemable against a later annual add).
    """
    company_id = _get_company_id(current_user)
    truck_id = body.get("truck_id")
    source = body.get("source", "website")
    if source not in ("desktop_erp", "website"):
        raise HTTPException(status_code=400, detail="source must be 'desktop_erp' or 'website'")

    truck = db.conn.execute(
        "SELECT id FROM trucks WHERE id = ? AND company_id = ?",
        (truck_id, company_id),
    ).fetchone()
    if truck is None:
        raise HTTPException(status_code=404, detail="Truck not found for this company")

    sub = _get_or_create_subscription(company_id, db)
    new_licensed = max(0, int(sub.get("licensed_truck_count") or 0) - 1)
    service_credit_cents = int(sub.get("service_credit_cents") or 0)

    if sub.get("billing_term") == "annual":
        months = _remaining_full_months(sub.get("current_period_end"))
        credit = months * int(sub.get("price_per_truck_erp_cents") or 0)
        if sub.get("ai_copilot_enabled"):
            credit += months * int(sub.get("price_per_truck_ai_cents") or 0)
        service_credit_cents += credit
        pending = None
    else:
        pending = new_licensed

    updates = {
        "licensed_truck_count": new_licensed,
        "pending_truck_count": pending,
        "service_credit_cents": service_credit_cents,
    }
    _save_subscription(db, sub["id"], updates)

    _record_truck_event(
        db, sub["id"], truck_id, "removed", False, None, source, current_user.get("id"),
    )
    _audit(db, "subscription.truck.removed", str(sub["id"]), {
        "truck_id": truck_id, "billing_term": sub.get("billing_term"),
        "source": source, "service_credit_added_cents": service_credit_cents,
    }, company_id)

    return _build_subscription(company_id, db)


@router.post("/billing-term")
def change_billing_term(
    body: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
):
    """Switch billing term between monthly and annual.

    monthly→annual: prorates remaining days of the current month into
    service_credit_cents against the new annual charge.
    annual→monthly: rejected mid-term with a clear error — per blueprint
    §4.4 the switch only takes effect at the annual term's natural end
    (avoids letting a customer escape an annual commitment early).
    """
    company_id = _get_company_id(current_user)
    term = body.get("term")
    if term not in ("monthly", "annual"):
        raise HTTPException(status_code=400, detail="term must be 'monthly' or 'annual'")

    sub = _get_or_create_subscription(company_id, db)
    current_term = sub.get("billing_term", "monthly")
    if term == current_term:
        return _build_subscription(company_id, db)

    if current_term == "annual" and term == "monthly":
        raise HTTPException(
            status_code=400,
            detail=(
                "Annual subscriptions can only switch to monthly at the end of "
                f"the current term ({sub.get('current_period_end')}). "
                "You'll be able to switch when the term renews."
            ),
        )

    # monthly → annual
    now = datetime.utcnow()
    period_start = _parse_ts(sub.get("current_period_start")) or now
    period_end = _parse_ts(sub.get("current_period_end")) or (now + timedelta(days=DEFAULT_PERIOD_DAYS))
    if period_start.tzinfo is not None:
        period_start = period_start.astimezone().replace(tzinfo=None)
    if period_end.tzinfo is not None:
        period_end = period_end.astimezone().replace(tzinfo=None)
    total_days = max(1, (period_end - period_start).days)
    days_remaining = max(0, math.ceil((period_end - now).total_seconds() / 86400))
    days_remaining = min(days_remaining, total_days)
    monthly_total = _monthly_erp_total(sub)
    if sub.get("priority_support_enabled"):
        monthly_total += int(sub.get("priority_support_price_cents") or 0)
    if sub.get("api_access_enabled"):
        monthly_total += int(sub.get("api_access_price_cents") or 0)
    credit = round(monthly_total * days_remaining / total_days)

    new_start = now.isoformat()
    new_end = (now + timedelta(days=365)).isoformat()
    _save_subscription(db, sub["id"], {
        "billing_term": "annual",
        "pending_truck_count": None,
        "service_credit_cents": int(sub.get("service_credit_cents") or 0) + credit,
        "current_period_start": new_start,
        "current_period_end": new_end,
    })
    _audit(db, "subscription.billing_term.changed", str(sub["id"]), {
        "from": current_term, "to": "annual", "credit_cents": credit,
    }, company_id)

    return _build_subscription(company_id, db)


@router.post("/cancel")
def cancel_subscription(
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
):
    """Cancel the subscription.

    Contract stored in the response: trucks stay fully usable until
    current_period_end — no immediate lockout, no refund processing.
    """
    company_id = _get_company_id(current_user)
    sub = _get_or_create_subscription(company_id, db)
    if sub.get("status") == "canceled":
        return _build_subscription(company_id, db)

    _save_subscription(db, sub["id"], {"status": "canceled"})
    _audit(db, "subscription.canceled", str(sub["id"]), {
        "usable_until": sub.get("current_period_end"),
    }, company_id)

    return {
        "status": "canceled",
        "usable_until": sub.get("current_period_end"),
        "note": "Trucks remain usable until the current period ends. "
                "You can reactivate any time before then.",
        "subscription": _build_subscription(company_id, db),
    }


@router.post("/reactivate")
def reactivate_subscription(
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
):
    """Re-activate a canceled subscription (trial-aware)."""
    company_id = _get_company_id(current_user)
    sub = _get_or_create_subscription(company_id, db)

    trial_ends = sub.get("trial_ends_at")
    if trial_ends and not _trial_is_expired(trial_ends):
        new_status = "trialing"
    else:
        new_status = "active"

    _save_subscription(db, sub["id"], {"status": new_status})
    _audit(db, "subscription.reactivated", str(sub["id"]), {
        "new_status": new_status,
    }, company_id)

    return _build_subscription(company_id, db)


@router.post("/toggle-addon")
def toggle_addon(
    body: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
):
    """Toggle a subscription addon (ai_copilot, priority_support, api_access).

    Always updates the local DB flag; pushes the change to Stripe only when
    STRIPE_SECRET_KEY is configured (best-effort — the DB stays the source
    of truth).
    """
    addon = body.get("addon")
    enabled = bool(body.get("enabled", False))
    if addon not in VALID_ADDONS:
        raise HTTPException(status_code=400, detail=f"Unknown addon: {addon}")

    company_id = _get_company_id(current_user)
    sub = _get_or_create_subscription(company_id, db)
    col = f"{addon}_enabled"
    _save_subscription(db, sub["id"], {col: 1 if enabled else 0})

    if _stripe_secret_key() and _get_stripe_module() and sub.get("stripe_subscription_id"):
        try:
            _update_stripe_addon(company_id, sub, addon, enabled, db)
        except Exception as exc:
            logger.error("Stripe addon sync failed for company %s: %s", company_id, exc)

    _audit(db, "subscription.addon.toggled", str(sub["id"]), {
        "addon": addon, "enabled": enabled,
    }, company_id)

    logger.info("Addon toggled: company=%s addon=%s enabled=%s", company_id, addon, enabled)
    return _build_subscription(company_id, db)


@router.post("/checkout")
def create_checkout_session(
    body: Optional[Dict[str, Any]] = None,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Create a Stripe Checkout session.

    When STRIPE_SECRET_KEY is configured this creates a real Checkout
    Session (customer created if missing, quantity = licensed_truck_count,
    prices from the subscription row) and returns the hosted URL. An
    idempotency key is always sent. When unset, returns a clearly-marked
    mock URL — never a fake that looks like a real Stripe URL.
    """
    company_id = _get_company_id(current_user)
    sub = _get_or_create_subscription(company_id, db)
    stripe = _get_stripe_module()
    secret = _stripe_secret_key()

    if not stripe or not secret:
        return {
            "url": f"https://checkout.stripe.com/mock/session_{company_id}",
            "session_id": f"cs_mock_{company_id}",
            "mock": True,
            "note": "Stripe is not configured — this is a mock checkout URL.",
        }

    stripe.api_key = secret
    customer_id = sub.get("stripe_customer_id")
    if not customer_id:
        company = db.conn.execute(
            "SELECT company_name FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        customer = stripe.Customer.create(
            name=(company["company_name"] if company else None) or f"Company {company_id}",
            metadata={"company_id": company_id},
        )
        customer_id = customer.id
        _save_subscription(db, sub["id"], {"stripe_customer_id": customer_id})

    billing_term = sub.get("billing_term", "monthly")
    interval = "year" if billing_term == "annual" else "month"
    discount = float(sub.get("annual_discount_pct") or 0.0)
    erp_unit = int(sub.get("price_per_truck_erp_cents") or DEFAULT_PRICE_PER_TRUCK_ERP_CENTS)
    if billing_term == "annual":
        erp_unit = round(erp_unit * 12 * (1 - discount / 100))

    line_items = [{
        "quantity": int(sub.get("licensed_truck_count") or 1) or 1,
        "price_data": {
            "currency": "eur",
            "product_data": {"name": "Operion ERP — Per-Truck"},
            "recurring": {"interval": interval},
            "unit_amount": erp_unit,
        },
    }]
    if sub.get("ai_copilot_enabled"):
        ai_unit = int(sub.get("price_per_truck_ai_cents") or DEFAULT_PRICE_PER_TRUCK_AI_CENTS)
        if billing_term == "annual":
            ai_unit = round(ai_unit * 12 * (1 - discount / 100))
        line_items.append({
            "quantity": int(sub.get("licensed_truck_count") or 1) or 1,
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "AI Copilot (ARGO) — Per-Truck"},
                "recurring": {"interval": interval},
                "unit_amount": ai_unit,
            },
        })
    if sub.get("priority_support_enabled"):
        line_items.append({
            "quantity": 1,
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "Priority Support"},
                "recurring": {"interval": interval},
                "unit_amount": int(sub.get("priority_support_price_cents") or DEFAULT_PRIORITY_SUPPORT_PRICE_CENTS),
            },
        })
    if sub.get("api_access_enabled"):
        line_items.append({
            "quantity": 1,
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "API Access"},
                "recurring": {"interval": interval},
                "unit_amount": int(sub.get("api_access_price_cents") or DEFAULT_API_ACCESS_PRICE_CENTS),
            },
        })

    idempotency_key = body.get("idempotency_key") if body else None
    if not idempotency_key:
        idempotency_key = f"checkout-{company_id}-{int(time.time())}"

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer=customer_id,
        client_reference_id=str(company_id),
        success_url="https://operionerp.xyz/dashboard/subscription?checkout=success",
        cancel_url="https://operionerp.xyz/dashboard/subscription?checkout=cancelled",
        line_items=line_items,
        idempotency_key=idempotency_key,
    )
    logger.info("Checkout session created for company %s: %s", company_id, session.id)
    return {"url": session.url, "session_id": session.id, "mock": False}


@router.post("/portal")
def create_portal_session(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Create a Stripe Customer Portal session (real when configured)."""
    company_id = _get_company_id(current_user)
    sub = _get_or_create_subscription(company_id, db)
    stripe = _get_stripe_module()
    secret = _stripe_secret_key()

    if not stripe or not secret or not sub.get("stripe_customer_id"):
        return {
            "url": f"https://billing.stripe.com/mock/portal/company_{company_id}",
            "mock": True,
            "note": "Stripe is not configured (or no customer exists) — mock portal URL.",
        }

    stripe.api_key = secret
    session = stripe.billing_portal.Session.create(
        customer=sub["stripe_customer_id"],
        return_url="https://operionerp.xyz/dashboard/subscription",
    )
    return {"url": session.url, "mock": False}


# ── Stripe helper calls (only reached when a key is configured) ─────────

def _stripe_charge_proration(
    company_id: int,
    sub: Dict[str, Any],
    amount_cents: int,
    description: str,
) -> None:
    """Best-effort immediate Stripe charge for an annual proration event.

    Uses the customer's default payment method. If the customer has no
    Stripe setup yet the charge is skipped (recorded as un-billed in the
    event row by the caller); failures are logged, never raised.
    """
    stripe = _get_stripe_module()
    if not stripe or not sub.get("stripe_customer_id") or amount_cents <= 0:
        return
    stripe.api_key = _stripe_secret_key()
    stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="eur",
        customer=sub["stripe_customer_id"],
        description=description,
        metadata={"company_id": company_id, "reason": "annual_truck_proration"},
    )


def _update_stripe_addon(company_id: int, sub: Dict[str, Any], addon: str, enabled: bool, db=None) -> None:
    """Best-effort addon line-item update on the Stripe subscription.

    The addon→Stripe Price mapping lives in ``addon_price_mappings`` (migration
    v7). When a price id is configured the matching SubscriptionItem is
    created/modified/deleted (proration_behavior='none' — the next invoice
    picks up the delta). When no mapping exists the sync is deferred with a
    warning; DB flags remain authoritative regardless. Never raises.
    """
    stripe = _get_stripe_module()
    stripe_sub_id = sub.get("stripe_subscription_id")
    if not stripe or not stripe_sub_id:
        logger.warning(
            "Addon Stripe sync deferred for company %s (no stripe subscription id)",
            company_id,
        )
        return
    stripe.api_key = _stripe_secret_key()

    # Look up the configured Stripe Price id for this addon.
    price_id: Optional[str] = None
    if db is not None:
        try:
            row = db.conn.execute(
                "SELECT stripe_price_id FROM addon_price_mappings WHERE addon = ?",
                (addon,),
            ).fetchone()
            price_id = row["stripe_price_id"] if row else None
        except Exception as exc:
            logger.warning("Addon price mapping lookup failed for company %s: %s", company_id, exc)

    if not price_id:
        logger.warning(
            "Addon sync deferred: company=%s sub=%s addon=%s enabled=%s "
            "(price mapping not yet configured)",
            company_id, stripe_sub_id, addon, enabled,
        )
        return

    try:
        items = stripe.SubscriptionItem.list(subscription=stripe_sub_id)
        existing = None
        for item in getattr(items, "data", []) or []:
            price = getattr(item, "price", None)
            if price is not None and getattr(price, "id", None) == price_id:
                existing = item
                break
        if enabled:
            if existing is not None:
                stripe.SubscriptionItem.modify(
                    existing.id, quantity=1, proration_behavior="none",
                )
            else:
                stripe.SubscriptionItem.create(
                    subscription=stripe_sub_id,
                    price=price_id,
                    quantity=1,
                    proration_behavior="none",
                )
        elif existing is not None:
            stripe.SubscriptionItem.delete(existing.id)
        logger.info(
            "Addon Stripe sync OK: company=%s addon=%s enabled=%s price=%s",
            company_id, addon, enabled, price_id,
        )
    except Exception as exc:
        logger.error("Stripe addon sync failed for company %s addon %s: %s", company_id, addon, exc)


@router.post("/admin/reconcile-billing")
def reconcile_billing(
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Admin: reconcile unbilled immediate truck-proration events (idempotent).

    Selects every ``subscription_truck_events`` row with
    ``billed_immediately=1``, ``amount_cents>0`` and ``reconciled_at IS NULL``.
    For each row:

    * Stripe configured + ``stripe_customer_id`` present → best-effort
      ``PaymentIntent`` charge. On success the row is marked
      ``reconciled_at = datetime('now')``; on failure it is left NULL and
      counted as ``failed`` (a later run retries it).
    * Stripe unconfigured (or the customer has no Stripe setup yet) → the row
      stays NULL and is counted as ``deferred`` (recorded-but-not-yet-billed).

    Returns ``{total_unbilled, charged, failed, deferred}``.

    Scheduled runs (periodic reconciliation without an admin session):

        celery -A backend.celery_app.celery_app worker --beat -l info

    See ``backend/celery_app/schedule.py`` for the periodic task definition;
    the task must call this same select-and-charge logic with an admin key.
    """
    events = db.conn.execute(
        "SELECT * FROM subscription_truck_events "
        "WHERE billed_immediately = 1 AND amount_cents > 0 AND reconciled_at IS NULL"
    ).fetchall()
    total_unbilled = len(events)
    charged = failed = deferred = 0

    stripe = _get_stripe_module()
    secret = _stripe_secret_key()
    stripe_ready = bool(stripe and secret)

    for event in events:
        sub = db.conn.execute(
            "SELECT * FROM subscriptions WHERE id = ?", (event["subscription_id"],)
        ).fetchone()
        if sub is None or not (stripe_ready and sub["stripe_customer_id"]):
            deferred += 1
            continue
        try:
            stripe.api_key = secret
            stripe.PaymentIntent.create(
                amount=int(event["amount_cents"]),
                currency="eur",
                customer=sub["stripe_customer_id"],
                description=f"Operion annual truck proration (event {event['id']})",
                metadata={
                    "company_id": sub["company_id"],
                    "event_id": event["id"],
                    "reason": "reconcile_truck_proration",
                },
            )
        except Exception as exc:
            logger.error("Reconcile charge failed for event %s: %s", event["id"], exc)
            failed += 1
            continue
        db.conn.execute(
            "UPDATE subscription_truck_events SET reconciled_at = datetime('now') WHERE id = ?",
            (event["id"],),
        )
        charged += 1

    db.conn.commit()
    return {
        "total_unbilled": total_unbilled,
        "charged": charged,
        "failed": failed,
        "deferred": deferred,
    }
