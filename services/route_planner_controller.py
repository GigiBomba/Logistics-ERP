"""Route Planner controller — business logic without Tk widgets."""
from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable

from repositories.settings_repository import SettingsRepository
from services.constraint_engine import TruckConstraintEngine
from services.cost_engine import CostEngineService
from services.country_avoidance import CountryAvoidanceManager
from services.i18n import t
from services.route_compliance import RouteComplianceAnalyzer
from services.route_history_service import RouteHistoryRecord
from services.route_persistence import RoutePersistenceService
from services.route_profiles import gh_profile_for_ui_label
from services.route_result_presenter import (
    extract_route_from_result,
    format_success_info,
    parse_error_message,
)
from services.route_runner import RouteRunner
from services.route_service import RouteService
from services.trip_context import TripContextService
from utils.perf_log import perf_timer

logger = logging.getLogger(__name__)


@dataclass
class RouteCalculationContext:
    truck: Any
    profile: str
    stops_state: list[dict[str, Any]]
    excluded_countries: list[str]


@dataclass
class ProcessedRouteResult:
    route: dict[str, Any]
    cost_info: dict[str, Any]
    info_text: str
    compliance: Any
    truck_obj: dict[str, Any]


class RoutePlannerController:
    """Orchestrates routing, costing, persistence, and trip context sync."""

    def __init__(self, db) -> None:
        self.route_service = RouteService(db)
        self.country_avoidance = CountryAvoidanceManager()
        self.cost_engine = CostEngineService()
        self.trip_context = TripContextService()
        self.compliance = RouteComplianceAnalyzer()
        self._runner = RouteRunner()
        self._persistence: RoutePersistenceService | None = None
        self._db = db

    @property
    def geocode_cache(self):
        return getattr(self.route_service, "_geocode_cache", None)

    def bind_persistence(self, persistence: RoutePersistenceService) -> None:
        self._persistence = persistence

    def get_excluded_countries(self) -> list[str]:
        return self.country_avoidance.get_selected()

    def set_excluded_countries(self, codes: list[str]) -> None:
        self.country_avoidance.set_selected(codes)

    def validate_calculation_input(
        self,
        *,
        truck_id: str,
        trucks_map: dict[str, Any],
        profile_label: str,
        stops_state: list[dict[str, Any]],
        row_addresses: list[tuple[int, str]],
    ) -> tuple[RouteCalculationContext | None, str | None]:
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

    def commit_route(self, route_id: int, truck_id: str | None = None) -> None:
        if self._persistence:
            self._persistence.commit_route(route_id, truck_id=truck_id)

    def discard_route(self, route_id: int) -> None:
        if self._persistence:
            self._persistence.history.discard_route(route_id)

    def process_calculation_result(
        self,
        result: Any,
        ctx: RouteCalculationContext,
        stop_addresses: dict[str, str],
    ) -> tuple[ProcessedRouteResult | None, str | None]:
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

            info_text = format_success_info(
                route, cost_info, len(ctx.stops_state),
                preferred_currency=_get_preferred_currency(),
            )
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
                except (ValueError, TypeError, RuntimeError):
                    logger.exception("Failed to save calculated route")

            return ProcessedRouteResult(
                route=route,
                cost_info=cost_info,
                info_text=info_text,
                compliance=compliance,
                truck_obj=truck_obj,
            ), None

    def estimate_cost(self, truck: Any, distance_km: float) -> dict[str, Any]:
        try:
            from models.cost_models import CostEstimateRequest
            result = self.cost_engine.estimate(CostEstimateRequest(distance_km=distance_km))
            if result.success and result.data:
                return result.data.model_dump()
            return {}
        except (ValueError, TypeError, RuntimeError):
            logger.warning("Cost estimation failed for truck %s at %.0f km", truck, distance_km, exc_info=True)
            return {}

    @staticmethod
    def _truck_cost_payload(truck: Any) -> dict[str, Any]:
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
        route: dict[str, Any],
        truck_obj: dict[str, Any],
        cost_info: dict[str, Any],
        profile: str,
    ) -> None:
        route_id = route.get("history_id")
        self.trip_context.set_active_trip_info(
            distance_km=route.get("distance_km"),
            duration_min=route.get("duration_min"),
            fuel_liters=cost_info.get("fuel_liters"),
            fuel_cost=cost_info.get("fuel_cost"),
            route_history_v2_id=route_id,
            truck_id=truck_obj.get("id"),
            truck_fuel_consumption=truck_obj.get("fuel_consumption_l_per_100km"),
        )

    def load_history_record(self, record: RouteHistoryRecord) -> dict[str, Any]:
        """Return planner state patch: stops, profile label key, truck_id, route dict."""
        from services.route_profiles import ui_label_for_profile

        return {
            "stops": RoutePersistenceService.normalize_history_stops(record),
            "profile_label": ui_label_for_profile(record.profile or ""),
            "truck_id": str(record.truck_id) if record.truck_id else None,
            "excluded_countries": list(record.excluded_countries or []),
            "route": RoutePersistenceService.record_to_planner_route(record),
        }

    def load_from_url(self, url: str) -> dict[str, Any] | None:
        """Parse a share URL and return a planner state patch.

        Returns a dict with keys ``stops``, ``profile_label``,
        ``truck_id``, ``truck_label`` — ready to populate the
        route planner view (same shape as ``load_history_record``).
        Returns ``None`` if the URL is invalid or has no stops.
        """
        from services.route_sharing_service import parse_share_url

        parsed = parse_share_url(url)
        stops = parsed.get("stops", [])
        if not stops:
            return None

        from services.route_profiles import ui_label_for_profile

        # Build stop dicts compatible with the view's stops_state
        stop_dicts: list[dict[str, Any]] = []
        for i, (lat, lng) in enumerate(stops):
            stop_type = "start" if i == 0 else ("destination" if i == len(stops) - 1 else "stop")
            stop_dicts.append({
                "id": hashlib.md5(f"{lat}{lng}{i}".encode()).hexdigest()[:8],
                "type": stop_type,
                "lat": lat,
                "lon": lng,
                "address": None,
                "source": "share",
                "resolved": True,
            })

        profile = parsed.get("profile") or ""
        profile_label = ui_label_for_profile(profile) if profile else "Recommended"

        return {
            "stops": stop_dicts,
            "profile_label": profile_label,
            "truck_id": parsed.get("truck_id"),
            "truck_label": parsed.get("truck_label"),
            "excluded_countries": [],
        }

    def load_from_route_file(self, filepath: str) -> dict[str, Any] | None:
        """Load a ``.operionroute`` file and return a planner state patch.

        Same return shape as ``load_from_url``.
        """
        from services.route_sharing_service import decode_route_file

        try:
            with open(filepath, "rb") as f:
                data = f.read()
        except OSError as exc:
            logger.warning("load_from_route_file: could not read %s — %s", filepath, exc)
            return None

        try:
            parsed = decode_route_file(data)
        except ValueError as exc:
            logger.warning("load_from_route_file: decode failed — %s", exc)
            return None

        stops = parsed.get("stops", [])
        if not stops:
            return None

        from services.route_profiles import ui_label_for_profile

        stop_dicts: list[dict[str, Any]] = []
        for i, (lat, lng) in enumerate(stops):
            stop_type = "start" if i == 0 else ("destination" if i == len(stops) - 1 else "stop")
            stop_dicts.append({
                "id": hashlib.md5(f"{lat}{lng}{i}".encode()).hexdigest()[:8],
                "type": stop_type,
                "lat": lat,
                "lon": lng,
                "address": None,
                "source": "share",
                "resolved": True,
            })

        profile = parsed.get("profile") or ""
        profile_label = ui_label_for_profile(profile) if profile else "Recommended"

        return {
            "stops": stop_dicts,
            "profile_label": profile_label,
            "truck_id": parsed.get("truck_id"),
            "truck_label": parsed.get("truck_label"),
            "excluded_countries": [],
            "route": {
                "distance_km": parsed.get("distance_km"),
                "duration_min": parsed.get("duration_min"),
                "geometry": parsed.get("geometry"),
                "stops": [(s[0], s[1]) for s in stops],
            },
        }

    def export_route_metadata(self, route: dict[str, Any] | None) -> tuple[str | None, str | None]:
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
        except (OSError, ValueError, TypeError) as exc:
            return None, f"❌ {t('result.generic_error').format('Export', str(exc))}"


_PREFERRED_CURRENCY: str | None = None
_PREFERRED_CURRENCY_LOCK = threading.Lock()

def _get_preferred_currency() -> str:
    global _PREFERRED_CURRENCY
    if _PREFERRED_CURRENCY is not None:
        return _PREFERRED_CURRENCY
    with _PREFERRED_CURRENCY_LOCK:
        # Double-checked locking: re-check after acquiring lock
        if _PREFERRED_CURRENCY is not None:
            return _PREFERRED_CURRENCY
    try:
        from services.app_state import AppState
        currency = AppState().get("currency")
        if currency:
            _PREFERRED_CURRENCY = currency
            return currency
    except (ValueError, RuntimeError, AttributeError):
        pass
    try:
        from config import Config
        from database.db_manager import DatabaseManager
        db = DatabaseManager(Config.DB_PATH)
        try:
            db.execute("SELECT 1").fetchone()
            value = SettingsRepository(db).get_setting_value('pref_currency')
        finally:
            db.close()
        if value:
            _PREFERRED_CURRENCY = value
            return value
    except (ValueError, RuntimeError, OSError, TypeError):
        pass
    _PREFERRED_CURRENCY = "EUR"
    return "EUR"
