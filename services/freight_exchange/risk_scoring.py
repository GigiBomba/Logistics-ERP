"""Freight Exchange risk scoring — documented, weighted formula.

Returns a 0.0–1.0 risk score (higher = riskier) based on concrete factors.
Weights are configurable per company, not hardcoded inline.  The formula
is deterministic and explainable — every score can be traced back to
which factors contributed.

Provider-agnostic: if a provider doesn't expose counterparty rating,
that input is simply absent (neutral contribution).  No per-provider
``if`` branches exist here.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Default weights (overridable per company via settings) ─────────────
DEFAULT_RISK_WEIGHTS = {
    "tightness": 0.30,       # delivery-window vs. estimated duration
    "cross_border": 0.25,    # number of border crossings
    "counterparty": 0.20,    # counterparty rating (if available)
    "price_deviation": 0.15,  # price vs. market-rate deviation
    "night_driving": 0.10,   # requires night driving
}
# Sum must be 1.0 for normalized scoring


def compute_risk_score(
    *,
    pickup_window: tuple[datetime, datetime],
    delivery_window: tuple[datetime, datetime],
    estimated_duration_hours: float,
    origin: str = "",
    destination: str = "",
    counterparty_rating: Optional[float] = None,
    load_price: float = 0.0,
    market_rate: Optional[float] = None,
    weights: Optional[dict[str, float]] = None,
) -> float:
    """Compute a 0.0–1.0 risk score for a freight load.

    Each factor contributes 0.0–1.0, weighted and summed.
    Higher score = higher risk.

    Args:
        pickup_window: (from, to) pickup datetime tuple
        delivery_window: (from, to) delivery datetime tuple
        estimated_duration_hours: route duration estimate
        origin: origin location string (for cross-border inference)
        destination: destination location string
        counterparty_rating: 0.0–1.0 rating (None if unavailable)
        load_price: the load's price
        market_rate: average market rate for this route (None if unavailable)
        weights: per-company weight overrides (uses DEFAULT_RISK_WEIGHTS if None)

    Returns:
        float in range 0.0–1.0
    """
    w = weights or DEFAULT_RISK_WEIGHTS
    # Auto-normalize: ensure weights sum to 1.0
    total_w = sum(w.values())
    if total_w > 0 and abs(total_w - 1.0) > 0.001:
        w = {k: v / total_w for k, v in w.items()}
    now = datetime.now(timezone.utc)

    # ── 1. Tightness: how narrow is the delivery window? ─────────────
    #    wider window → lower risk; narrow/impossible → higher risk
    pickup_duration = (pickup_window[1] - pickup_window[0]).total_seconds() / 3600
    delivery_duration = (delivery_window[1] - delivery_window[0]).total_seconds() / 3600
    available_window = max(pickup_duration, delivery_duration)
    if estimated_duration_hours > 0:
        tightness_ratio = estimated_duration_hours / max(available_window, 0.1)
        tightness = min(tightness_ratio, 1.0)
    else:
        tightness = 0.5  # neutral if no duration estimate

    # ── 2. Cross-border: more borders → higher risk ──────────────────
    #    Simple heuristic: if origin/destination differ, estimate crossings
    cross_border = 0.0
    if origin and destination and origin.lower() != destination.lower():
        cross_border = 0.3  # assume cross-border if different cities
        # Scale up if country codes differ (simple prefix check)
        if origin[:2].upper() != destination[:2].upper():
            cross_border = 0.7

    # ── 3. Counterparty: unknown = neutral, low rating = high risk ───
    if counterparty_rating is not None:
        # Invert: high rating → low risk
        counterparty = max(0.0, 1.0 - min(counterparty_rating, 1.0))
    else:
        counterparty = 0.5  # neutral — no data, no penalty

    # ── 4. Price deviation: far from market rate = riskier ───────────
    if market_rate is not None and market_rate > 0 and load_price > 0:
        deviation = abs(load_price - market_rate) / market_rate
        price_deviation = min(deviation, 1.0)
    else:
        price_deviation = 0.0  # no market data, no penalty

    # ── 5. Night driving: pickup/delivery in night hours ────────────
    pickup_hour = pickup_window[0].hour
    delivery_hour = delivery_window[1].hour
    night = 0.0
    if 0 <= pickup_hour < 6 or 22 <= pickup_hour <= 23:
        night += 0.5
    if 0 <= delivery_hour < 6 or 22 <= delivery_hour <= 23:
        night += 0.5
    night_driving = min(night, 1.0)

    # ── Weighted sum ─────────────────────────────────────────────────
    score = (
        w.get("tightness", 0.30) * tightness
        + w.get("cross_border", 0.25) * cross_border
        + w.get("counterparty", 0.20) * counterparty
        + w.get("price_deviation", 0.15) * price_deviation
        + w.get("night_driving", 0.10) * night_driving
    )

    return round(min(max(score, 0.0), 1.0), 4)
