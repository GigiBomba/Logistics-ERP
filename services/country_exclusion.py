"""GraphHopper country exclusion via custom_model areas (POST routing).

GraphHopper ignores custom_model on GET /route; exclusions must be sent as JSON POST
with ch.disable=true so pathfinding respects blocked country polygons.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from services.country_borders import get_polygons
from utils.logger import get_logger

# ISO2 -> ISO3166-1 alpha3
ISO2_TO_ISO3: Dict[str, str] = {
    "AL": "ALB", "AD": "AND", "AT": "AUT", "BY": "BLR", "BE": "BEL",
    "BA": "BIH", "BG": "BGR", "HR": "HRV", "CY": "CYP", "CZ": "CZE",
    "DK": "DNK", "EE": "EST", "FI": "FIN", "FR": "FRA", "DE": "DEU",
    "GR": "GRC", "HU": "HUN", "IS": "ISL", "IE": "IRL", "IT": "ITA",
    "XK": "XKX", "LV": "LVA", "LI": "LIE", "LT": "LTU", "LU": "LUX",
    "MT": "MLT", "MD": "MDA", "MC": "MCO", "ME": "MNE", "NL": "NLD",
    "MK": "MKD", "NO": "NOR", "PL": "POL", "PT": "PRT", "RO": "ROU",
    "RU": "RUS", "SM": "SMR", "RS": "SRB", "SK": "SVK", "SI": "SVN",
    "ES": "ESP", "SE": "SWE", "CH": "CHE", "TR": "TUR", "UA": "UKR",
    "GB": "GBR", "VA": "VAT",
}

# Bounding boxes for fast country detection: (lon_min, lat_min, lon_max, lat_max)
# Tightened to minimize overlap with neighboring countries
COUNTRY_BOUNDS: Dict[str, Tuple[float, float, float, float]] = {
    "AL": (19.1, 39.6, 21.1, 42.7),
    "AD": (1.4, 42.4, 1.8, 42.7),
    "AT": (9.5, 46.4, 17.2, 49.0),
    "BY": (23.2, 51.3, 32.8, 56.2),
    "BE": (2.5, 49.5, 6.4, 51.5),
    "BA": (15.7, 42.6, 19.6, 45.3),
    "BG": (22.4, 41.2, 28.6, 44.2),
    "HR": (13.5, 42.4, 19.4, 46.6),
    "CY": (32.2, 34.5, 34.6, 35.7),
    "CZ": (12.1, 48.6, 18.9, 51.1),
    "DK": (8.0, 54.5, 15.2, 57.8),
    "EE": (21.8, 57.5, 28.2, 59.7),
    "FI": (20.6, 59.8, 31.6, 70.1),
    "FR": (-5.1, 41.3, 9.6, 51.1),
    "DE": (5.9, 47.3, 15.0, 55.1),
    "GR": (19.4, 34.8, 29.7, 41.8),
    "HU": (16.1, 45.7, 22.9, 48.6),
    "IS": (-24.5, 63.4, -13.5, 66.5),
    "IE": (-10.5, 51.4, -6.0, 55.4),
    "IT": (6.6, 36.6, 18.5, 47.1),
    "XK": (20.0, 41.8, 21.8, 43.3),
    "LV": (20.9, 55.7, 28.2, 58.1),
    "LI": (9.5, 47.0, 9.6, 47.3),
    "LT": (20.9, 53.9, 26.8, 56.5),
    "LU": (5.7, 49.4, 6.5, 50.2),
    "MT": (14.2, 35.8, 14.6, 36.1),
    "MD": (26.6, 45.5, 30.1, 48.5),
    "MC": (7.4, 43.7, 7.4, 43.8),
    "ME": (18.4, 41.8, 20.4, 43.6),
    "NL": (3.4, 50.7, 7.2, 53.6),
    "MK": (20.4, 40.8, 23.0, 42.4),
    "NO": (4.6, 57.9, 31.1, 71.2),
    "PL": (14.1, 49.0, 24.2, 54.9),
    "PT": (-9.5, 36.9, -6.2, 42.2),
    "RO": (20.2, 43.6, 29.7, 48.3),
    "RU": (27.4, 41.2, 40.0, 81.9),
    "SM": (12.4, 43.9, 12.5, 43.99),
    "RS": (18.8, 42.2, 23.0, 46.2),
    "SK": (16.8, 47.7, 22.6, 49.6),
    "SI": (13.4, 45.4, 16.6, 46.9),
    "ES": (-9.3, 36.0, 4.3, 43.8),
    "SE": (11.1, 55.3, 24.2, 69.1),
    "CH": (5.9, 45.8, 10.5, 47.8),
    "TR": (26.0, 36.0, 44.8, 42.1),
    "UA": (22.1, 45.0, 40.2, 52.4),
    "GB": (-8.6, 49.9, 1.8, 60.9),
    "VA": (12.4, 41.9, 12.5, 41.91),
}


@dataclass
class ExclusionPlan:
    """Routing exclusion plan passed to GraphHopperClient."""

    requested: List[str] = field(default_factory=list)
    applied: List[str] = field(default_factory=list)
    skipped_at_stops: List[str] = field(default_factory=list)
    custom_model: Optional[Dict[str, Any]] = None
    strategy: str = "none"

    @property
    def active(self) -> bool:
        return bool(self.custom_model and self.applied)


class CountryExclusionEngine:
    """Build GraphHopper custom_model polygons to block excluded countries."""

    def __init__(self) -> None:
        self.logger = get_logger("CountryExclusion")
        self.debug_logger = get_logger("route_debug")

    @staticmethod
    def normalize_codes(codes: Optional[Sequence[str]]) -> List[str]:
        if not codes:
            return []
        out: List[str] = []
        for c in codes:
            if not c or not isinstance(c, str):
                continue
            cc = c.strip().upper()
            if len(cc) == 2 and cc not in out:
                out.append(cc)
        return out

    @staticmethod
    def _point_in_bounds(lon: float, lat: float, bounds: Tuple[float, float, float, float]) -> bool:
        lon_min, lat_min, lon_max, lat_max = bounds
        return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max

    @staticmethod
    def countries_at_stops(stops: Sequence[Tuple[float, float]]) -> List[str]:
        """Return ISO2 codes whose bounds contain any stop (lat, lon)."""
        found: List[str] = []
        for lat, lon in stops:
            for code, bounds in COUNTRY_BOUNDS.items():
                if CountryExclusionEngine._point_in_bounds(lon, lat, bounds) and code not in found:
                    found.append(code)
        return found

    def prepare(
        self,
        excluded: Optional[Sequence[str]],
        stops: Sequence[Tuple[float, float]],
    ) -> ExclusionPlan:
        requested = self.normalize_codes(excluded)
        if not requested:
            self.debug_logger.info("[CountryExclusion] No excluded countries requested")
            return ExclusionPlan(requested=[], strategy="none")

        self.logger.info(f"[RoutePlanner] Excluding countries: {requested}")
        stop_countries = self.countries_at_stops(stops)
        skipped = [c for c in requested if c in stop_countries]
        applied = [c for c in requested if c not in stop_countries]

        if skipped:
            self.logger.warning(
                f"[CountryExclusion] Skipping block for {skipped} — route stop lies inside "
                f"(stops detected in: {stop_countries})"
            )

        if not applied:
            self.debug_logger.warning(
                "[CountryExclusion] All exclusions skipped because stops are inside excluded countries"
            )
            return ExclusionPlan(
                requested=requested,
                applied=[],
                skipped_at_stops=skipped,
                strategy="skipped_all",
            )

        custom_model = self._build_custom_model(applied)
        plan = ExclusionPlan(
            requested=requested,
            applied=applied,
            skipped_at_stops=skipped,
            custom_model=custom_model,
            strategy="custom_model_areas_post",
        )
        self.debug_logger.info(
            f"[RouteService] Generated exclusion strategy={plan.strategy} applied={applied} "
            f"skipped={skipped}"
        )
        try:
            self.debug_logger.info(
                f"[GraphHopper] Applied custom model exclusions: {json.dumps(custom_model, separators=(',', ':'))}"
            )
        except Exception:
            pass
        return plan

    def _build_custom_model(self, countries: List[str]) -> Dict[str, Any]:
        areas: Dict[str, Any] = {}
        conditions: List[str] = []
        for code in countries:
            rings = get_polygons(code)
            if not rings or len(rings[0]) < 3:
                self.logger.warning(f"[CountryExclusion] No polygon for {code}; skipping")
                continue
            area_id = f"avoid_{code.lower()}"
            if len(rings) == 1:
                coords = [[p[1], p[0]] for p in rings[0]]
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                areas[area_id] = {
                    "type": "Feature",
                    "properties": {"country": code},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [coords],
                    },
                }
            else:
                all_coords = []
                for ring in rings:
                    coords = [[p[1], p[0]] for p in ring]
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    all_coords.append([coords])
                areas[area_id] = {
                    "type": "Feature",
                    "properties": {"country": code},
                    "geometry": {
                        "type": "MultiPolygon",
                        "coordinates": all_coords,
                    },
                }
            conditions.append(f"in_{area_id}")

        if not areas:
            return {}

        if_clause = conditions[0] if len(conditions) == 1 else " || ".join(conditions)
        return {
            "areas": areas,
            "priority": [{"if": if_clause, "multiply_by": "0"}],
        }

    def merge_into_params(
        self,
        gh_params: Dict[str, Any],
        plan: ExclusionPlan,
    ) -> Dict[str, Any]:
        """Attach custom_model + ch.disable to GraphHopper params when exclusions are active."""
        if not plan.active or not plan.custom_model:
            return gh_params
        merged = dict(gh_params)
        merged["_custom_model"] = plan.custom_model
        merged["ch.disable"] = True
        merged["avoid_countries"] = plan.applied
        merged["_exclusion_strategy"] = plan.strategy
        merged["_exclusion_requested"] = plan.requested
        merged["_exclusion_skipped"] = plan.skipped_at_stops
        return merged
