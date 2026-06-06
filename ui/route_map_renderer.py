"""Map overlay rendering for Route Planner (TkinterMapView, reused paths/markers)."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from ui.map_helpers import create_path_on_map
from utils.perf_log import perf_timer

logger = logging.getLogger(__name__)

try:
    from tkintermapview import TkinterMapView

    HAS_TKMAP = True
except Exception:
    HAS_TKMAP = False
    TkinterMapView = None  # type: ignore


class RouteMapRenderer:
    """Manages route path, stop markers, and optional comparison overlay on one map widget."""

    def __init__(self, map_widget: Any) -> None:
        self.map_widget = map_widget
        self.route_line = None
        self.alt_route_line = None
        self.stop_markers: List[Any] = []
        self.avoid_markers: List[Any] = []
        self._country_overlays: List[Any] = []
        self._last_geom_key: Optional[tuple] = None
        self._last_draw_time = 0.0
        self._min_redraw_interval_s = 0.3

    @property
    def has_map(self) -> bool:
        return HAS_TKMAP and self.map_widget is not None

    def clear_stop_markers(self) -> None:
        for marker in self.stop_markers:
            try:
                marker.delete()
            except Exception:
                pass
        self.stop_markers = []

    def clear_route_overlays(self) -> None:
        if self.route_line:
            try:
                self.route_line.delete()
            except Exception:
                pass
            self.route_line = None
        if self.alt_route_line:
            try:
                self.alt_route_line.delete()
            except Exception:
                pass
            self.alt_route_line = None
        for marker in self.avoid_markers:
            try:
                marker.delete()
            except Exception:
                pass
        self.avoid_markers = []
        self.clear_country_overlays()

    def clear_country_overlays(self) -> None:
        for overlay in self._country_overlays:
            try:
                overlay.delete()
            except Exception:
                pass
        self._country_overlays = []
        try:
            canvas = getattr(self.map_widget, 'canvas', None)
            if canvas is not None:
                canvas.delete("route_fallback")
        except Exception:
            pass

    def draw_avoided_country_overlays(self, country_codes: List[str]) -> None:
        from services.country_borders import get_polygons

        self.clear_country_overlays()
        if not self.has_map or not country_codes:
            return
        has_set_polygon = hasattr(self.map_widget, 'set_polygon')
        for code in country_codes:
            rings = get_polygons(code.upper())
            if not rings:
                continue
            for ring in rings:
                if len(ring) < 3:
                    continue
                try:
                    if has_set_polygon:
                        overlay = self.map_widget.set_polygon(
                            ring,
                            fill_color="#cc0000",
                            border_width=0,
                            name=f"avoid_{code.lower()}",
                        )
                        try:
                            if hasattr(overlay, 'canvas_polygon') and overlay.canvas_polygon is not None:
                                self.map_widget.canvas.itemconfigure(overlay.canvas_polygon, stipple="gray25")
                        except Exception:
                            pass
                    else:
                        canvas = getattr(self.map_widget, 'canvas', None)
                        if canvas is None:
                            continue
                        canvas_coords = [self.map_widget.get_canvas_pos(lat, lon) for lat, lon in ring]
                        flat = []
                        for x, y in canvas_coords:
                            flat.extend([x, y])
                        overlay = canvas.create_polygon(*flat, fill="#cc0000", stipple="gray25", outline="", tags=("avoid_overlay",))
                    self._country_overlays.append(overlay)
                except Exception as exc:
                    logger.warning("Failed to draw overlay for %s: %s", code, exc)

    def update_stop_markers(self, stops_state: List[Dict[str, Any]]) -> None:
        self.clear_stop_markers()
        if not self.has_map:
            return
        with perf_timer("map_stop_markers"):
            for stop in stops_state:
                if not stop.get("resolved"):
                    continue
                lat, lon = stop.get("lat"), stop.get("lon")
                if lat is None or lon is None:
                    continue
                try:
                    marker = self.map_widget.set_marker(lat, lon, text=stop.get("address"))
                    self.stop_markers.append(marker)
                except Exception:
                    pass

    def should_redraw(self, geometry: List[Tuple[float, float]]) -> bool:
        if not geometry:
            return False
        n = len(geometry)
        first = geometry[0]
        last = geometry[-1]
        now = time.time()
        if (n, first, last) == self._last_geom_key and (now - self._last_draw_time) < self._min_redraw_interval_s:
            return False
        self._last_geom_key = (n, first, last)
        self._last_draw_time = now
        return True

    def draw_route(
        self,
        geometry: List[Tuple[float, float]],
        route: Optional[Dict[str, Any]] = None,
        *,
        show_comparison: bool = True,
        highlight_avoided: bool = False,
    ) -> None:
        if not self.has_map or not geometry:
            return
        geometry = [(float(p[0]), float(p[1])) for p in geometry]
        if len(geometry) < 2:
            return
        if not self.should_redraw(geometry):
            return

        with perf_timer("map_draw_route"):
            self.clear_stop_markers()
            self.clear_route_overlays()

            orig = route.get("original_route") if isinstance(route, dict) else None
            if show_comparison and isinstance(orig, dict) and orig.get("geometry"):
                try:
                    self.alt_route_line = self.map_widget.set_path(
                        orig.get("geometry"), width=3, color="gray"
                    )
                except Exception as exc:
                    logger.warning("alt_route_line draw failed: %s", exc)
                    self.alt_route_line = None

            route_ok = False
            try:
                self.route_line, _, _, _ = create_path_on_map(
                    self.map_widget,
                    geometry,
                    create_markers=False,
                )
                route_ok = self.route_line is not None
            except Exception as exc:
                logger.warning("create_path_on_map failed: %s, trying fallback", exc)

            if not route_ok:
                try:
                    self.route_line = self.map_widget.set_path(geometry, width=4, color="blue")
                    route_ok = self.route_line is not None
                except Exception as exc:
                    logger.warning("fallback set_path failed: %s", exc)

            if not route_ok:
                self._draw_canvas_fallback(geometry)

            if highlight_avoided and route and route.get("excluded_countries_requested"):
                excluded = route["excluded_countries_requested"]
                if excluded:
                    self.draw_avoided_country_overlays(excluded)

    def _draw_canvas_fallback(self, geometry: List[Tuple[float, float]]) -> None:
        try:
            canvas = getattr(self.map_widget, 'canvas', None)
            if canvas is None:
                print("[DRAW] _draw_canvas_fallback ABORT: canvas is None")
                return
            w = max(canvas.winfo_width(), 300)
            h = max(canvas.winfo_height(), 300)
            lats = [p[0] for p in geometry]
            lons = [p[1] for p in geometry]
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
            span_lat = max(max_lat - min_lat, 0.0001)
            span_lon = max(max_lon - min_lon, 0.0001)
            pad = 20
            coords = []
            for lat, lon in geometry:
                x = pad + ((lon - min_lon) / span_lon) * (w - 2 * pad)
                y = h - pad - ((lat - min_lat) / span_lat) * (h - 2 * pad)
                coords.extend([x, y])
            line_id = canvas.create_line(*coords, fill="#0066cc", width=3, tags=("route_fallback",))
            logger.info("canvas fallback route drawn (line_id=%s)", line_id)
        except Exception as exc:
            logger.error("canvas fallback also failed: %s", exc)

    def center_on_geometry(self, geometry: List[Tuple[float, float]], zoom: int = 6) -> None:
        if not self.has_map or not geometry:
            return
        try:
            lat, lon = geometry[0]
            self.map_widget.set_position(lat, lon)
            self.map_widget.set_zoom(zoom)
        except Exception:
            pass
