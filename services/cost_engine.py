import logging
import warnings
from typing import Optional

from config import Config
from models.common import ErrorDetail, ServiceResult
from models.cost_models import (
    CostBreakdown,
    CostEstimateOperationResult,
    CostEstimateRequest,
    CostEstimateResult,
)
from repositories.fleet_repository import FleetRepository
from services.fuel_price_service import FuelPriceService

logger = logging.getLogger("cost_engine")


class CostEngineService:
    COUNTRY_FACTORS = {
        'RO': 1.0,
        'DE': 1.2,
        'FR': 1.3,
        'IT': 1.25,
        'DEFAULT': 1.0
    }

    ROAD_CLASS_FACTOR = {
        'motorway': 1.0,
        'trunk': 1.0,
        'primary': 0.8,
        'secondary': 0.5,
        'tertiary': 0.2,
        'default': 0.3
    }

    def __init__(
        self,
        fuel_price_eur_per_liter: Optional[float] = None,
        country_code: str = 'DEFAULT',
        fleet_repo: Optional[FleetRepository] = None,
    ):
        if fuel_price_eur_per_liter is not None:
            self._fixed_fuel_price = fuel_price_eur_per_liter
        else:
            self._fixed_fuel_price = None
        self._default_country = country_code
        self._fleet_repo = fleet_repo  # None is OK; truck lookup is optional

    @property
    def fuel_price(self) -> float:
        if self._fixed_fuel_price is not None:
            return self._fixed_fuel_price
        fuel_service = FuelPriceService()
        return fuel_service.get_price(self._default_country)

    # ── Primary typed interface (with backward-compat dispatch) ─────────

    def estimate(self, *args, **kwargs):
        """Estimate trip costs.

        .. code-block:: python

            # New typed interface (recommended):
            result: CostEstimateOperationResult = service.estimate(
                CostEstimateRequest(distance_km=1000, ...)
            )

            # Legacy positional/ keyword interface (deprecated):
            result: dict = service.estimate(1000.0, {"fuel_consumption": 30}, ...)
            result: dict = service.estimate(distance_km=1000.0, truck={...}, ...)
        """
        # ── New typed interface: single positional CostEstimateRequest ──
        if (
            len(args) == 1
            and isinstance(args[0], CostEstimateRequest)
            and not kwargs
        ):
            return self._estimate_typed(args[0])

        # ── Legacy path with deprecation warning ──
        warnings.warn(
            "estimate(distance_km, truck, ...) is deprecated — "
            "use estimate(request=CostEstimateRequest(...)) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        distance_km = args[0] if len(args) > 0 else kwargs.get('distance_km')
        truck = args[1] if len(args) > 1 else kwargs.get('truck', {})
        route_details = args[2] if len(args) > 2 else kwargs.get('route_details')
        country_code = args[3] if len(args) > 3 else kwargs.get('country_code', 'DEFAULT')
        return self._estimate_legacy(distance_km, truck or {}, route_details, country_code)

    # ── New typed implementation ─────────────────────────────────────────

    def _estimate_typed(self, request: CostEstimateRequest) -> CostEstimateOperationResult:
        """Typed cost estimation using a Pydantic request model."""
        logger.info("Cost estimation request: %s", request.model_dump())
        try:
            consumption = self._resolve_consumption(request)
            fuel_price = self._resolve_fuel_price(request)
            truck_info = self._resolve_truck_info(request)

            fuel_cost = round(request.distance_km * consumption / 100.0 * fuel_price, 2)
            driver_cost = round(request.driver_daily_rate * request.days, 2)
            extra_costs_total = sum(request.extra_costs.values())
            total_cost = round(
                fuel_cost + request.toll_cost_eur + driver_cost + extra_costs_total, 2
            )
            cost_per_km = round(total_cost / request.distance_km, 4)

            breakdown = CostBreakdown(
                fuel_cost=fuel_cost,
                toll_cost=request.toll_cost_eur,
                driver_cost=driver_cost,
                extra_costs=request.extra_costs,
                total_cost=total_cost,
                cost_per_km=cost_per_km,
                currency=request.currency,
            )

            result = CostEstimateResult(
                distance_km=request.distance_km,
                days=request.days,
                breakdown=breakdown,
                truck_info=truck_info,
            )

            logger.info("Cost estimation result: %s", result.model_dump())
            return ServiceResult(success=True, data=result)

        except Exception as exc:
            logger.exception("Cost estimation failed")
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="ESTIMATION_ERROR")],
            )

    # ── Legacy positional implementation (deprecated) ────────────────────

    def _estimate_legacy(
        self,
        distance_km: float,
        truck: dict,
        route_details: Optional[dict] = None,
        country_code: str = 'DEFAULT',
    ) -> dict:
        """Original positional-argument implementation (kept for backward compat)."""
        if distance_km is None:
            return {
                'fuel_liters': 0.0,
                'fuel_cost': 0.0,
                'toll_cost': 0.0,
                'total_cost': 0.0,
            }
        consumption = truck.get('fuel_consumption_l_per_100km') or truck.get('fuel_consumption') or 34.0
        fuel_liters = (distance_km / 100.0) * float(consumption)
        fuel_cost = fuel_liters * self.fuel_price

        country_factor = self.COUNTRY_FACTORS.get(country_code, self.COUNTRY_FACTORS['DEFAULT'])
        avg_road_factor = 0.5
        if route_details and 'road_class' in route_details:
            road_class_str = route_details.get('road_class', 'default')
            avg_road_factor = self.ROAD_CLASS_FACTOR.get(road_class_str, 0.5)

        toll_rate = Config.DEFAULT_TOLL_RATE
        toll_cost = distance_km * toll_rate * country_factor * avg_road_factor

        total = fuel_cost + toll_cost

        return {
            'fuel_liters': round(fuel_liters, 2),
            'fuel_cost': round(fuel_cost, 2),
            'toll_cost': round(toll_cost, 2),
            'total_cost': round(total, 2),
        }

    # ── Convenience: estimate for a specific truck by ID ─────────────────

    def estimate_for_truck(self, distance_km: float, truck_id: int) -> CostEstimateOperationResult:
        """Fetch truck consumption from the database and estimate costs.

        Parameters
        ----------
        distance_km : float
            Route distance in kilometres.
        truck_id : int
            ID of the truck to look up in the fleet repository.

        Returns
        -------
        CostEstimateOperationResult
        """
        logger.info("estimate_for_truck(distance_km=%s, truck_id=%s)", distance_km, truck_id)
        try:
            if self._fleet_repo is None:
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(
                        message="Fleet repository not available — cannot look up truck",
                        code="FLEET_REPO_MISSING",
                    )],
                )
            truck = self._fleet_repo.get_by_id(truck_id)
            if not truck:
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(
                        message=f"Truck {truck_id} not found",
                        code="TRUCK_NOT_FOUND",
                    )],
                )
            request = CostEstimateRequest(
                distance_km=distance_km,
                truck_id=truck_id,
                consumption_l_per_100km=truck.get('fuel_consumption'),
            )
            return self.estimate(request)
        except Exception as exc:
            logger.exception("estimate_for_truck failed")
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="ESTIMATE_TRUCK_ERROR")],
            )

    # ── Internal helpers ─────────────────────────────────────────────────

    def _resolve_consumption(self, request: CostEstimateRequest) -> float:
        """Resolve fuel consumption (L/100km) from request or truck DB lookup."""
        if request.consumption_l_per_100km is not None:
            return request.consumption_l_per_100km
        if request.truck_id is not None and self._fleet_repo is not None:
            truck = self._fleet_repo.get_by_id(request.truck_id)
            if truck and truck.get('fuel_consumption'):
                return float(truck['fuel_consumption'])
        return 34.0  # fallback default

    def _resolve_fuel_price(self, request: CostEstimateRequest) -> float:
        """Fuel price from request or service default."""
        if request.fuel_price_per_liter is not None:
            return request.fuel_price_per_liter
        return self.fuel_price

    def _resolve_truck_info(self, request: CostEstimateRequest) -> str:
        """Build a human-readable truck info string if truck_id is given."""
        if request.truck_id is None or self._fleet_repo is None:
            return ""
        truck = self._fleet_repo.get_by_id(request.truck_id)
        if not truck:
            return ""
        parts = [
            str(truck.get('manufacturer', '')),
            str(truck.get('model', '')),
        ]
        plate = truck.get('plate_number')
        if plate:
            parts.append(f"({plate})")
        return " ".join(p for p in parts if p).strip()
