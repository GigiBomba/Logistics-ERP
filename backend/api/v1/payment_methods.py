"""Stripe payment-method endpoints (blueprint §4.5, deferral D-B1).

GET    /api/v1/payment-methods                — List saved card payment methods.
POST   /api/v1/payment-methods/setup-intent   — Create a SetupIntent (ensures a Stripe customer).
DELETE /api/v1/payment-methods/{pm_id}        — Detach (remove) a saved payment method.

Stripe access mirrors ``subscriptions.py``: the SDK is imported lazily and
every call is env-gated on ``OPERION_STRIPE_SECRET_KEY``. When Stripe is not
configured the list endpoint returns an empty list and setup-intent returns
a clearly-marked mock response. Tests always monkeypatch the ``stripe``
module — no live calls are ever made by the test suite.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.v1.subscriptions import (
    _get_or_create_subscription,
    _save_subscription,
)
from backend.config import BackendSettings
from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.payment_methods import PaymentMethodOut, SetupIntentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment-methods", tags=["payment-methods"])


# ── Small helpers (mirror subscriptions.py) ─────────────────────────────

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


def _stripe_customer_id(company_id: int, db: DatabaseManager) -> Optional[str]:
    """Return the company's Stripe customer id (same lookup subscriptions.py uses)."""
    row = db.conn.execute(
        "SELECT stripe_customer_id FROM subscriptions WHERE company_id = ?",
        (company_id,),
    ).fetchone()
    if row is None:
        return None
    return row["stripe_customer_id"] or None


def _ensure_stripe_customer(company_id: int, db: DatabaseManager, stripe) -> str:
    """Return the company's Stripe customer id, creating it when missing.

    Mirrors the customer-creation logic used by the checkout endpoint: the
    customer is created with the company name and stored on the company's
    ``subscriptions`` row (seeding the row first if it doesn't exist yet).
    """
    sub = _get_or_create_subscription(company_id, db)
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
    return customer_id


def _stripe_default_payment_method_id(stripe, customer_id: str) -> Optional[str]:
    """Best-effort lookup of the customer's default card payment method."""
    try:
        customer = stripe.Customer.retrieve(customer_id)
    except Exception as exc:
        logger.warning("Stripe customer retrieve failed for %s: %s", customer_id, exc)
        return None
    invoice_settings = getattr(customer, "invoice_settings", None)
    if invoice_settings is not None:
        default = getattr(invoice_settings, "default_payment_method", None)
        if default:
            return str(default)
    return getattr(customer, "default_source", None) or None


def _map_payment_method(pm, default_id: Optional[str]) -> PaymentMethodOut:
    card = getattr(pm, "card", None) or {}
    return PaymentMethodOut(
        id=getattr(pm, "id", ""),
        type=getattr(pm, "type", ""),
        card={
            "brand": getattr(card, "brand", None),
            "last4": getattr(card, "last4", None),
            "exp_month": getattr(card, "exp_month", None),
            "exp_year": getattr(card, "exp_year", None),
        },
        billing_details=dict(getattr(pm, "billing_details", None) or {}),
        created=int(getattr(pm, "created", 0) or 0),
        is_default=bool(default_id) and getattr(pm, "id", None) == default_id,
    )


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("", response_model=list[PaymentMethodOut])
def list_payment_methods(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """List saved card payment methods for the company's Stripe customer.

    When Stripe is unconfigured — or the company has no Stripe customer yet —
    an empty list is returned, mirroring how subscriptions.py degrades to
    mocks when no key is configured.
    """
    company_id = _get_company_id(current_user)
    stripe = _get_stripe_module()
    secret = _stripe_secret_key()

    if not stripe or not secret:
        return []

    customer_id = _stripe_customer_id(company_id, db)
    if not customer_id:
        return []

    try:
        stripe.api_key = secret
        items = stripe.PaymentMethod.list(customer=customer_id, type="card")
    except Exception as exc:
        logger.error("Stripe payment-method list failed for company %s: %s", company_id, exc)
        raise HTTPException(status_code=502, detail="Stripe payment-method list failed")

    default_id = _stripe_default_payment_method_id(stripe, customer_id)
    return [
        _map_payment_method(pm, default_id)
        for pm in (getattr(items, "data", None) or [])
    ]


@router.post("/setup-intent", response_model=SetupIntentResponse)
def create_setup_intent(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Create a Stripe SetupIntent so a card can be saved for the company.

    Ensures the company has a Stripe customer (creating one exactly like the
    checkout endpoint does), then creates the SetupIntent and returns its
    client secret to the website. When Stripe is unconfigured a clearly
    marked mock response is returned.
    """
    company_id = _get_company_id(current_user)
    stripe = _get_stripe_module()
    secret = _stripe_secret_key()

    if not stripe or not secret:
        return SetupIntentResponse(
            client_secret=f"seti_mock_{company_id}_secret",
            setup_intent_id=f"seti_mock_{company_id}",
        )

    stripe.api_key = secret
    customer_id = _ensure_stripe_customer(company_id, db, stripe)
    try:
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=["card"],
        )
    except Exception as exc:
        logger.error("Stripe SetupIntent creation failed for company %s: %s", company_id, exc)
        raise HTTPException(status_code=502, detail="Stripe SetupIntent creation failed")

    return SetupIntentResponse(
        client_secret=setup_intent.client_secret,
        setup_intent_id=setup_intent.id,
    )


@router.delete("/{payment_method_id}")
def remove_payment_method(
    payment_method_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Detach (remove) a saved payment method from the company's Stripe customer."""
    company_id = _get_company_id(current_user)
    stripe = _get_stripe_module()
    secret = _stripe_secret_key()

    if not stripe or not secret:
        raise HTTPException(status_code=502, detail="Stripe is not configured")

    stripe.api_key = secret
    try:
        stripe.PaymentMethod.detach(payment_method_id)
    except Exception as exc:
        logger.error(
            "Stripe payment-method detach failed for company %s pm=%s: %s",
            company_id, payment_method_id, exc,
        )
        error_name = type(exc).__name__.lower()
        error_code = str(getattr(exc, "code", "") or "")
        if "invalidrequesterror" in error_name or error_code == "resource_missing":
            raise HTTPException(status_code=404, detail="Payment method not found") from exc
        raise HTTPException(status_code=502, detail="Stripe payment-method removal failed") from exc

    return {"status": "removed"}