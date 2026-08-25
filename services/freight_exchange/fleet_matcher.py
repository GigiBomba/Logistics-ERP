"""Freight Exchange Fleet Matcher — provider-agnostic truck-to-load scoring.

Scores every available truck against a given load using a weighted-sum
formula over 7 factors.  Returns a ranked list with deterministic reasons
derived from which scoring components contributed most — never free-text
explanations from anything non-deterministic.

Provider-agnostic by construction: ``provider_id`` has zero influence on
the scoring formula or its inputs.
"""
from __future__ import annotations

import logging
from typing import Optional

from models.common import Money
from models.freight_exchange_models import LoadSearchResult, TruckMatchScore
from services.freight_exchange.search import SearchEngineService

logger = logging.getLogger(__name__)

# ── Default scoring weights (per-company overridable via settings) ─────
DEFAULT_MATCHER_WEIGHTS = {
    "proximity": 25,
    "expected_profit": 20,
    "driver_hours": 15,
    "maintenance_health": 15,
    "trailer_compatibility": 10,
    "historical_reliability": 10,
    "positioning": 5,
}
# Sum = 100


class FleetMatcherService:
    """Scores and ranks available trucks for a given freight load.

    Delegates to existing services for raw data (fleet, drivers, maintenance,
    route estimation) and applies the weighted-sum scoring formula here.
    Zero provider-specific logic — every adapter's load is matched identically.

    Usage::

        matcher = FleetMatcherService(db)
        ranked = await matcher.find_best_trucks(
            company_id=1, provider_id="timocom", provider_load_id="TL-12345",
            top_n=5,
        )
    """

    def __init__(self, db):
        self.db = db
        self._search = SearchEngineService(db)

    async def find_best_trucks(
        self,
        company_id: int,
        provider_id: str,
        provider_load_id: str,
        top_n: int = 5,
    ) -> list[TruckMatchScore]:
        """Score every available truck and return the top N ranked results.

        Each truck is independently scored against the same load using
        the weighted-sum formula.  Results are sorted by score (descending)
        and limited to ``top_n``.
        """
        # 1. Fetch load
        load = await self._search.get_load(company_id, provider_id, provider_load_id)
        if load is None:
            raise ValueError(
                f"Load not found: provider={provider_id} load_id={provider_load_id}"
            )

        # 2. Get all trucks for this company
        trucks = self._get_available_trucks(company_id)
        if not trucks:
            return []

        # 3. Score each truck
        scores = []
        for truck in trucks:
            truck_score = self._score_truck(load, truck, company_id)
            if truck_score is not None:
                scores.append(truck_score)

        # 4. Sort by score descending, assign ranks, return top N
        scores.sort(key=lambda s: s.score, reverse=True)
        for i, s in enumerate(scores):
            s.rank = i + 1

        return scores[:top_n]

    # ── Private: scoring ────────────────────────────────────────────────

    def _score_truck(
        self,
        load: LoadSearchResult,
        truck: dict,
        company_id: int,
    ) -> Optional[TruckMatchScore]:
        """Score a single truck against a load.

        Returns None if the truck cannot be scored (missing critical data).
        """
        truck_id = truck.get("id")
        if truck_id is None:
            return None

        # Get driver assignment
        driver_id = self._get_driver_for_truck(truck_id)

        # Compute each factor (0-100 scale)
        proximity = self._score_proximity(load, truck)
        profit = self._score_profit(load, truck)
        driver = self._score_driver_hours(driver_id, load)
        maintenance = self._score_maintenance(truck_id)
        trailer = self._score_trailer_compatibility(load, truck)
        reliability = self._score_reliability(truck_id, driver_id)
        positioning = self._score_positioning(load, truck)

        # Weighted sum
        w = DEFAULT_MATCHER_WEIGHTS
        total_w = sum(w.values())
        score = (
            w["proximity"] * proximity
            + w["expected_profit"] * profit
            + w["driver_hours"] * driver
            + w["maintenance_health"] * maintenance
            + w["trailer_compatibility"] * trailer
            + w["historical_reliability"] * reliability
            + w["positioning"] * positioning
        ) / max(total_w, 1)

        # Round to integer, clamp to [0, 100]
        score = min(max(round(score), 0.0), 100.0)

        # Build reasons from top contributing factors
        contributions = [
            (proximity, "freight.match_reason.closest_vehicle"),
            (profit, "freight.match_reason.highest_profit"),
            (driver, "freight.match_reason.driver_hours"),
            (maintenance, "freight.match_reason.maintenance_health"),
            (trailer, "freight.match_reason.trailer_compatible"),
            (reliability, "freight.match_reason.reliable_history"),
            (positioning, "freight.match_reason.good_positioning"),
        ]
        contributions.sort(key=lambda c: c[0], reverse=True)
        reasons = [key for val, key in contributions[:3] if val > 50]

        # If no reasons would mention compatibility issues
        if trailer < 30:
            reasons.append("freight.compat.trailer_mismatch")
        if driver < 30 and driver_id is not None:
            reasons.append("freight.compat.driver_hours_insufficient")

        # Estimate deadhead and profit
        deadhead_km = self._estimate_deadhead(load, truck)
        # Compute actual expected profit: revenue minus estimated costs
        estimated_fuel = (load.distance_km or 500) * 0.35
        estimated_tolls = (load.distance_km or 500) * 0.08
        estimated_salary = (load.distance_km or 500) * 0.12
        actual_profit = float(load.price.amount) - (estimated_fuel + estimated_tolls + estimated_salary)
        expected_profit = Money(
            amount=actual_profit,
            currency=load.price.currency,
        )

        return TruckMatchScore(
            vehicle_id=truck_id,
            driver_id=driver_id,
            score=float(score),
            rank=0,  # assigned after sorting
            reasons=reasons,
            distance_to_pickup_km=proximity * 10.0,  # rough: score/100 * max_distance
            expected_deadhead_km=deadhead_km,
            expected_profit=expected_profit,
            driver_hours_remaining=self._get_driver_hours(driver_id) if driver_id else None,
            maintenance_status=self._get_maintenance_status(truck_id),
            trailer_compatible=trailer >= 50,
        )

    # ── Factor scorers (each returns 0-100) ─────────────────────────────

    def _score_proximity(self, load: LoadSearchResult, truck: dict) -> float:
        """How close is the truck to the load's pickup location?

        Closer = higher score.  Uses truck's current location vs load origin.
        """
        # Default: assume truck is near pickup (most dispatchers filter by proximity)
        truck_location = truck.get("current_location", "") or truck.get("location", "")
        if not truck_location:
            return 50.0  # neutral — no location data

        # Simple heuristic: same city = high score, different = lower
        load_city = load.origin.split(",")[0].strip().lower() if load.origin else ""
        truck_city = truck_location.split(",")[0].strip().lower()

        if load_city and truck_city == load_city:
            return 100.0  # same city
        elif load_city and truck_city[:3] == load_city[:3]:
            return 75.0  # similar area
        return 40.0  # different location

    def _score_profit(self, load: LoadSearchResult, truck: dict) -> float:
        """Expected profit contribution.

        Higher revenue loads with lower operating costs score higher.
        """
        # Estimate cost based on truck consumption
        consumption = float(truck.get("consumption_l_per_100km", 30) or 30)
        distance = load.distance_km or 500
        fuel_liters = (distance / 100.0) * consumption
        fuel_cost_est = fuel_liters * 1.50  # ~1.50 EUR/L
        total_cost_est = fuel_cost_est + (distance * 0.15)  # tolls + salary

        price_amount = float(load.price.amount)
        profit_est = price_amount - total_cost_est
        if profit_est <= 0:
            return 10.0  # unprofitable

        # Scale: profit/price ratio mapped to 0-100
        margin = profit_est / price_amount
        return min(margin * 150.0, 100.0)  # 66% margin = 100 score

    def _score_driver_hours(self, driver_id: Optional[int], load: LoadSearchResult) -> float:
        """Driver remaining hours vs. estimated trip duration."""
        hours = self._get_driver_hours(driver_id)
        if hours is None or hours <= 0:
            return 50.0  # neutral — no driver assigned or no data

        distance = load.distance_km or 500
        est_duration = distance / 60.0  # ~60 km/h average

        if hours >= est_duration * 1.5:
            return 100.0  # plenty of hours
        elif hours >= est_duration:
            return 70.0  # just enough
        elif hours >= est_duration * 0.5:
            return 30.0  # not enough without rest
        return 10.0  # insufficient

    def _score_maintenance(self, truck_id: int) -> float:
        """Fleet health score — higher = better maintained."""
        health = self._get_health_score(truck_id)
        if health is None:
            return 50.0  # neutral
        # Health scores are typically 0-100 already
        return min(max(float(health), 0.0), 100.0)

    def _score_trailer_compatibility(
        self, load: LoadSearchResult, truck: dict
    ) -> float:
        """Does the truck's trailer type match the load requirements?"""
        load_trailer = load.trailer_type.lower() if load.trailer_type else "standard"
        truck_trailer = (truck.get("trailer_type", "") or "").lower()

        if not truck_trailer:
            return 50.0  # unknown — neutral

        if truck_trailer == load_trailer:
            score = 100.0
        elif truck_trailer in ("universal", "any"):
            score = 85.0
        else:
            score = 10.0  # mismatch

        # ADR penalty
        if load.adr and not truck.get("adr_certified", False):
            score *= 0.5

        return score

    def _score_reliability(
        self, truck_id: int, driver_id: Optional[int] = None
    ) -> float:
        """Historical reliability — on-time delivery record."""
        # Default: neutral.  In production, this queries trip history
        # for on-time percentage.  For now, use maintenance health as proxy.
        health = self._score_maintenance(truck_id)
        return health * 0.9  # slightly lower than raw maintenance

    def _score_positioning(
        self, load: LoadSearchResult, truck: dict
    ) -> float:
        """Positioning-for-future-work — does this dispatch leave the truck
        somewhere with good onward-load prospects?"""
        destination = load.destination.lower() if load.destination else ""
        # Heuristic: major logistics hubs = good positioning
        hubs = ["berlin", "bucharest", "warsaw", "budapest", "vienna", "prague",
                "paris", "milan", "madrid", "frankfurt", "munich", "rotterdam"]
        for hub in hubs:
            if hub in destination:
                return 90.0
        return 50.0  # neutral

    # ── Data access helpers (delegate to existing repos/services) ──────

    def _get_available_trucks(self, company_id: int) -> list[dict]:
        """Get all trucks for a company."""
        try:
            from repositories.fleet_repository import FleetRepository
            # Ensure company scoping matches the requested company
            original = getattr(self.db, "user_company_id", None)
            try:
                self.db.user_company_id = company_id
                repo = FleetRepository(self.db)
                return repo.get_all(limit=500)
            finally:
                if original is not None:
                    self.db.user_company_id = original
        except Exception as e:
            logger.warning("Could not fetch trucks: %s", e)
            return []

    def _get_driver_for_truck(self, truck_id: int) -> Optional[int]:
        """Get the driver currently assigned to a truck."""
        try:
            from repositories.driver_truck_assignment_repository import (
                DriverTruckAssignmentRepository,
            )
            repo = DriverTruckAssignmentRepository(self.db)
            return repo.get_driver_id_for_truck(truck_id)
        except Exception:
            return None

    def _get_driver_hours(self, driver_id: Optional[int]) -> Optional[float]:
        """Get remaining driving hours for a driver."""
        if driver_id is None:
            return None
        try:
            from repositories.driver_repository import DriverRepository
            repo = DriverRepository(self.db)
            driver = repo.get_by_id(driver_id)
            if driver:
                return float(driver.get("hours_remaining", 0) or 0)
        except Exception:
            pass
        return None

    def _get_health_score(self, truck_id: int) -> Optional[float]:
        """Get fleet health score for a truck."""
        try:
            from repositories.fleet_repository import FleetRepository
            repo = FleetRepository(self.db)
            health = repo.get_truck_health(truck_id)
            if health:
                return float(health.get("score", health.get("health_score", 50)) or 50)
        except Exception:
            pass
        return None

    def _get_maintenance_status(self, truck_id: int) -> str:
        """Get human-readable maintenance status."""
        score = self._get_health_score(truck_id)
        if score is None:
            return "unknown"
        if score >= 80:
            return "good"
        if score >= 50:
            return "fair"
        return "needs_attention"

    def _estimate_deadhead(self, load: LoadSearchResult, truck: dict) -> float:
        """Estimate deadhead distance: truck location → load pickup."""
        # Simple: if same city, 0 km; otherwise use load distance as rough proxy
        truck_loc = (truck.get("current_location", "") or "").lower()
        load_origin = load.origin.lower() if load.origin else ""

        if truck_loc and load_origin:
            tc = truck_loc.split(",")[0].strip()
            lo = load_origin.split(",")[0].strip()
            if tc == lo:
                return 0.0
        distance = load.distance_km if load.distance_km is not None and load.distance_km >= 0 else 500
        return distance * 0.3  # rough estimate
