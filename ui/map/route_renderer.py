"""Route overlay renderer for the Qt MapWidget.

Mirrors the API of ``ui/route_map_renderer.py`` but dispatches to
``MapWidget`` JS bridge calls instead of TkinterMapView canvas primitives.
"""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Any

from ui.design_tokens import COLOR_NEUTRAL_DEFAULT
from ui.map.map_helpers import create_path_on_map
from utils.perf_log import perf_timer

logger = logging.getLogger(__name__)


class QtRouteMapRenderer:
    """Manages route path, stop markers, and comparison overlay on a MapWidget."""

    # Marker colors are Leaflet color-marker names (web surface, not app
    # chrome) — intentionally exempt from design_tokens.py.
    MARKER_COLOR_START = "green"
    MARKER_COLOR_STOP = "blue"
    MARKER_COLOR_DEST = "red"
    ALT_ROUTE_COLOR = COLOR_NEUTRAL_DEFAULT
    # Map overlay colors are intentionally exempt from design_tokens.py (web surface, not app chrome).
    AVOID_COLOR = "#cc0000"
    AVOID_FILL_OPACITY = 0.15

    def __init__(self, map_widget) -> None:
        self.map_widget = map_widget
        self._last_geom_key: tuple | None = None
        self._last_draw_time = 0.0
        self._min_redraw_interval_s = 0.3

    def clear_stop_markers(self) -> None:
        self._clear_all()

    def clear_route_overlays(self) -> None:
        self._clear_all()

    def _clear_all(self) -> None:
        if self.map_widget is None:
            return
        try:
            self.map_widget.clear_overlays()
        except Exception:
            logger.exception("clear_overlays failed")

    def draw_avoided_country_overlays(self, country_codes: list[str]) -> None:
        if self.map_widget is None:
            return
        with contextlib.suppress(Exception):
            self.clear_route_overlays()
        if not country_codes:
            return

        from services.country_borders import get_polygons

        for code in country_codes:
            rings = get_polygons(code.upper())
            if not rings:
                continue
            for ring in rings:
                if len(ring) < 3:
                    continue
                try:
                    self.map_widget.add_polygon(
                        ring,
                        color=self.AVOID_COLOR,
                        fill_opacity=self.AVOID_FILL_OPACITY,
                    )
                except Exception as exc:
                    logger.warning("Failed to draw overlay for %s: %s", code, exc)

    def update_stop_markers(self, stops_state: list[dict[str, Any]]) -> None:
        self.clear_stop_markers()
        if self.map_widget is None:
            return
        with perf_timer("map_stop_markers"):
            for stop in stops_state:
                if not stop.get("resolved"):
                    continue
                lat, lon = stop.get("lat"), stop.get("lon")
                if lat is None or lon is None:
                    continue
                color = self.MARKER_COLOR_STOP
                if stop.get("type") == "start":
                    color = self.MARKER_COLOR_START
                elif stop.get("type") == "destination":
                    color = self.MARKER_COLOR_DEST
                try:
                    self.map_widget.add_marker(
                        lat, lon,
                        label=str(stop.get("address") or ""),
                        color=color,
                    )
                except Exception:
                    logger.exception("Failed to add stop marker")

    def should_redraw(self, geometry: list[tuple[float, float]]) -> bool:
        if not geometry:
            return False
        n = len(geometry)
        first = geometry[0]
        last = geometry[-1]
        now = time.time()
        return not ((n, first, last) == self._last_geom_key and now - self._last_draw_time < self._min_redraw_interval_s)

    def mark_redrawn(self, geometry: list[tuple[float, float]]) -> None:
        """Record the geometry and timestamp after a successful draw."""
        if not geometry:
            return
        n = len(geometry)
        first = geometry[0]
        last = geometry[-1]
        self._last_geom_key = (n, first, last)
        self._last_draw_time = time.time()

    def draw_route(
        self,
        geometry: list[tuple[float, float]],
        route: dict[str, Any] | None = None,
        *,
        show_comparison: bool = True,
        highlight_avoided: bool = False,
    ) -> None:
        if self.map_widget is None or not geometry:
            return
        geometry = [(float(p[0]), float(p[1])) for p in geometry if len(p) >= 2]
        if len(geometry) < 2:
            return
        if not self.should_redraw(geometry):
            return

        # Downsample for map rendering — 500 pts is more than enough
        # to draw a smooth polyline; avoids massive JSON serialization
        # and QWebEngineView JS overhead on 15K+ point routes
        MAX_MAP_PTS = 500
        geometry_raw = geometry
        if len(geometry) > MAX_MAP_PTS:
            step = max(1, len(geometry) // MAX_MAP_PTS)
            geometry = [geometry[i] for i in range(0, len(geometry), step)]
            if geometry[-1] != geometry_raw[-1]:
                geometry.append(geometry_raw[-1])

        try:
            self.clear_route_overlays()

            # Alternative route (comparison)
            orig = route.get("original_route") if isinstance(route, dict) else None
            if show_comparison and isinstance(orig, dict) and orig.get("geometry"):
                try:
                    alt_geo = orig.get("geometry")
                    alt_coords = [(float(p[0]), float(p[1])) for p in (alt_geo or []) if len(p) >= 2]
                    self.map_widget.add_polyline(alt_coords, color=self.ALT_ROUTE_COLOR, weight=2)
                except Exception as exc:
                    logger.warning("alt_route_line draw failed: %s", exc)

            # Primary route
            try:
                create_path_on_map(self.map_widget, geometry, create_markers=False)
            except Exception as exc:
                logger.warning("create_path_on_map failed: %s", exc)

            # Country overlays
            if highlight_avoided and route and route.get("excluded_countries_requested"):
                excluded = route["excluded_countries_requested"]
                if excluded:
                    self.draw_avoided_country_overlays(excluded)

            self.mark_redrawn(geometry)
        except Exception:
            logger.exception("draw_route failed")

    def center_on_geometry(self, geometry: list[tuple[float, float]], zoom: int = 6) -> None:
        if self.map_widget is None or not geometry:
            return
        try:
            lat, lon = geometry[0]
            self.map_widget.set_view(lat, lon, zoom)
        except Exception:
            pass
