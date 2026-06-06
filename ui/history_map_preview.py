"""Embedded TkinterMapView preview for Route History (single instance, reusable)."""
from __future__ import annotations

import logging
import tkinter as tk
from typing import Any, List, Optional, Tuple

from ui.styles import Theme
from ui.map_helpers import clear_map_overlays, create_path_on_map

logger = logging.getLogger(__name__)

try:
    from tkintermapview import TkinterMapView

    HAS_TKMAP = True
except ImportError:
    HAS_TKMAP = False
    TkinterMapView = None  # type: ignore

from ui.map_helpers import create_path_on_map


class HistoryMapPreview:
    """Lazy-initialized mini-map with route overlay and cleanup on destroy."""

    DEFAULT_LAT = 46.0
    DEFAULT_LON = 25.0
    DEFAULT_ZOOM = 5

    def __init__(self, parent: tk.Widget, height: int = 200) -> None:
        self.parent = parent
        self.height = height
        self._container = tk.Frame(parent, bg=Theme.SURFACE, height=height)
        self._container.pack(fill="both", expand=True)
        self._container.pack_propagate(True)

        self._map: Any = None
        self._ready = False
        self._retry_count = 0
        self._max_retries = 20
        self._placeholder: Optional[tk.Label] = None
        self._fallback_canvas: Optional[tk.Canvas] = None
        self._route_line = None
        self._bound_resize = False

    def _ensure_widget(self) -> None:
        if self._map is not None or self._fallback_canvas is not None:
            return
        if HAS_TKMAP:
            self._map = TkinterMapView(self._container, corner_radius=0)
            self._map.pack(fill="both", expand=True)
            if not self._bound_resize:
                self._container.bind("<Configure>", self._on_resize)
                self._bound_resize = True
            root = self._container.winfo_toplevel()
            root.after_idle(self._deferred_init)
        else:
            self._fallback_canvas = tk.Canvas(
                self._container,
                height=self.height,
                bg=Theme.INPUT_BG,
                highlightthickness=1,
                highlightbackground=Theme.BORDER,
            )
            self._fallback_canvas.pack(fill="both", expand=True)

    def _deferred_init(self) -> None:
        if not self._map or self._ready:
            return
        self._retry_count += 1
        if self._retry_count > self._max_retries:
            self._draw_fallback()
            return
        try:
            if self._map.winfo_width() < 2 or self._map.winfo_height() < 2:
                self._container.winfo_toplevel().after(50, self._deferred_init)
                return
            self._map.set_position(self.DEFAULT_LAT, self.DEFAULT_LON)
            self._map.set_zoom(self.DEFAULT_ZOOM)
            self._ready = True
        except Exception:
            self._container.winfo_toplevel().after(100, self._deferred_init)

    def _on_resize(self, _event=None) -> None:
        if self._map and self._ready:
            try:
                self._map.update()
            except Exception:
                pass

    def clear(self) -> None:
        self._clear_overlays()
        if self._map and self._ready:
            try:
                self._map.set_position(self.DEFAULT_LAT, self.DEFAULT_LON)
                self._map.set_zoom(self.DEFAULT_ZOOM)
            except Exception:
                pass

    def _clear_overlays(self) -> None:
        """Delete ALL previous overlays (route line, markers) from the map widget."""
        clear_map_overlays(self._map)
        self._route_line = None

    def show_route(
        self,
        geometry: Optional[List[Any]],
        max_points: int = 800,
        intermediate_stops: Optional[List[Any]] = None,
    ) -> None:
        """Render route polyline with start/end markers and optional waypoint stops.

        Args:
            geometry: route polyline points (lat, lon) — drawn as polyline ONLY.
            max_points: max polyline points before downsampling.
            intermediate_stops: explicit waypoint markers as (lat, lon, label) tuples.
                                NEVER derived from geometry points.
        """
        self._ensure_widget()
        points = self._normalize_geometry(geometry)
        raw_count = len(points)
        if len(points) > max_points:
            step = max(1, len(points) // max_points)
            sampled = points[::step]
            if sampled[-1] != points[-1]:
                sampled.append(points[-1])
            points = sampled
        logger.debug("show_route: %d raw pts -> %d sampled pts", raw_count, len(points))

        if self._map:
            self._clear_overlays()
            if len(points) < 2:
                self.clear()
                return
            if not self._ready:
                self._container.winfo_toplevel().after(
                    80, lambda: self.show_route(geometry, max_points, intermediate_stops)
                )
                return
            try:
                create_path_on_map(self._map, points, intermediate_stops=intermediate_stops)
            except Exception as exc:
                logger.warning("history map create_path_on_map failed: %s", exc)
                self._draw_fallback(points)
            return

        if self._fallback_canvas:
            self._draw_fallback(points)

    def _normalize_geometry(self, geometry: Optional[List[Any]]) -> List[Tuple[float, float]]:
        points: List[Tuple[float, float]] = []
        if not geometry:
            return points
        for pt in geometry:
            try:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    lat, lon = float(pt[0]), float(pt[1])
                    points.append((lat, lon))
            except (TypeError, ValueError):
                continue
        return points

    def _draw_fallback(self, points: List[Tuple[float, float]]) -> None:
        canvas = self._fallback_canvas
        if not canvas:
            return
        canvas.delete("all")
        w = max(canvas.winfo_width(), 280)
        h = self.height
        if len(points) < 2:
            canvas.create_text(w / 2, h / 2, text="No route selected", fill=Theme.MUTED)
            return
        lats = [p[0] for p in points]
        lons = [p[1] for p in points]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        pad = 14
        span_lat = max(max_lat - min_lat, 0.0001)
        span_lon = max(max_lon - min_lon, 0.0001)
        coords = []
        step = max(1, len(points) // 250)
        for lat, lon in points[::step]:
            x = pad + ((lon - min_lon) / span_lon) * (w - 2 * pad)
            y = h - pad - ((lat - min_lat) / span_lat) * (h - 2 * pad)
            coords.extend([x, y])
        canvas.create_line(*coords, fill=Theme.ACCENT, width=2, smooth=True)

    def destroy(self) -> None:
        self._clear_overlays()
        if self._map:
            try:
                self._map.pack_forget()
                self._map.destroy()
            except Exception:
                pass
            self._map = None
        if self._fallback_canvas:
            try:
                self._fallback_canvas.destroy()
            except Exception:
                pass
            self._fallback_canvas = None
        self._ready = False
        try:
            self._container.destroy()
        except Exception:
            pass
