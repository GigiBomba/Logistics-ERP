from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from pydantic import ValidationError

from config import Config
from models.calculator_models import (
    CalculationOperationResult,
    CalculationRequest,
    TripCalculationResult,
)
from models.common import ErrorDetail
from repositories.fleet_repository import FleetRepository

logger = logging.getLogger(__name__)


@dataclass
class TripResult:
    net_profit: float
    fuel_cost: float
    toll_cost: float
    salary_cost: float
    extra_costs: float
    rate_per_km: float
    gross_per_km: float
    margin_percent: float


class TripCalculator:
    # ── Raw (backward-compatible) API ──────────────────────────────

    @staticmethod
    def calculate_raw(
        km,
        price_eur,
        fuel_price,
        days,
        consum_litri,
        extra_in=None,
        sal_in=0,
        taxa_in=0,
        fuel_cost_override=None,
    ):
        """Backward-compatible raw calculation.

        Returns a ``TripResult`` dataclass.  New code should prefer
        :meth:`calculate` with a typed :class:`CalculationRequest`.
        """
        logger.info(
            "Calculating trip (raw): km=%s, price_eur=%s, fuel_price=%s, days=%s, "
            "consum_litri=%s, extra_in=%s, sal_in=%s, taxa_in=%s, fuel_cost_override=%s",
            km,
            price_eur,
            fuel_price,
            days,
            consum_litri,
            extra_in,
            sal_in,
            taxa_in,
            fuel_cost_override,
        )

        # Validate inputs
        if km <= 0:
            logger.warning("Invalid km value: %s (must be > 0)", km)
        if days <= 0:
            logger.warning("Invalid days value: %s (must be > 0)", days)
        if price_eur < 0:
            logger.warning("Negative price_eur: %s", price_eur)
        if fuel_price < 0:
            logger.warning("Negative fuel_price: %s", fuel_price)
        if consum_litri < 0:
            logger.warning("Negative consum_litri: %s", consum_litri)

        try:
            # 1. Salary
            salary_cost = sal_in if sal_in > 0 else (days * Config.DEFAULT_DRIVER_SALARY)

            # 2. Toll
            toll_cost = taxa_in if taxa_in > 0 else (km * Config.DEFAULT_TOLL_RATE)

            # 3. Extra costs
            if extra_in is not None:
                extra_costs = extra_in
            else:
                extra_costs = round(
                    (km * Config.EXTRA_COST_PER_KM) + (days * Config.EXTRA_COST_PER_DAY), 2
                )

            # 4. Fuel
            if fuel_cost_override is not None and fuel_cost_override > 0:
                fuel_cost = fuel_cost_override
            else:
                fuel_cost = (km / 100) * consum_litri * fuel_price

            # 5. Final calculations
            total_costs = fuel_cost + toll_cost + salary_cost + extra_costs
            net_profit = price_eur - total_costs

            rate_net_km = net_profit / km if km > 0 else 0
            rate_gross_km = price_eur / km if km > 0 else 0
            margin = (net_profit / price_eur * 100) if price_eur > 0 else 0

            result = TripResult(
                net_profit=round(net_profit, 2),
                fuel_cost=round(fuel_cost, 2),
                toll_cost=round(toll_cost, 2),
                salary_cost=round(salary_cost, 2),
                extra_costs=round(extra_costs, 2),
                rate_per_km=round(rate_net_km, 2),
                gross_per_km=round(rate_gross_km, 2),
                margin_percent=round(margin, 1),
            )

            logger.info(
                "Trip calculation result: net_profit=%s, fuel_cost=%s, toll_cost=%s, "
                "salary_cost=%s, extra_costs=%s, rate_per_km=%s, gross_per_km=%s, margin_percent=%s",
                result.net_profit,
                result.fuel_cost,
                result.toll_cost,
                result.salary_cost,
                result.extra_costs,
                result.rate_per_km,
                result.gross_per_km,
                result.margin_percent,
            )
            return result
        except Exception as e:
            logger.error(
                "Error calculating trip: km=%s, price_eur=%s, fuel_price=%s, days=%s, "
                "consum_litri=%s — %s",
                km,
                price_eur,
                fuel_price,
                days,
                consum_litri,
                e,
                exc_info=True,
            )
            raise

    # ── Typed Pydantic API ────────────────────────────────────────

    def calculate(self, request: CalculationRequest) -> CalculationOperationResult:
        """Typed calculation using Pydantic models.

        Accepts a :class:`CalculationRequest` (which validates all inputs via
        Pydantic) and returns a :class:`CalculationOperationResult` wrapping a
        :class:`TripCalculationResult` on success, or error details on failure.
        """
        try:
            logger.info(
                "Calculating trip: km=%s, price_eur=%s, fuel_price=%s, days=%s, "
                "consum_litri=%s, extra_in=%s, sal_in=%s, taxa_in=%s, fuel_cost_override=%s",
                request.km,
                request.price_eur,
                request.fuel_price,
                request.days,
                request.consum_litri,
                request.extra_in,
                request.sal_in,
                request.taxa_in,
                request.fuel_cost_override,
            )

            # 1. Salary (automatic 100€/day if sal_in == 0)
            salary_cost = request.sal_in if request.sal_in > 0 else (
                request.days * Config.DEFAULT_DRIVER_SALARY
            )

            # 2. Toll (automatic 0.22€/km if taxa_in == 0)
            toll_cost = request.taxa_in if request.taxa_in > 0 else (
                request.km * Config.DEFAULT_TOLL_RATE
            )

            # 3. Extra costs (automatic 0.03€/km + 12€/day if extra_in is None)
            if request.extra_in is not None:
                extra_costs = request.extra_in
            else:
                extra_costs = round(
                    (request.km * Config.EXTRA_COST_PER_KM)
                    + (request.days * Config.EXTRA_COST_PER_DAY),
                    2,
                )

            # 4. Fuel consumption & cost
            fuel_consumed_liters = (request.km / 100.0) * request.consum_litri
            if (
                request.fuel_cost_override is not None
                and request.fuel_cost_override > 0
            ):
                fuel_cost = request.fuel_cost_override
            else:
                fuel_cost = fuel_consumed_liters * request.fuel_price

            # 5. Final calculations
            total_costs = fuel_cost + toll_cost + salary_cost + extra_costs
            net_profit = request.price_eur - total_costs

            profit_per_km = net_profit / request.km if request.km > 0 else 0.0
            cost_per_km = total_costs / request.km if request.km > 0 else 0.0
            margin_percent = (
                (net_profit / request.price_eur * 100.0)
                if request.price_eur > 0
                else 0.0
            )

            data = TripCalculationResult(
                km=request.km,
                price_eur=request.price_eur,
                fuel_price=request.fuel_price,
                days=request.days,
                consum_litri=request.consum_litri,
                extra_in=request.extra_in or 0.0,
                sal_in=request.sal_in,
                taxa_in=request.taxa_in,
                total_income=round(request.price_eur, 2),
                fuel_consumed_liters=round(fuel_consumed_liters, 3),
                fuel_cost=round(fuel_cost, 2),
                toll_cost=round(toll_cost, 2),
                salary_cost=round(salary_cost, 2),
                extra_costs=round(extra_costs, 2),
                net_profit=round(net_profit, 2),
                profit_per_km=round(profit_per_km, 2),
                gross_per_km=round(request.price_eur / request.km, 2) if request.km > 0 else 0.0,
                margin_percent=round(margin_percent, 1),
                cost_per_km=round(cost_per_km, 2),
            )

            logger.info(
                "Trip calculation result: net_profit=%s, fuel_cost=%s, "
                "profit_per_km=%s, margin_percent=%s, cost_per_km=%s",
                data.net_profit,
                data.fuel_cost,
                data.profit_per_km,
                data.margin_percent,
                data.cost_per_km,
            )

            return CalculationOperationResult(success=True, data=data)

        except ValidationError as exc:
            errors = [
                ErrorDetail(
                    field=".".join(str(p) for p in err["loc"]),
                    message=err["msg"],
                    code=err["type"],
                )
                for err in exc.errors()
            ]
            logger.warning("Validation error in trip calculation: %s", errors)
            return CalculationOperationResult(success=False, errors=errors)

        except Exception as exc:
            logger.error("Error calculating trip: %s", exc, exc_info=True)
            return CalculationOperationResult(
                success=False,
                errors=[
                    ErrorDetail(message=str(exc), code="CALCULATION_ERROR")
                ],
            )

    # ── Estimate API ──────────────────────────────────────────────

    def calculate_estimate(
        self,
        km: float,
        truck_id: int,
        fleet_repo: FleetRepository,
        fuel_price: Optional[float] = None,
    ) -> CalculationOperationResult:
        """Estimate trip costs using a truck's known fuel consumption.

        Args:
            km: Distance in kilometres.
            truck_id: Database ID of the truck to look up.
            fleet_repo: Repository for accessing truck data.
            fuel_price: Fuel price per litre (defaults to 1.55 if not given).

        Returns:
            A :class:`CalculationOperationResult` with the estimated costs.
            Only cost fields are meaningful — ``price_eur`` is set to 0 so
            the caller can supply a real revenue later.
        """
        truck = fleet_repo.get_by_id(truck_id)
        if not truck:
            return CalculationOperationResult(
                success=False,
                errors=[
                    ErrorDetail(
                        message=f"Truck {truck_id} not found",
                        code="TRUCK_NOT_FOUND",
                    )
                ],
            )

        consumption = truck.get("fuel_consumption")
        if not consumption:
            return CalculationOperationResult(
                success=False,
                errors=[
                    ErrorDetail(
                        message=f"Truck {truck_id} has no fuel consumption data",
                        code="NO_CONSUMPTION_DATA",
                    )
                ],
            )

        request = CalculationRequest(
            km=km,
            price_eur=0.0,
            fuel_price=fuel_price if fuel_price is not None else 1.55,
            days=max(1, round(km / 800)),
            consum_litri=float(consumption),
        )
        return self.calculate(request)
