"""Route Planner controller — business logic without Tk widgets."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.constraint_engine import TruckConstraintEngine
from services.cost_engine import CostEngineService
from services.country_avoidance import CountryAvoidanceManager
from services.route_compliance import RouteComplianceAnalyzer
from services.route_history_service import RouteHistoryRecord
from services.route_persistence import RoutePersistenceService
from services.route_profiles import gh_profile_for_ui_label
from services.i18n import t
from services.route_result_presenter import (
    extract_route_from_result,
    format_success_info,
    parse_error_message,
)
from services.route_runner import RouteRunner
from services.route_service import RouteService
from services.trip_context import TripContextService
from services.calculator import TripCalculator
from services.operations.event_bus import EventBus, TRIP_CREATED, ROUTE_ASSIGNED
from repositories.route_repository import RouteRepository
from repositories.fleet_repository import FleetRepository
from repositories.driver_repository import DriverRepository
from utils.perf_log import perf_timer


@dataclass
class RouteCalculationContext:
    truck: Any
    profile: str
    stops_state: List[Dict[str, Any]]
    excluded_countries: List[str]


@dataclass
class ProcessedRouteResult:
    route: Dict[str, Any]
    cost_info: Dict[str, Any]
    info_text: str
    compliance: Any
    truck_obj: Dict[str, Any]


class RoutePlannerController:
    """Orchestrates routing, costing, persistence, and trip context sync."""

    def __init__(self, db) -> None:
        self.route_service = RouteService(db)
        self.country_avoidance = CountryAvoidanceManager()
        self.cost_engine = CostEngineService()
        self.trip_context = TripContextService()
        self.compliance = RouteComplianceAnalyzer()
        self._runner = RouteRunner()
        self._persistence: Optional[RoutePersistenceService] = None
        self._db = db

    @property
    def geocode_cache(self):
        return getattr(self.route_service, "_geocode_cache", None)

    def bind_persistence(self, persistence: RoutePersistenceService) -> None:
        self._persistence = persistence

    def get_excluded_countries(self) -> List[str]:
        codes = self.country_avoidance.get_selected()
        self.country_avoidance.set_selected(codes)
        return codes

    def set_excluded_countries(self, codes: List[str]) -> None:
        self.country_avoidance.set_selected(codes)

    def validate_calculation_input(
        self,
        *,
        truck_id: str,
        trucks_map: Dict[str, Any],
        profile_label: str,
        stops_state: List[Dict[str, Any]],
        row_addresses: List[Tuple[int, str]],
    ) -> Tuple[Optional[RouteCalculationContext], Optional[str]]:
        if not truck_id:
            return None, f"⚠️ {t('result.controller_select_truck')}"
        truck = trucks_map.get(truck_id)
        if not truck:
            return None, f"⚠️ {t('result.controller_invalid_truck')}"
        for idx, address in row_addresses:
            if not (address or "").strip():
                return None, f"⚠️ {t('result.controller_empty_stop').format(idx + 1)}"
            if 0 <= idx < len(stops_state):
                stops_state[idx]["address"] = address.strip()
        if len(stops_state) < 2:
            return None, f"⚠️ {t('result.controller_need_2_stops')}"
        profile = gh_profile_for_ui_label(profile_label)
        return RouteCalculationContext(
            truck=truck,
            profile=profile,
            stops_state=stops_state,
            excluded_countries=self.get_excluded_countries(),
        ), None

    def start_calculation(
        self,
        ctx: RouteCalculationContext,
        callback: Callable[[Any], None],
    ) -> None:
        with perf_timer("route_calculation_async_start"):
            self._runner.run_route_async(
                route_service=self.route_service,
                stops_state=ctx.stops_state,
                truck=ctx.truck,
                profile=ctx.profile,
                callback=callback,
                geocode_cache=self.geocode_cache,
                avoid_countries=ctx.excluded_countries,
            )

    def cancel_calculation(self) -> None:
        self._runner.cancel()

    def process_calculation_result(
        self,
        result: Any,
        ctx: RouteCalculationContext,
        stop_addresses: Dict[str, str],
    ) -> Tuple[Optional[ProcessedRouteResult], Optional[str]]:
        err = parse_error_message(result) if isinstance(result, dict) else None
        if err:
            return None, err[0]

        with perf_timer("route_result_process"):
            route = extract_route_from_result(result)
            if not route:
                return None, f"❌ {t('result.controller_calc_failed')}"

            distance = float(route.get("distance_km") or 0)
            if distance <= 0:
                return None, f"❌ {t('result.controller_invalid_distance')}"

            cost_info = self.estimate_cost(ctx.truck, distance)
            truck_obj = self._truck_cost_payload(ctx.truck)
            self._sync_trip_context(route, truck_obj, cost_info, ctx.profile)

            info_text = format_success_info(route, cost_info, len(ctx.stops_state))
            compliance = self.compliance.analyze(route)

            if self._persistence:
                try:
                    self._persistence.save_calculated_route(
                        route=route,
                        truck=ctx.truck,
                        profile=ctx.profile,
                        stops_state=ctx.stops_state,
                        stop_addresses=stop_addresses,
                        excluded_countries=ctx.excluded_countries,
                        cost_info=cost_info,
                    )
                except Exception:
                    import traceback
                    traceback.print_exc()

            return ProcessedRouteResult(
                route=route,
                cost_info=cost_info,
                info_text=info_text,
                compliance=compliance,
                truck_obj=truck_obj,
            ), None

    def estimate_cost(self, truck: Any, distance_km: float) -> Dict[str, Any]:
        try:
            payload = self._truck_cost_payload(truck)
            return self.cost_engine.estimate(distance_km, payload)
        except Exception:
            return {}

    @staticmethod
    def _truck_cost_payload(truck: Any) -> Dict[str, Any]:
        return {
            "id": TruckConstraintEngine._get_truck_value(truck, "id"),
            "name": TruckConstraintEngine._get_truck_value(truck, "plate_number"),
            "fuel_consumption_l_per_100km": (
                TruckConstraintEngine._get_truck_value(truck, "fuel_consumption")
                or TruckConstraintEngine._get_truck_value(truck, "fuel_consumption_l_per_100km")
            ),
        }

    def _sync_trip_context(
        self,
        route: Dict[str, Any],
        truck_obj: Dict[str, Any],
        cost_info: Dict[str, Any],
        profile: str,
    ) -> None:
        route_id = route.get("history_id")
        self.trip_context.set_active_trip_info(
            distance_km=route.get("distance_km"),
            duration_min=route.get("duration_min"),
            fuel_liters=cost_info.get("fuel_liters"),
            fuel_cost=cost_info.get("fuel_cost"),
            route_history_v2_id=route_id,
        )

    def load_history_record(self, record: RouteHistoryRecord) -> Dict[str, Any]:
        """Return planner state patch: stops, profile label key, truck_id, route dict."""
        from services.route_profiles import ui_label_for_profile

        return {
            "stops": RoutePersistenceService.normalize_history_stops(record),
            "profile_label": ui_label_for_profile(record.profile or ""),
            "truck_id": str(record.truck_id) if record.truck_id else None,
            "excluded_countries": list(record.excluded_countries or []),
            "route": RoutePersistenceService.record_to_planner_route(record),
        }

    def export_route_metadata(self, route: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
        if not route:
            return None, f"⚠️ {t('result.controller_no_metadata')}"
        try:
            import datetime
            import json

            ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            path = f"reports/route_metadata_{ts}.json"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(route, fh, ensure_ascii=False, indent=2)
            return path, None
        except Exception as exc:
            return None, f"❌ {t('result.generic_error').format('Export', str(exc))}"


    def create_trip_from_route(
        self,
        route_id: int,
        truck_id: str,
        driver_id: int = None,
        client_name: str = '',
        client_id: int = None,
        start_date: str = None,
        currency: str = 'EUR',
    ) -> int:
        import logging
        from datetime import datetime, timedelta
        from services.fuel_price_service import FuelPriceService
        _log = logging.getLogger(__name__)

        from services.trip_service import TripService
        route_repo = RouteRepository(self._db)
        fleet_repo = FleetRepository(self._db)
        driver_repo = DriverRepository(self._db)
        trip_service = TripService(self._db)
        calculator = TripCalculator()

        route = route_repo.get_by_id(route_id)
        if not route:
            raise ValueError(f'Route {route_id} not found')

        truck = fleet_repo.get_by_id(int(truck_id))
        if not truck:
            raise ValueError(f'Truck {truck_id} not found')
        truck_plate = truck.get('plate_number', '')
        truck_consumption = truck.get('fuel_consumption') or 34.0

        driver_name = ''
        if driver_id:
            driver = driver_repo.get_by_id(driver_id)
            if driver:
                driver_name = driver.get('name', '')

        if not client_id and client_name:
            from services.client_service import ClientService
            client_id = ClientService(self._db).get_or_create(client_name)

        distance_km = float(route.get('total_distance_km') or 0)
        start_dt = datetime.now()
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%d/%m/%Y')
            except ValueError:
                pass

        duration_min = int(route.get('duration_min') or 0)
        end_dt = start_dt + timedelta(minutes=duration_min)

        fuel_price = FuelPriceService().get_price('DEFAULT', currency)
        fuel_liters = (distance_km / 100.0) * truck_consumption
        fuel_cost = fuel_liters * fuel_price

        result = calculator.calculate(
            km=distance_km,
            price_eur=0,
            fuel_price=fuel_price,
            days=max(1, duration_min // 1440 or 1),
            consum_litri=truck_consumption,
            extra_in=0,
            sal_in=0,
            taxa_in=0,
            fuel_cost_override=fuel_cost,
        )

        trip_data = {
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'truck_number': truck_plate,
            'truck_id': int(truck_id),
            'driver_name': driver_name,
            'driver_id': driver_id,
            'client_name': client_name,
            'client_id': client_id,
            'distance_km': distance_km,
            'total_price_eur': 0,
            'rate_per_km': result.rate_per_km if result else 0,
            'gross_per_km': result.gross_per_km if result else 0,
            'net_profit': result.net_profit if result else 0,
            'start_date': start_dt.strftime('%Y-%m-%d'),
            'end_date': end_dt.strftime('%Y-%m-%d'),
            'fuel_cost': fuel_cost,
            'toll_cost': 0,
            'salary_cost': 0,
            'extra_costs': 0,
            'currency': currency,
            'status': 'Planned',
            'route_history_v2_id': route_id,
            'truck_consumption_l_per_100km': truck_consumption,
        }

        new_id = trip_service.add(trip_data)

        EventBus().publish(ROUTE_ASSIGNED, {
            'route_id': route_id,
            'trip_id': new_id,
            'truck_id': truck_id,
        })

        _log.info('Trip %d created from route %d (truck: %s)', new_id, route_id, truck_plate)
        return new_id
