"""Accessibility tests for MapWidget.

MapWidget is a folium Leaflet map rendered inside a QWebEngineView with a
QWebChannel JS bridge for marker/polyline/click support.  These tests verify
basic accessibility properties of the widget itself.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from tests.a11y.conftest import (
    assert_accessible_name_not_empty,
    assert_accessible_description_not_empty,
)

# Skip the entire module if QWebEngineView is not available (headless CI, etc.)
pytestmark = pytest.mark.skipif(
    not pytest.importorskip(
        "PySide6.QtWebEngineWidgets",
        reason="QWebEngineView not available",
    ),
    reason="Requires QWebEngineView",
)


class TestMapWidgetA11y:
    """MapWidget — Folium Leaflet map in a QWebEngineView.

    These tests document accessibility gaps.  MapWidget currently does not
    set an explicit accessibleName or accessibleDescription.
    """

    def test_widget_has_accessible_name(self, qt_widget, qtbot):
        """MapWidget should expose an accessibleName."""
        from ui.map.map_widget import MapWidget

        widget = MapWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        assert_accessible_name_not_empty(widget)

    def test_widget_accessible_description(self, qt_widget, qtbot):
        """MapWidget should expose an accessibleDescription."""
        from ui.map.map_widget import MapWidget

        widget = MapWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        assert_accessible_description_not_empty(widget)

    def test_widget_is_focusable(self, qt_widget, qtbot):
        """MapWidget uses NoFocus — intentional design choice.

        MapWidget is a mouse-interactive widget (folium Leaflet map inside
        a QWebEngineView).  NoFocus is deliberate: keyboard focus is managed
        by the embedded web view.  This test documents the design decision.
        """
        from ui.map.map_widget import MapWidget

        widget = MapWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        policy = widget.focusPolicy()
        # NoFocus is intentional — mouse-interactive, not keyboard-focusable
        assert policy == Qt.FocusPolicy.NoFocus, (
            f"MapWidget uses NoFocus by design; got {policy}. "
            f"If the focus policy changes, update this test accordingly."
        )
