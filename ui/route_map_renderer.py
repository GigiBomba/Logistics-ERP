"""Map overlay rendering for Route Planner (TkinterMapView, reused paths/markers)."""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple

from ui.map_helpers import create_path_on_map
from utils.perf_log import perf_timer

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
        self._last_geom_hash: Optional[str] = None
        self._last_draw_time = 0.0
        self._min_redraw_interval_s = 1.0

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
        geom_str = ";".join(f"{lat:.6f},{lon:.6f}" for lat, lon in geometry)
        geom_hash = hashlib.md5(geom_str.encode()).hexdigest()
        now = time.time()
        if geom_hash == self._last_geom_hash and (now - self._last_draw_time) < self._min_redraw_interval_s:
            return False
        self._last_geom_hash = geom_hash
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
                except Exception:
                    self.alt_route_line = None

            try:
                self.route_line, _, _, _ = create_path_on_map(
                    self.map_widget,
                    geometry,
                )
            except Exception:
                try:
                    self.route_line = self.map_widget.set_path(geometry, width=4, color="blue")
                except Exception:
                    self.route_line = None

            if highlight_avoided and route and route.get("excluded_countries_requested"):
                step = max(1, len(geometry) // 20)
                for lat, lon in geometry[::step]:
                    try:
                        if hasattr(self.map_widget, "set_marker"):
                            m = self.map_widget.set_marker(lat, lon, text="⚠️")
                            self.avoid_markers.append(m)
                    except Exception:
                        pass

    def center_on_geometry(self, geometry: List[Tuple[float, float]], zoom: int = 6) -> None:
        if not self.has_map or not geometry:
            return
        try:
            lat, lon = geometry[0]
            self.map_widget.set_position(lat, lon)
            self.map_widget.set_zoom(zoom)
        except Exception:
            pass
