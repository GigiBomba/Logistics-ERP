"""Helper utilities for map drawing separated from UI logic.
This keeps geometry/path rendering isolated so UI file stays focused on widgets.

HARD RULE: NEVER create markers from route polyline points.
route geometry = ONLY polyline; markers = ONLY explicit stops.
"""
import logging
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def clear_map_overlays(map_widget) -> None:
    """Delete all route line and marker overlays from the map widget."""
    if not map_widget:
        return
    for attr in ("_last_route_line", "_last_start_marker", "_last_end_marker"):
        item = getattr(map_widget, attr, None)
        if item is not None:
            try:
                item.delete()
            except Exception:
                try:
                    map_widget.delete(item)
                except Exception:
                    pass
        setattr(map_widget, attr, None)
    prev_stops = getattr(map_widget, "_last_stop_markers", None) or []
    for marker in prev_stops:
        try:
            marker.delete()
        except Exception:
            pass
    map_widget._last_stop_markers = []


def create_path_on_map(
    map_widget,
    geometry: List[Tuple[float, float]],
    start_city: str = None,
    end_city: str = None,
    intermediate_stops: Optional[List[Tuple[float, float, str]]] = None,
):
    """Draw a route polyline and optional markers for start / waypoints / end.

    Args:
        map_widget: tkintermapview widget instance.
        geometry: route polyline points — used ONLY for the path (polyline).
        start_city: optional label for the start marker (first geometry point).
        end_city: optional label for the destination marker (last geometry point).
        intermediate_stops: explicit waypoint markers as (lat, lon, label) tuples.
                           NEVER derived from geometry points.

    Returns:
        (route_line, start_marker, end_marker, stop_markers)
    """
    route_line = None
    start_marker = None
    end_marker = None
    stop_markers: List[Any] = []

    if not geometry or not hasattr(map_widget, 'set_path'):
        return route_line, start_marker, end_marker, stop_markers

    try:
        # ── Cleanup any previous overlays ──────────────────────────
        clear_map_overlays(map_widget)

        # ── Draw polyline (geometry is ONLY for the path) ──────────
        try:
            coords = [(lat, lon) for (lat, lon) in geometry]
            route_line = map_widget.set_path(coords)
        except Exception:
            route_line = None

        geo_count = len(geometry)
        stops_count = len(intermediate_stops) if intermediate_stops else 0
        logger.debug("create_path_on_map: %d geometry points, %d explicit stops", geo_count, stops_count)

        # ── Start marker (first geometry point) ────────────────────
        try:
            start_marker = map_widget.set_marker(
                geometry[0][0], geometry[0][1],
                text=start_city or 'Start', marker_color='green',
            )
        except Exception:
            try:
                start_marker = map_widget.set_marker(
                    geometry[0][0], geometry[0][1],
                    text=start_city or 'Start',
                )
            except Exception:
                start_marker = None

        # ── Intermediate waypoint markers (ONLY from explicit stops) ──
        # HARD RULE: NEVER create markers from route polyline points.
        for stop in (intermediate_stops or []):
            try:
                lat, lon = stop[0], stop[1]
                label = stop[2] if len(stop) >= 3 else ""
                m = map_widget.set_marker(lat, lon, text=label)
                stop_markers.append(m)
            except Exception:
                pass

        # ── End marker (last geometry point) ────────────────────────
        try:
            end_marker = map_widget.set_marker(
                geometry[-1][0], geometry[-1][1],
                text=end_city or 'End', marker_color='red',
            )
        except Exception:
            try:
                end_marker = map_widget.set_marker(
                    geometry[-1][0], geometry[-1][1],
                    text=end_city or 'End',
                )
            except Exception:
                end_marker = None

        # ── Persist references for next cleanup ────────────────────
        map_widget._last_route_line = route_line
        map_widget._last_start_marker = start_marker
        map_widget._last_end_marker = end_marker
        map_widget._last_stop_markers = stop_markers

        logger.debug("Markers created: 1 start + %d stops + 1 end = %d total", len(stop_markers), len(stop_markers) + 2)

        # ── Fit bounding box ───────────────────────────────────────
        try:
            if hasattr(map_widget, 'fit_bounding_box'):
                lats = [p[0] for p in geometry]
                lons = [p[1] for p in geometry]
                max_lat = max(lats)
                min_lat = min(lats)
                min_lon = min(lons)
                max_lon = max(lons)
                map_widget.fit_bounding_box((max_lat, min_lon), (min_lat, max_lon))
        except Exception:
            pass

    except Exception:
        pass

    return route_line, start_marker, end_marker, stop_markers
