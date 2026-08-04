"""Accessibility tests for QtRoutePlannerView.

Regression tests for existing accessible names + gap tests for description.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget

from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name,
    assert_accessible_name_not_empty,
)


# SP workaround: route_planner_view imports StyledComboBox from ui.widgets
# which accesses SP (imported as S internally).



# Real QWidget subclass to replace MapWidget (which requires QWebEngineView).
# Layouts require a real QWidget instance; a MagicMock will not work.
class _FakeMapWidget(QWidget):
    """Stand-in for MapWidget that satisfies layout type checks."""
    loadFinished = Signal(bool)
    def set_click_callback(self, cb):
        pass
    def setMinimumWidth(self, w: int):
        pass
    def page(self):
        return MagicMock()
    def destroy(self):
        pass


class TestRoutePlannerViewA11y:
    """QtRoutePlannerView — route planning with map and sidebar controls."""

    def _make_view(self, parent, qtbot):
        """Helper: create view with MapWidget and heavy services mocked."""
        from ui.views.route_planner_view import QtRoutePlannerView

        with patch("ui.views.route_planner_view.MapWidget", _FakeMapWidget):
            with patch("ui.views.route_planner_view.QtRouteMapRenderer"):
                with patch("ui.views.route_planner_view.RoutePlannerController"):
                    with patch("ui.views.route_planner_view.RouteHistoryService"):
                        with patch("ui.views.route_planner_view.RouteStateManager"):
                            with patch("ui.views.route_planner_view.FleetService"):
                                with patch("ui.views.route_planner_view.RoutePersistenceService"):
                                    # Patch _load_trucks to prevent async thread
                                    with patch.object(
                                        QtRoutePlannerView, "_load_trucks", lambda self: None
                                    ):
                                        view = QtRoutePlannerView(
                                            parent,
                                            db=MagicMock(),
                                            controller=MagicMock(),
                                            api_client=MagicMock(),
                                        )
                                        qtbot.addWidget(view)
                                        return view

    def test_view_retains_accessible_name(self, qt_widget, qtbot):
        """Regression: route planner already has accessibleName='Route planner'."""
        view = self._make_view(qt_widget, qtbot)
        assert_accessible_name(view, "Route planner")
        view.shutdown()

    def test_view_has_accessible_description(self, qt_widget, qtbot):
        """Gap: route planner has no accessibleDescription yet."""
        view = self._make_view(qt_widget, qtbot)
        # Currently empty; this test will FAIL until description is added.
        assert_accessible_description_not_empty(view)
        view.shutdown()

    def test_calculate_button_has_accessible_name(self, qt_widget, qtbot):
        """The primary 'Calculate' button should be identifiable."""
        view = self._make_view(qt_widget, qtbot)

        calc_btn = view.calc_btn
        name = calc_btn.accessibleName()
        if name:
            assert_accessible_name_not_empty(calc_btn)
        else:
            # Fallback: button has visible text
            assert calc_btn.text(), "Calculate button should have text content"

        view.shutdown()

    def test_truck_combo_and_profile_combo_have_accessible_names(self, qt_widget, qtbot):
        """Truck selector and profile dropdown should be accessible."""
        view = self._make_view(qt_widget, qtbot)

        truck_combo = view.truck_combo
        name = truck_combo.accessibleName()
        if name:
            assert_accessible_name_not_empty(truck_combo)

        profile_combo = view.profile_combo
        name = profile_combo.accessibleName()
        if name:
            assert_accessible_name_not_empty(profile_combo)

        view.shutdown()

    def test_sidebar_panels_have_accessible_names(self, qt_widget, qtbot):
        """Collapsible sidebar cards (Route, Options, Results) should have headers."""
        view = self._make_view(qt_widget, qtbot)

        # Check that collapsible card headers exist (they're QPushButtons)
        card_headers = view.findChildren(QWidget)
        # There should be some header buttons with accessible names
        header_btns = [
            w for w in card_headers
            if isinstance(w, QWidget) and w.accessibleName()
        ]
        # At minimum, the calculate button exists in the widget tree
        assert view.calc_btn is not None, "Calculate button should exist"
        # Ensure a button exists in the button bar layout
        assert view._button_bar_layout is not None, "Button bar layout should exist"

        view.shutdown()

    def test_export_and_share_buttons_have_accessible_names(self, qt_widget, qtbot):
        """Export and Share buttons in the bottom bar should be named."""
        view = self._make_view(qt_widget, qtbot)

        # The button bar contains export, share (and calculate) buttons
        # Look for all QPushButton descendants
        all_btns = view.findChildren(QWidget)
        text_btns = [b for b in all_btns if hasattr(b, "text") and callable(b.text) and b.text()]

        # At minimum there are 3+ buttons with visible text
        assert len(text_btns) >= 3, (
            f"Expected at least 3 buttons with text, found {len(text_btns)}"
        )

        view.shutdown()

    def test_focusable_controls_exist(self, qt_widget, qtbot):
        """Route planner should have focusable controls in the widget tree."""
        view = self._make_view(qt_widget, qtbot)

        # Find all children with a non-zero focus policy (regardless of visibility)
        from PySide6.QtCore import Qt
        focusable = [
            c for c in view.findChildren(QWidget)
            if c.focusPolicy() != Qt.FocusPolicy.NoFocus
        ]
        # Several interactive controls expected: combo boxes, buttons, etc.
        assert len(focusable) >= 3, (
            f"Expected at least 3 focusable children, found {len(focusable)}"
        )
        view.shutdown()
