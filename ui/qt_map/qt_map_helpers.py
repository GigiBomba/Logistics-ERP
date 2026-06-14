"""Map overlay helpers for the Qt MapWidget.

Mirrors the public API of ``ui/map_helpers.py`` but dispatches to the
``MapWidget`` JS bridge instead of TkinterMapView canvas primitives.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

from ui.qt_map.qt_map_widget import MapWidget

logger = logging.getLogger(__name__)


def clear_map_overlays(map_widget: MapWidget) -> None:
    """Remove all marker and polyline overlays from the map widget."""
    if map_widget is None:
        return
    try:
        map_widget.clear_overlays()
    except Exception:
        logger.exception("clear_map_overlays failed")


def create_path_on_map(
    map_widget: MapWidget,
    geometry: List[Tuple[float, float]],
    start_city: Optional[str] = None,
    end_city: Optional[str] = None,
    intermediate_stops: Optional[List[Tuple[float, float, str]]] = None,
    create_markers: bool = True,
) -> Any:
    """Draw a route polyline and optional stop markers.

    Returns a tuple ``(polyline, start_marker, end_marker, stop_markers)``.
    Because the Qt map uses a stateless JS bridge, we approximate by returning
    the geometry list as the "line" reference and using ``None`` for markers
    (callers that need marker handles should call ``add_marker`` individually).
    """
    if map_widget is None or not geometry:
        return None, None, None, []

    try:
        map_widget.clear_overlays()
    except Exception as exc:
        logger.warning("clear_map_overlays failed: %s", exc)

    coords = [(float(p[0]), float(p[1])) for p in geometry]
    try:
        map_widget.add_polyline(coords)
    except Exception as exc:
        logger.warning("add_polyline failed: %s", exc)

    start_marker = None
    end_marker = None
    stop_markers = []

    if create_markers:
        if start_city:
            try:
                map_widget.add_marker(coords[0][0], coords[0][1], start_city, "green")
                start_marker = True
            except Exception as exc:
                logger.warning("start marker failed: %s", exc)
        if end_city:
            try:
                map_widget.add_marker(coords[-1][0], coords[-1][1], end_city, "red")
                end_marker = True
            except Exception as exc:
                logger.warning("end marker failed: %s", exc)
        if intermediate_stops:
            for lat, lon, label in intermediate_stops:
                try:
                    map_widget.add_marker(lat, lon, label, "blue")
                    stop_markers.append(True)
                except Exception as exc:
                    logger.warning("stop marker failed: %s", exc)

    return coords, start_marker, end_marker, stop_markers
