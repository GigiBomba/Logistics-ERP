"""Tests for the Qt MapWidget with folium and QWebEngine."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ui.map.map_widget import MapBridge


class FakeMapWidget(QWidget):
    """Stub QWidget that mirrors MapWidget's public API."""
    loadFinished = Signal(bool)

    def __init__(self, parent=None, center=(0, 0), zoom=6):
        super().__init__(parent)
        self._map_ready = True
        self._on_click_callbacks = []
        self._bridge = MapBridge(self)
        self._bridge.mapClicked.connect(self._emit_click)

    def _emit_click(self, lat, lng):
        for cb in self._on_click_callbacks:
            try:
                cb(lat, lng)
            except Exception:
                pass

    def set_click_callback(self, callback):
        self._on_click_callbacks.clear()
        if callback is not None:
            self._on_click_callbacks.append(callback)

    def add_marker(self, lat, lng, label="", color="blue"):
        pass

    def add_polyline(self, coords, color="#6366f1", weight=3):
        pass

    def fit_bounds(self, lat1, lng1, lat2, lng2):
        pass

    def set_view(self, lat, lng, zoom=6):
        pass

    def add_rectangle(self, lat1, lng1, lat2, lng2, color="#ef4444", fill_opacity=0.15):
        pass

    def add_polygon(self, coords, color="#ef4444", fill_opacity=0.15, fill_color=""):
        pass

    def clear_overlays(self):
        pass

    def _run_js(self, js: str) -> None:
        pass

    def destroy(self):
        self.deleteLater()


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def map_widget(qt_widget, qtbot):
    widget = FakeMapWidget(qt_widget)
    qtbot.addWidget(widget)
    yield widget


@pytest.fixture
def real_map_widget(qt_widget, qtbot, monkeypatch):
    """Create a real MapWidget — requires software-rendering flags.

    If QWebEngineView fails to construct (headless/CI without flags), the
    fixture is skipped.
    """
    monkeypatch.setattr(
        "ui.map.map_widget.MapWidget._build_map",
        lambda self: None,
    )
    monkeypatch.setattr(
        "ui.map.map_widget.MapWidget._run_js",
        lambda self, js: None,
    )
    try:
        from ui.map.map_widget import MapWidget
        widget = MapWidget(qt_widget)
        qtbot.addWidget(widget)
        yield widget
        widget.destroy()
    except Exception:
        pytest.skip("QWebEngineView not available (use software rendering flags)")


# ── MapBridge tests ───────────────────────────────────────────────────────────


class TestMapBridge:
    def test_creation(self):
        bridge = MapBridge()
        assert bridge is not None

    def test_map_click_emits_signal(self, qtbot):
        bridge = MapBridge()
        clicks = []
        bridge.mapClicked.connect(lambda lat, lng: clicks.append((lat, lng)))
        bridge.map_click(44.4, 26.1)
        assert clicks == [(44.4, 26.1)]


# ── FakeMapWidget tests (always run) ──────────────────────────────────────────


class TestFakeMapWidget:
    def test_creation(self, map_widget):
        assert map_widget is not None

    def test_add_marker_does_not_crash(self, map_widget):
        map_widget.add_marker(44.4, 26.1, "Test", "green")

    def test_add_polyline_does_not_crash(self, map_widget):
        map_widget.add_polyline([(44.4, 26.1), (44.5, 26.2)])

    def test_fit_bounds_does_not_crash(self, map_widget):
        map_widget.fit_bounds(44.0, 26.0, 45.0, 27.0)

    def test_clear_overlays_does_not_crash(self, map_widget):
        map_widget.clear_overlays()

    def test_click_callback(self, map_widget):
        clicks = []
        map_widget.set_click_callback(lambda lat, lng: clicks.append((lat, lng)))
        map_widget._bridge.mapClicked.emit(44.4, 26.1)
        assert clicks == [(44.4, 26.1)]


# ── Real MapWidget tests (only when QWebEngineView is available) ─────────────


class TestRealMapWidget:
    def test_creation(self, real_map_widget):
        assert real_map_widget is not None

    def test_bridge_connected(self, real_map_widget):
        assert real_map_widget._bridge is not None

    def test_set_click_callback(self, real_map_widget):
        clicks = []
        real_map_widget.set_click_callback(lambda lat, lng: clicks.append((lat, lng)))
        real_map_widget._bridge.mapClicked.emit(44.4, 26.1)
        assert clicks == [(44.4, 26.1)]

    def test_add_marker_js_generated(self, real_map_widget, monkeypatch):
        js_calls = []
        monkeypatch.setattr(real_map_widget, "_run_js", lambda js: js_calls.append(js))
        real_map_widget._map_ready = True
        real_map_widget.add_marker(44.4, 26.1, "Test", "green")
        assert len(js_calls) == 1
        assert "_opAddMarker" in js_calls[0]
        assert "44.4" in js_calls[0]
        assert "26.1" in js_calls[0]

    def test_add_polyline_js_generated(self, real_map_widget, monkeypatch):
        js_calls = []
        monkeypatch.setattr(real_map_widget, "_run_js", lambda js: js_calls.append(js))
        real_map_widget._map_ready = True
        real_map_widget.add_polyline([(44.4, 26.1), (44.5, 26.2)], color="#ff0000")
        assert "_opAddPolyline" in js_calls[0]
        assert "44.4" in js_calls[0]

    def test_clear_overlays_js_generated(self, real_map_widget, monkeypatch):
        js_calls = []
        monkeypatch.setattr(real_map_widget, "_run_js", lambda js: js_calls.append(js))
        real_map_widget._map_ready = True
        real_map_widget.clear_overlays()
        assert "_opClearAllOverlays" in js_calls[0]
