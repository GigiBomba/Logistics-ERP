"""Simplified country border polygons and point-in-polygon utilities.

Loads data/country_borders.json once and provides fast lookup functions.
Each country stores a list of rings: first is mainland, rest are islands.
All coordinates are stored as [lat, lon] for consistency.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

_DATA: Optional[Dict[str, List[List[List[float]]]]] = None
_BBOX: Dict[str, Tuple[float, float, float, float]] = {}


def _load() -> Dict[str, List[List[List[float]]]]:
    global _DATA, _BBOX
    if _DATA is not None:
        return _DATA
    path = os.path.join("data", "country_borders.json")
    with open(path, "r", encoding="utf-8") as fh:
        _DATA = json.load(fh)
    for code, rings in _DATA.items():
        all_lats = []
        all_lons = []
        for ring in rings:
            all_lats.extend(p[0] for p in ring)
            all_lons.extend(p[1] for p in ring)
        _BBOX[code] = (min(all_lons), min(all_lats), max(all_lons), max(all_lats))
    return _DATA


def get_polygon(code: str) -> List[Tuple[float, float]]:
    """Return the main (first) ring for a country as [(lat,lon), ...] or empty."""
    data = _load()
    rings = data.get(code.upper(), [])
    if not rings or not rings[0]:
        return []
    return [(p[0], p[1]) for p in rings[0]]


def get_polygons(code: str) -> List[List[Tuple[float, float]]]:
    """Return ALL rings for a country. First is mainland, rest are islands."""
    data = _load()
    rings = data.get(code.upper(), [])
    result: List[List[Tuple[float, float]]] = []
    for ring in rings:
        result.append([(p[0], p[1]) for p in ring])
    return result


def point_in_polygon(lat: float, lon: float, polygon: List[Tuple[float, float]]) -> bool:
    """Ray-casting algorithm: returns True if (lat,lon) is inside the polygon."""
    if len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        lng_i, lat_i = polygon[i][1], polygon[i][0]
        lng_j, lat_j = polygon[j][1], polygon[j][0]
        if ((lng_i > lon) != (lng_j > lon)) and \
           (lat < (lat_j - lat_i) * (lon - lng_i) / (lng_j - lng_i) + lat_i):
            inside = not inside
        j = i
    return inside


def bbox_contains(code: str, lat: float, lon: float) -> bool:
    """Fast bounding-box pre-check before full point_in_polygon."""
    _load()
    b = _BBOX.get(code.upper())
    if b is None:
        return False
    return b[0] <= lon <= b[2] and b[1] <= lat <= b[3]


def countries_at_point(lat: float, lon: float) -> List[str]:
    """Return ISO2 codes whose polygon (any ring) contains the point."""
    data = _load()
    result: List[str] = []
    for code in data:
        if bbox_contains(code, lat, lon):
            for poly in get_polygons(code):
                if poly and point_in_polygon(lat, lon, poly):
                    result.append(code)
                    break
    return result


def point_in_country(lat: float, lon: float, code: str) -> bool:
    """Check if a point is inside any ring of a country's polygon."""
    if not bbox_contains(code, lat, lon):
        return False
    for poly in get_polygons(code):
        if poly and point_in_polygon(lat, lon, poly):
            return True
    return False


def countries_from_points(points: List[Tuple[float, float]]) -> List[str]:
    """Detect which countries a list of (lat,lon) points fall in. Sampled to max 30 points."""
    if not points:
        return []
    step = max(1, len(points) // 30)
    sampled = points[::step]
    found: set = set()
    for lat, lon in sampled:
        for code in countries_at_point(lat, lon):
            found.add(code)
    return list(found)


def get_bounds(code: str) -> Optional[Tuple[float, float, float, float]]:
    """Return (lon_min, lat_min, lon_max, lat_max) for a country."""
    _load()
    return _BBOX.get(code.upper())
