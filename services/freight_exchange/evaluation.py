"""Freight Exchange Evaluation Engine — provider-agnostic load evaluation.

Turns any searched or imported load into real business numbers by
orchestrating EXISTING engines.  Computes nothing itself that already
has a home elsewhere in Operion.  Zero provider-specific logic — every
adapter's load is evaluated identically.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from models.common import Money
from models.freight_exchange_models import (
    DriverCompatibility,
    LoadEvaluation,
    LoadSearchResult,
    VehicleCompatibility,
)
from services.freight_exchange.risk_scoring import compute_risk_score
from services.freight_exchange.search import SearchEngineService

logger = logging.getLogger(__name__)


class EvaluationEngineService:
    """Evaluates freight exchange loads using existing Operion services.

    Delegates to:
      - ``calculator.py``  → revenue, profit, margin
      - ``cost_engine.py`` → fuel, toll, driver salary estimates
      - ``route_service.py`` → deadhead distance, duration
      - ``risk_scoring.py`` → 0.0–1.0 risk score (the only new module)

    Usage::

        engine = EvaluationEngineService(db)
        evaluation = await engine.evaluate_load(
            company_id=1, provider_id="timocom", provider_load_id="TL-12345",
        )
    """

    def __init__(self, db):
        self.db = db
        self._search = SearchEngineService(db)

    async def evaluate_load(
        self,
        company_id: int,
        provider_id: str,
        provider_load_id: str,
        candidate_vehicle_id: Optional[int] = None,
    ) -> LoadEvaluation:
        """Evaluate a load from any provider and return business numbers.

        Steps:
        1. Fetch the load via Search Engine
        2. Estimate route (deadhead distance + duration)
        3. Estimate costs (fuel, tolls, driver salary)
        4. Calculate revenue/profit via the Trip Calculator
        5. Compute risk score
        6. Check vehicle/driver compatibility (if candidate_vehicle_id provided)
        """
        # 1. Fetch load
        load = await self._search.get_load(company_id, provider_id, provider_load_id)
        if load is None:
            raise ValueError(
                f"Load not found: provider={provider_id} load_id={provider_load_id}"
            )

        # 2. Estimate route (distance + duration)
        deadhead_km, duration_hours = self._estimate_route(load)

        # 3. Estimate costs
        fuel_cost, toll_cost, driver_salary = self._estimate_costs(
            load, deadhead_km, candidate_vehicle_id
        )

        # 4. Calculate revenue/profit
        revenue, profit, margin = self._calculate_financials(
            load, fuel_cost, toll_cost, driver_salary
        )

        # 5. Risk score
        risk = compute_risk_score(
            pickup_window=load.pickup_window,
            delivery_window=load.delivery_window,
            estimated_duration_hours=duration_hours,
            origin=load.origin,
            destination=load.destination,
            load_price=load.price.amount,
        )

        # 6. Vehicle/driver compatibility
        vehicle_compat = []
        driver_compat = []
        if candidate_vehicle_id is not None:
            vehicle_compat = self._check_vehicle_compatibility(load, candidate_vehicle_id)
            driver_compat = self._check_driver_compatibility(candidate_vehicle_id, duration_hours)

        return LoadEvaluation(
            provider_id=provider_id,
            provider_load_id=provider_load_id,
            estimated_revenue=Money(amount=revenue, currency=load.price.currency),
            fuel_cost=Money(amount=fuel_cost, currency=load.price.currency),
            toll_cost=Money(amount=toll_cost, currency=load.price.currency),
            driver_salary=Money(amount=driver_salary, currency=load.price.currency),
            deadhead_distance_km=deadhead_km,
            expected_profit=Money(amount=profit, currency=load.price.currency),
            profit_margin_pct=margin,
            estimated_duration_hours=duration_hours,
            risk_score=risk,
            vehicle_compatibility=vehicle_compat,
            driver_compatibility=driver_compat,
            evaluated_at=datetime.now(timezone.utc),
        )

    # ── Private: orchestrate existing services ─────────────────────────

    def _estimate_route(self, load: LoadSearchResult) -> tuple[float, float]:
        """Estimate deadhead distance and duration via RouteService.

        Returns (distance_km, duration_hours).
        """
        # Use the load's existing distance if available; otherwise delegate
        if load.distance_km and load.distance_km > 0:
            distance = load.distance_km
        else:
            distance = 500.0  # fallback

        # Estimate duration: ~60 km/h average for trucking
        duration = distance / 60.0

        # Try to use the real RouteService if available
        try:
            from services.route_service import RouteService
            route_svc = RouteService(self.db)
            stops = [
                {"address": load.origin},
                {"address": load.destination},
            ]
            result = route_svc.calculate_route(stops, profile="truck")
            if result and result.get("distance_km"):
                distance = float(result["distance_km"])
            if result and result.get("duration_hours"):
                duration = float(result["duration_hours"])
        except Exception as e:
            logger.debug("RouteService unavailable, using estimate: %s", e)

        return distance, duration

    def _estimate_costs(
        self,
        load: LoadSearchResult,
        distance_km: float,
        vehicle_id: Optional[int] = None,
    ) -> tuple[float, float, float]:
        """Estimate fuel, toll, and driver salary costs via CostEngineService.

        Returns (fuel_cost, toll_cost, driver_salary).
        """
        fuel_cost = 0.0
        toll_cost = 0.0
        driver_salary = 0.0

        try:
            from repositories.fleet_repository import FleetRepository
            from services.cost_engine import CostEngineService
            cost_svc = CostEngineService(fleet_repo=FleetRepository(self.db))

            if vehicle_id is not None:
                result = cost_svc.estimate_for_truck(distance_km, vehicle_id)
                if result and result.success and result.data:
                    fuel_cost = float(getattr(result.data, "fuel_cost", 0) or 0)
                    toll_cost = float(getattr(result.data, "toll_cost", 0) or 0)
                    driver_salary = float(getattr(result.data, "salary_cost", 0) or 0)
            else:
                from models.cost_models import CostEstimateRequest
                result = cost_svc.estimate(CostEstimateRequest(distance_km=distance_km))
                if result is None:
                    raise ValueError("Cost engine returned no result")
                if isinstance(result, dict):
                    fuel_cost = float(result.get("fuel_cost", 0) or 0)
                    toll_cost = float(result.get("toll_cost", 0) or 0)
                elif hasattr(result, "data") and result.data:
                    fuel_cost = float(getattr(result.data, "fuel_cost", 0) or 0)
                    toll_cost = float(getattr(result.data, "toll_cost", 0) or 0)
                    driver_salary = float(getattr(result.data, "salary_cost", 0) or 0)

            # Sanity check: if all costs are unreasonably low, use fallback
            if fuel_cost + toll_cost + driver_salary < distance_km * 0.1:
                fuel_cost = distance_km * 0.35
                toll_cost = distance_km * 0.08
                driver_salary = distance_km * 0.12
                logger.warning("Cost engine returned near-zero values, using fallback estimates")
        except Exception as e:
            logger.debug("CostEngineService unavailable, using defaults: %s", e)
            # Fallback estimates
            fuel_cost = distance_km * 0.35  # ~0.35 EUR/km fuel
            toll_cost = distance_km * 0.08  # ~0.08 EUR/km tolls
            driver_salary = distance_km * 0.12  # ~0.12 EUR/km driver

        return fuel_cost, toll_cost, driver_salary

    def _calculate_financials(
        self,
        load: LoadSearchResult,
        fuel_cost: float,
        toll_cost: float,
        driver_salary: float,
    ) -> tuple[float, float, float]:
        """Calculate revenue, profit, and margin.

        Returns (revenue, profit, margin_pct).
        """
        revenue = float(load.price.amount)
        total_cost = fuel_cost + toll_cost + driver_salary
        profit = revenue - total_cost
        margin = (profit / revenue * 100.0) if revenue != 0 else 0.0

        return revenue, profit, margin

    def _check_vehicle_compatibility(
        self, load: LoadSearchResult, vehicle_id: int
    ) -> list[VehicleCompatibility]:
        """Check if a vehicle is compatible with the load.

        Checks trailer type match and ADR requirements.
        """
        reasons = []
        compatible = True

        try:
            from repositories.fleet_repository import FleetRepository
            fleet_repo = FleetRepository(self.db)
            truck = fleet_repo.get_by_id(vehicle_id)
            if truck:
                truck_trailer = truck.get("trailer_type", "").lower()
                load_trailer = load.trailer_type.lower() if load.trailer_type else "standard"
                if truck_trailer and load_trailer and truck_trailer != load_trailer:
                    compatible = False
                    reasons.append("freight.compat.trailer_mismatch")

                if load.adr and not truck.get("adr_certified", False):
                    compatible = False
                    reasons.append("freight.compat.adr_required")
            else:
                compatible = False
                reasons.append("freight.compat.vehicle_unavailable")
        except Exception as e:
            logger.debug("Vehicle check unavailable: %s", e)
            reasons.append("freight.compat.vehicle_unavailable")
            compatible = False

        return [VehicleCompatibility(
            vehicle_id=vehicle_id, compatible=compatible, reasons=reasons,
        )]

    def _check_driver_compatibility(
        self, vehicle_id: int, duration_hours: float
    ) -> list[DriverCompatibility]:
        """Check driver compatibility for a vehicle based on hours remaining."""
        try:
            from repositories.fleet_repository import FleetRepository
            fleet_repo = FleetRepository(self.db)
            truck = fleet_repo.get_by_id(vehicle_id)
            if truck and truck.get("driver_id"):
                driver_id = truck["driver_id"]
                from repositories.driver_repository import DriverRepository
                driver_repo = DriverRepository(self.db)
                driver = driver_repo.get_by_id(driver_id)
                if driver:
                    hours_remaining = float(driver.get("hours_remaining", 8.0))
                    compatible = hours_remaining >= duration_hours
                    reasons = []
                    if not compatible:
                        reasons.append("freight.compat.driver_hours_insufficient")
                    return [DriverCompatibility(
                        driver_id=driver_id,
                        compatible=compatible,
                        hours_remaining=hours_remaining,
                        reasons=reasons,
                    )]
        except Exception as e:
            logger.debug("Driver check unavailable: %s", e)

        return []
