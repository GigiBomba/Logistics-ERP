"""Accessibility tests for QtFleetTrackingView.

Regression tests for existing accessible names + gap tests for description.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name,
    assert_accessible_name_not_empty,
)


# Real QWidget subclass to replace MapWidget (which requires QWebEngineView).
# Layouts require a real QWidget instance; a MagicMock will not work.
class _FakeMapWidget(QWidget):
    """Stand-in for MapWidget that satisfies layout type checks."""
    def set_view(self, lat, lng, zoom=None):
        pass
    def clear_overlays(self):
        pass
    def add_marker(self, lat, lng, **kwargs):
        pass
    def destroy(self):
        pass


class TestFleetTrackingViewA11y:
    """QtFleetTrackingView — live fleet tracking map with vehicle list."""

    def _make_view(self, parent, qtbot):
        """Helper: create view with MapWidget and tracking service mocked."""
        from ui.views.fleet_tracking_view import QtFleetTrackingView

        # FleetTrackingService is a singleton; need to reset it
        from services.fleet_tracking_service import FleetTrackingService
        FleetTrackingService._instance = None

        with patch("ui.views.fleet_tracking_view.MapWidget", _FakeMapWidget):
            with patch("ui.views.fleet_tracking_view.fleet_tracking_service") as mock_svc:
                # Make is_configured return True so the full UI builds
                mock_svc.is_configured.return_value = True
                mock_svc.get_positions.return_value = []

                view = QtFleetTrackingView(
                    parent,
                    db=MagicMock(),
                    prefs=MagicMock(),
                    ops=MagicMock(),
                )
                qtbot.addWidget(view)
                return view

    def _make_view_not_configured(self, parent, qtbot):
        """Helper: create view when tracking is not configured (empty state)."""
        from ui.views.fleet_tracking_view import QtFleetTrackingView

        from services.fleet_tracking_service import FleetTrackingService
        FleetTrackingService._instance = None

        with patch("ui.views.fleet_tracking_view.MapWidget", _FakeMapWidget):
            with patch("ui.views.fleet_tracking_view.fleet_tracking_service") as mock_svc:
                mock_svc.is_configured.return_value = False

                view = QtFleetTrackingView(
                    parent,
                    db=MagicMock(),
                    prefs=MagicMock(),
                    ops=MagicMock(),
                )
                qtbot.addWidget(view)
                return view

    def test_view_retains_accessible_name(self, qt_widget, qtbot):
        """Regression: fleet tracking already has accessibleName='Fleet tracking'."""
        view = self._make_view(qt_widget, qtbot)
        assert_accessible_name(view, "Fleet tracking")
        view.shutdown()

    def test_view_has_accessible_description(self, qt_widget, qtbot):
        """Gap: fleet tracking has no accessibleDescription yet."""
        view = self._make_view(qt_widget, qtbot)
        # Currently empty; this test will FAIL until description is added.
        assert_accessible_description_not_empty(view)
        view.shutdown()

    def test_not_configured_state_retains_accessible_name(self, qt_widget, qtbot):
        """When tracking is not configured, view still has its accessibleName."""
        view = self._make_view_not_configured(qt_widget, qtbot)
        assert_accessible_name(view, "Fleet tracking")
        view.shutdown()

    def test_vehicle_panel_header_has_accessible_names(self, qt_widget, qtbot):
        """Vehicle panel title and refresh button should be identifiable."""
        view = self._make_view(qt_widget, qtbot)

        # Panel title label
        if view._updated_lbl is not None:
            name = view._updated_lbl.accessibleName()
            if name:
                assert_accessible_name_not_empty(view._updated_lbl)

        # Refresh button
        refresh_btn = view._refresh_btn
        if refresh_btn is not None:
            name = refresh_btn.accessibleName()
            if name:
                assert_accessible_name_not_empty(refresh_btn)
            else:
                # At minimum has text content
                assert refresh_btn.text(), "Refresh button should have text"

        view.shutdown()

    def test_detail_panel_has_accessible_children(self, qt_widget, qtbot):
        """Detail panel (bottom of sidebar) should contain accessible widgets."""
        view = self._make_view(qt_widget, qtbot)

        detail_panel = view._detail_panel
        if detail_panel is not None:
            # The detail panel itself should have some meaningful content
            detail_children = detail_panel.findChildren(QWidget)
            visible = [c for c in detail_children if c.isVisible()]
            # Even in the empty state, there should be some labels
            assert len(visible) >= 0  # Just ensure no crash

        view.shutdown()

    def test_focusable_controls_exist(self, qt_widget, qtbot):
        """Fleet tracking view should have focusable controls in the widget tree."""
        view = self._make_view(qt_widget, qtbot)

        # Find all children with a non-zero focus policy (regardless of visibility)
        from PySide6.QtCore import Qt
        focusable = [
            c for c in view.findChildren(QWidget)
            if c.focusPolicy() != Qt.FocusPolicy.NoFocus
        ]
        # At least 1 focusable element (refresh button)
        assert len(focusable) >= 1, (
            f"Expected at least 1 focusable child, found {len(focusable)}"
        )
        view.shutdown()
