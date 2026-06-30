"""Two-way folium map widget via QWebEngineView + QWebChannel.

Replaces ``TkinterMapView``. Renders a folium leaflet map inside a Qt web view
and exposes Python-callable JS functions for markers, polylines, and viewport
control. Map-click events flow back to Python via a QWebChannel slot.
"""

from __future__ import annotations

import contextlib
import html as html_module
import json
import logging
import os
import re
from typing import Callable

import folium
from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QSizePolicy

logger = logging.getLogger(__name__)

_QWC_JS: str | None = None


def _qwebchannel_js() -> str:
    global _QWC_JS
    if _QWC_JS is None:
        from utils.resource_path import resource_path
        p = resource_path("ui/map/qwebchannel.js")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                _QWC_JS = fh.read()
        else:
            logger.warning("qwebchannel.js not found at %s — bridge unavailable", p)
            _QWC_JS = ""
    return _QWC_JS


class MapBridge(QObject):
    """Exposed to JavaScript as ``pybridge``. JS calls these slots."""

    mapClicked = Signal(float, float)

    @Slot(float, float)
    def map_click(self, lat: float, lng: float) -> None:
        self.mapClicked.emit(lat, lng)


class MapWidget(QWebEngineView):
    """Folium leaflet map rendered in a QWebEngineView with JS bridge."""

    DEFAULT_CENTER = (44.4268, 26.1025)
    DEFAULT_ZOOM = 6

    def __init__(
        self,
        parent=None,
        center: tuple[float, float] = DEFAULT_CENTER,
        zoom: int = DEFAULT_ZOOM,
    ):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.page().setBackgroundColor(QColor("#09090b"))
        self.setStyleSheet("QWebEngineView { background-color: #09090b; border: none; margin: 0; padding: 0; }")
        self._center = center
        self._zoom = zoom
        self._bridge = MapBridge(self)
        self._on_click_callbacks: list[Callable[[float, float], None]] = []
        self._pending_js: list[str] = []

        channel = QWebChannel(self)
        self.page().setWebChannel(channel)
        channel.registerObject("pybridge", self._bridge)

        self._bridge.mapClicked.connect(self._emit_click)

        self._build_map()

    def _build_map(self) -> None:
        m = folium.Map(
            location=list(self._center),
            zoom_start=self._zoom,
            tiles="CartoDB dark_matter",
            control_scale=True,
        )
        map_var = m.get_name()

        # Get the raw iframe HTML from folium's figure
        raw = m._repr_html_()

        # Extract the srcdoc content from the iframe to get the raw HTML doc
        # Folium wraps the map in a responsive container with padding-bottom:60%.
        # We strip that and use the inner HTML doc directly.
        match = re.search(r'srcdoc="([^"]+)"', raw)
        inner_html = html_module.unescape(match.group(1)) if match else raw

        # Ensure full-viewport dark styling
        inner_html = inner_html.replace(
            "<html>",
            '<html style="background-color:#09090b; height:100%;">'
        )
        inner_html = inner_html.replace(
            "<body>",
            '<body style="background-color:#09090b; margin:0; padding:0; height:100%;">'
        )
        # Make the leaflet map div fill the viewport
        inner_html = inner_html.replace(
            '<div id="map"',
            '<div id="map" style="position:absolute;top:0;bottom:0;left:0;right:0;width:100%;height:100%;"'
        )

        qwc = _qwebchannel_js()
        bridge_script = self._bridge_script(map_var, qwc)
        inner_html = inner_html.replace("</body>", bridge_script + "\n</body>")

        self.setHtml(inner_html, QUrl("about:blank"))
        self._map_ready = False
        self.loadFinished.connect(self._on_load_finished)

    def _on_load_finished(self, ok: bool) -> None:
        if ok:
            self._map_ready = True
            for js in self._pending_js:
                try:
                    self.page().runJavaScript(js)
                except Exception:
                    logger.exception("runJavaScript failed for pending JS")
            self._pending_js.clear()

    @staticmethod
    def _bridge_script(map_var: str, qwc_js: str) -> str:
        return (
            f"<script>\n{qwc_js}\n</script>\n"
            "<script>\n"
            f"var _opmap = {map_var};\n"
            "document.addEventListener('DOMContentLoaded', function() {\n"
            "  new QWebChannel(qt.webChannelTransport, function(channel) {\n"
            "    window._pybridge = channel.objects.pybridge;\n"
            "    _opmap.on('click', function(e) {\n"
            "      try {\n"
            "        window._pybridge.map_click(e.latlng.lat, e.latlng.lng);\n"
            "      } catch(ex) {}\n"
            "    });\n"
            "  });\n"
            "});\n"
            "function _opAddMarker(lat, lng, label, color) {\n"
            "  var icon = new L.Icon.Default();\n"
            "  try {\n"
            "    var markerUrl = 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/'\n"
            "      + 'master/img/marker-icon-2x-' + color + '.png';\n"
            "    icon = L.icon({\n"
            "      iconUrl: markerUrl,\n"
            "      shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',\n"
            "      iconSize: [25,41], iconAnchor: [12,41], popupAnchor: [1,-34], shadowSize: [41,41]\n"
            "    });\n"
            "  } catch(e) {}\n"
            "  var marker = L.marker([lat, lng], {icon: icon, title: label}).addTo(_opmap);\n"
            "  if (label) marker.bindPopup(label);\n"
            "  return marker;\n"
            "}\n"
            "function _opAddPolyline(coords, color, weight) {\n"
            "  return L.polyline(coords, {color: color, weight: weight || 3, opacity: 0.8}).addTo(_opmap);\n"
            "}\n"
            "function _opFitBounds(lat1, lng1, lat2, lng2) {\n"
            "  _opmap.fitBounds([[lat1, lng1], [lat2, lng2]]);\n"
            "}\n"
            "function _opSetView(lat, lng, zoom) {\n"
            "  _opmap.setView([lat, lng], zoom);\n"
            "}\n"
            "function _opClearAllOverlays() {\n"
            "  _opmap.eachLayer(function(layer) {\n"
            "    if (layer._url === undefined) _opmap.removeLayer(layer);\n"
            "  });\n"
            "}\n"
            "function _opAddRectangle(lat1, lng1, lat2, lng2, color, fillOpacity) {\n"
            "  return L.rectangle([[lat1, lng1], [lat2, lng2]], {\n"
            "    color: color, weight: 1, fillColor: color, fillOpacity: fillOpacity || 0.15\n"
            "  }).addTo(_opmap);\n"
            "}\n"
            "function _opAddPolygon(coords, color, fillOpacity, fillColor) {\n"
            "  return L.polygon(coords, {\n"
            "    color: color, weight: 1, fillColor: fillColor || color, fillOpacity: fillOpacity || 0.15\n"
            "  }).addTo(_opmap);\n"
            "}\n"
            "</script>\n"
        )

    # ── Public methods ─────────────────────────────────────────────────────────

    def set_click_callback(self, callback: Callable[[float, float], None] | None) -> None:
        self._on_click_callbacks.clear()
        if callback is not None:
            self._on_click_callbacks.append(callback)

    def _emit_click(self, lat: float, lng: float) -> None:
        for cb in self._on_click_callbacks:
            with contextlib.suppress(Exception):
                cb(lat, lng)

    @staticmethod
    def _js_str(s: str) -> str:
        """Escape a string for safe embedding in a JavaScript single-quoted string."""
        return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "")

    @staticmethod
    def _js_color(s: str) -> str:
        """Validate a color string for safe JS embedding — only allow hex/rgb/named."""
        if re.match(r'^[#a-zA-Z0-9(),.%]+$', s):
            return s.replace("'", "")
        return "#6366f1"

    def add_marker(self, lat: float, lng: float, label: str = "", color: str = "blue") -> None:
        js_label = json.dumps(label)
        js_color = self._js_color(color)
        js = f"_opAddMarker({lat}, {lng}, {js_label}, '{js_color}');"
        self._run_js(js)

    def add_polyline(self, coords: list[tuple[float, float]], color: str = "#6366f1", weight: int = 3) -> None:
        coords_json = json.dumps([[lat, lng] for lat, lng in coords])
        js_color = self._js_color(color)
        js = f"_opAddPolyline({coords_json}, '{js_color}', {weight});"
        self._run_js(js)

    def fit_bounds(self, lat1: float, lng1: float, lat2: float, lng2: float) -> None:
        js = f"_opFitBounds({lat1}, {lng1}, {lat2}, {lng2});"
        self._run_js(js)

    def set_view(self, lat: float, lng: float, zoom: int = 6) -> None:
        js = f"_opSetView({lat}, {lng}, {zoom});"
        self._run_js(js)

    def add_rectangle(
        self, lat1: float, lng1: float, lat2: float, lng2: float,
        color: str = "#ef4444", fill_opacity: float = 0.15,
    ) -> None:
        js_color = self._js_color(color)
        js = f"_opAddRectangle({lat1}, {lng1}, {lat2}, {lng2}, '{js_color}', {fill_opacity});"
        self._run_js(js)

    def add_polygon(
        self, coords: list[tuple[float, float]],
        color: str = "#ef4444", fill_opacity: float = 0.15, fill_color: str = "",
    ) -> None:
        fill = fill_color or color
        js_color = self._js_color(color)
        js_fill = self._js_color(fill)
        coords_json = json.dumps([[lat, lng] for lat, lng in coords])
        js = f"_opAddPolygon({coords_json}, '{js_color}', {fill_opacity}, '{js_fill}');"
        self._run_js(js)

    def clear_overlays(self) -> None:
        self._run_js("_opClearAllOverlays();")

    def _run_js(self, js: str) -> None:
        if not self._map_ready:
            self._pending_js.append(js)
            return
        try:
            self.page().runJavaScript(js)
        except Exception:
            logger.exception("runJavaScript failed")

    def destroy(self) -> None:
        with contextlib.suppress(Exception):
            self._bridge.deleteLater()
        super().deleteLater()
