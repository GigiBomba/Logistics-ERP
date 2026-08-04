"""Accessibility tests for widget classes.

Some widgets intentionally lack accessibleName/accessibleDescription.
Those tests will FAIL, documenting the accessibility gap.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QPushButton, QWidget

from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name_not_empty,
)


class TestStatCardA11y:
    """StatCard — compact KPI metric card (gap: no accessibleName/Description set)."""

    def test_stat_card_accessible_name(self, qt_widget):
        from ui.widgets.stat_card import StatCard

        widget = StatCard(qt_widget, label="Revenue", value="$1,234")
        assert_accessible_name_not_empty(widget)

    def test_stat_card_accessible_description(self, qt_widget):
        from ui.widgets.stat_card import StatCard

        widget = StatCard(qt_widget, label="Revenue", value="$1,234")
        assert_accessible_description_not_empty(widget)


class TestToastA11y:
    """Toast — non-blocking notification overlay (gap: no accessibleName/Description)."""

    def test_toast_accessible_name(self, qt_widget):
        from ui.widgets.toast import Toast

        widget = Toast(qt_widget, message="Operation successful")
        assert_accessible_name_not_empty(widget)

    def test_toast_accessible_description(self, qt_widget):
        from ui.widgets.toast import Toast

        widget = Toast(qt_widget, message="Operation successful")
        assert_accessible_description_not_empty(widget)


class TestQtTripCardA11y:
    """QtTripCard — dispatch board trip card (gap: no accessibleName/Description)."""

    def test_trip_card_accessible_name(self, qt_widget):
        from ui.widgets.trip_card import QtTripCard

        trip_data = {
            "trip_id": "T-001",
            "status": "Planned",
            "origin": "New York",
            "destination": "Los Angeles",
            "truck_plate": "ABC-1234",
            "driver_name": "John Doe",
            "departure_date": "2025-06-01",
            "eta": "2025-06-03",
        }
        widget = QtTripCard(qt_widget, trip_data=trip_data)
        assert_accessible_name_not_empty(widget)

    def test_trip_card_accessible_description(self, qt_widget):
        from ui.widgets.trip_card import QtTripCard

        trip_data = {
            "trip_id": "T-001",
            "status": "Planned",
            "origin": "New York",
            "destination": "Los Angeles",
        }
        widget = QtTripCard(qt_widget, trip_data=trip_data)
        assert_accessible_description_not_empty(widget)


class TestTopBarA11y:
    """TopBar — regression tests for already-existing accessible names."""

    def test_back_button_retains_accessible_name(self, qt_widget):
        from ui.widgets.topbar import TopBar

        topbar = TopBar(qt_widget)
        back_btn = topbar._back_btn
        name = back_btn.accessibleName()
        assert name == "Go back", (
            f"TopBar back button accessibleName mismatch:\n"
            f"  Expected: 'Go back'\n"
            f"  Actual:   '{name}'"
        )

    def test_notification_bell_retains_accessible_name(self, qt_widget):
        from ui.widgets.topbar import TopBar

        topbar = TopBar(qt_widget)
        bell = topbar._bell
        name = bell.accessibleName()
        assert "Notification" in name, (
            f"Bell accessibleName should contain 'Notification':\n"
            f"  Actual: '{name}'"
        )

    def test_clock_retains_accessible_name(self, qt_widget):
        from ui.widgets.topbar import TopBar

        topbar = TopBar(qt_widget)
        clock = topbar._clock
        name = clock.accessibleName()
        assert "time" in name.lower() or "clock" in name.lower(), (
            f"Clock accessibleName should contain 'time' or 'clock':\n"
            f"  Actual: '{name}'"
        )

    def test_topbar_sections_have_accessible_names(self, qt_widget):
        from ui.widgets.topbar import TopBar

        topbar = TopBar(qt_widget)
        named = 0
        for child in topbar.findChildren(QWidget):
            if child.accessibleName():
                named += 1
        assert named >= 3, (
            f"Expected at least 3 topbar children with non-empty "
            f"accessibleName, found {named}"
        )


class TestSidebarA11y:
    """Sidebar — regression tests for already-existing accessible names."""

    def test_monogram_retains_accessible_name(self, qt_widget):
        from ui.widgets.sidebar import Sidebar

        sidebar = Sidebar(qt_widget)
        monogram = sidebar._monogram
        name = monogram.accessibleName()
        assert name, "Sidebar monogram accessibleName is empty"
        assert "Operion" in name or "home" in name.lower(), (
            f"Monogram accessibleName should describe the element:\n"
            f"  Actual: '{name}'"
        )

    def test_search_input_retains_accessible_name(self, qt_widget):
        from ui.widgets.sidebar import Sidebar

        sidebar = Sidebar(qt_widget)
        search = sidebar._search_input
        name = search.accessibleName()
        assert name, "Sidebar search input accessibleName is empty"
        assert "Search" in name, (
            f"Search input accessibleName should contain 'Search':\n"
            f"  Actual: '{name}'"
        )

    def test_nav_items_have_accessible_names(self, qt_widget):
        from ui.widgets.sidebar import Sidebar

        sidebar = Sidebar(qt_widget)
        # Add items so there are nav frames with accessible names to check
        sidebar.add_item("overview", "Overview")
        sidebar.add_item("analytics", "Analytics")
        sidebar.add_item("settings", "Settings")
        for key, frame in sidebar._items.items():
            name = frame.accessibleName()
            assert name, (
                f"Nav item '{key}' has empty accessibleName"
            )
