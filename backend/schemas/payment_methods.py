from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict


class PaymentMethodOut(BaseModel):
    """A saved card payment method (blueprint §4.5)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    type: str
    card: Dict[str, Any]
    billing_details: Dict[str, Any]
    created: int
    is_default: bool = False


class SetupIntentResponse(BaseModel):
    """Response for POST /payment-methods/setup-intent."""

    model_config = ConfigDict(extra="ignore")

    client_secret: str
    setup_intent_id: str