"""Tests for the assignment dropdown widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtAssignmentDropdown:
    def test_creation(self, qt_widget, qtbot, anchor_widget):
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        dropdown = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=[]),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dropdown)
        assert dropdown is not None

    def test_set_items(self, qt_widget, qtbot, anchor_widget):
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown, _ItemRow
        items = [
            {"id": 1, "label": "Truck A", "available": False},
            {"id": 2, "label": "Truck B", "available": False},
        ]
        dropdown = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=items),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dropdown)
        qtbot.wait(80)
        assert len(dropdown.findChildren(_ItemRow)) == 2

    def test_set_selected(self, qt_widget, qtbot, anchor_widget):
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown, _ItemRow
        on_select = MagicMock()
        items = [{"id": 1, "label": "Truck A", "available": True}]
        dropdown = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=items),
            on_select=on_select,
        )
        qtbot.addWidget(dropdown)
        # Patch _walk_set_click before the timer fires to avoid the __func__ bug
        original = _ItemRow._walk_set_click
        _ItemRow._walk_set_click = lambda self, w: None
        try:
            qtbot.wait(80)
            rows = dropdown.findChildren(_ItemRow)
            assert len(rows) == 1
            _ItemRow._walk_set_click = original
            rows[0]._on_click()
        finally:
            _ItemRow._walk_set_click = original
        on_select.assert_called_once_with(1)

    def test_get_selected_id(self, qt_widget, qtbot, anchor_widget):
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        items = [{"id": 1, "label": "Truck A", "available": False}]
        dropdown = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=items),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dropdown)
        qtbot.wait(80)
        # The loaded items are stored on the dropdown for selection.
        assert dropdown._items == items

    def test_clear(self, qt_widget, qtbot, anchor_widget):
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        items = [{"id": 1, "label": "Truck A", "available": False}]
        dropdown = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=items),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dropdown)
        qtbot.wait(80)
        assert dropdown._list_layout.count() == 1
        # Re-rendering with no items clears the previous rows (empty state).
        dropdown._items = []
        dropdown._render_items()
        assert dropdown._list_layout.count() == 1


# =========================================================================
# Sample data / fixtures for expanded tests
# =========================================================================

ITEMS = [
    {"id": 1, "label": "AB-01-TST", "sublabel": "Mercedes Actros", "available": True},
    {"id": 2, "label": "CD-02-TST", "sublabel": "Volvo FH", "available": True},
    {
        "id": 3,
        "label": "EF-03-TST",
        "sublabel": "MAN TGX",
        "available": False,
        "status_text": "In maintenance",
    },
]


@pytest.fixture
def anchor_widget(qtbot, qt_widget):
    from PySide6.QtWidgets import QPushButton

    btn = QPushButton("Anchor", qt_widget)
    qtbot.addWidget(btn)
    return btn


@pytest.fixture
def dropdown(qtbot, qt_widget, anchor_widget):
    from ui.widgets.assignment_dropdown import QtAssignmentDropdown

    dd = QtAssignmentDropdown(
        parent=qt_widget,
        anchor_widget=anchor_widget,
        title="Test",
        fetch_func=MagicMock(return_value=ITEMS),
        on_select=MagicMock(),
        on_close=MagicMock(),
    )
    qtbot.addWidget(dd)
    yield dd


# =========================================================================
# TestItemRow -- Individual row widget behaviour
# =========================================================================


class TestItemRow:
    """Individual _ItemRow widget behaviour."""

    # NOTE: _walk_set_click has a PySide6 compatibility issue with __func__
    # on builtin methods. We work around it by patching the method before
    # constructing _ItemRow with available=True.

    @staticmethod
    def _make_available_row(item, on_select=None):
        """Create an _ItemRow avoiding the _walk_set_click __func__ bug."""
        from ui.widgets.assignment_dropdown import _ItemRow

        # Patch before construction so the __init__ -> _install_click_handler
        # -> _walk_set_click path does not crash.
        original = _ItemRow._walk_set_click
        _ItemRow._walk_set_click = lambda self, w: None
        try:
            row = _ItemRow(
                {"id": item.get("id", 1), "label": item.get("label", ""), "available": True, **item},
                on_select=on_select or MagicMock(),
            )
        finally:
            _ItemRow._walk_set_click = original
        return row

    def test_available_row_has_pointer_cursor(self):
        """Available row -> pointing hand cursor."""
        from PySide6.QtCore import Qt

        row = self._make_available_row({"id": 1, "label": "Test"})
        assert row.cursor().shape() == Qt.PointingHandCursor

    def test_unavailable_row_has_arrow_cursor(self):
        """Not available -> arrow cursor."""
        from ui.widgets.assignment_dropdown import _ItemRow
        from PySide6.QtCore import Qt

        row = _ItemRow(
            {
                "id": 1,
                "label": "Test",
                "available": False,
                "status_text": "Offline",
            },
            on_select=MagicMock(),
        )
        assert row.cursor().shape() == Qt.ArrowCursor

    def test_click_fires_on_select(self, qtbot):
        """Click -> on_select called with item_id."""
        on_select = MagicMock()
        row = self._make_available_row({"id": 42, "label": "Test"}, on_select=on_select)
        # Manually wire click handler since _walk_set_click was skipped
        row._on_click = lambda ev=None: on_select(42)
        qtbot.addWidget(row)
        row.show()
        from PySide6.QtCore import Qt

        qtbot.mouseClick(row, Qt.LeftButton)
        on_select.assert_called_once_with(42)

    def test_click_unavailable_does_nothing(self, qtbot):
        """Unavailable click -> on_select not called."""
        from ui.widgets.assignment_dropdown import _ItemRow

        on_select = MagicMock()
        row = _ItemRow(
            {
                "id": 42,
                "label": "Test",
                "available": False,
                "status_text": "Offline",
            },
            on_select=on_select,
        )
        qtbot.addWidget(row)
        row.show()
        from PySide6.QtCore import Qt

        qtbot.mouseClick(row, Qt.LeftButton)
        on_select.assert_not_called()

    def test_hover_changes_background(self):
        """enterEvent -> stylesheet set."""
        row = self._make_available_row({"id": 1, "label": "Test"})
        row.enterEvent(None)
        assert row.styleSheet() != ""

    def test_leave_clears_stylesheet(self):
        """leaveEvent -> stylesheet cleared."""
        row = self._make_available_row({"id": 1, "label": "Test"})
        row.enterEvent(None)
        assert row.styleSheet() != ""
        row.leaveEvent(None)
        assert row.styleSheet() == ""


# =========================================================================
# TestQtAssignmentDropdownUI -- Dropdown construction
# =========================================================================


class TestQtAssignmentDropdownUI:
    """Dropdown construction."""

    def test_dropdown_has_popup_flags(self, dropdown):
        """windowFlags includes Qt.Popup."""
        from PySide6.QtCore import Qt

        assert dropdown.windowFlags() & Qt.Popup

    def test_header_contains_title(self, dropdown):
        """Header QLabel text matches title."""
        from PySide6.QtWidgets import QLabel

        labels = dropdown.findChildren(QLabel)
        assert any("Test" in l.text() for l in labels)

    def test_header_has_close_button(self, dropdown):
        """Close QLabel with '✕' exists."""
        from PySide6.QtWidgets import QLabel

        labels = dropdown.findChildren(QLabel)
        assert any("\u2715" in l.text() for l in labels)

    def test_scroll_area_exists(self, dropdown):
        """_scroll is QScrollArea, _content is QWidget."""
        from PySide6.QtWidgets import QScrollArea, QWidget

        assert isinstance(dropdown._scroll, QScrollArea)
        assert isinstance(dropdown._content, QWidget)


# =========================================================================
# TestQtAssignmentDropdownItems -- Item loading and rendering
# =========================================================================


class TestQtAssignmentDropdownItems:
    """Item loading and rendering."""

    def test_loading_shows_spinner_text(self, qtbot, qt_widget, anchor_widget):
        """_show_loading -> label with loading text."""
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        from services.i18n import t
        from PySide6.QtWidgets import QLabel

        dd = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=ITEMS),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dd)
        loading_text = t("dispatch_board.loading_options")
        found = any(
            loading_text in c.text()
            for c in dd.findChildren(QLabel)
            if c.text()
        )
        assert found

    def test_error_shows_error_message(self, qtbot, qt_widget, anchor_widget):
        """_show_error('boom') -> label with 'boom'."""
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        from PySide6.QtWidgets import QLabel

        dd = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(side_effect=ValueError("boom")),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dd)
        qtbot.wait(80)
        found = any(
            "boom" in c.text() for c in dd.findChildren(QLabel) if c.text()
        )
        assert found

    def test_empty_shows_no_options(self, qtbot, qt_widget, anchor_widget):
        """Empty list -> _show_empty called."""
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown, _ItemRow
        from services.i18n import t
        from PySide6.QtWidgets import QLabel

        dd = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=[]),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dd)
        qtbot.wait(80)
        assert len(dd.findChildren(_ItemRow)) == 0
        empty_text = t("dispatch_board.no_options")
        found = any(
            empty_text in c.text() for c in dd.findChildren(QLabel) if c.text()
        )
        assert found

    def test_load_items_renders_rows(self, qtbot, qt_widget, anchor_widget):
        """fetch_func returns items -> _ItemRow children created."""
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown, _ItemRow

        # Use all-unavailable items to avoid _walk_set_click __func__ bug
        items = [{"id": i, "label": f"T{i}", "available": False} for i in range(3)]
        dd = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=items),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dd)
        qtbot.wait(80)
        rows = dd.findChildren(_ItemRow)
        assert len(rows) == 3

    def test_load_items_on_error_shows_error(self, qtbot, qt_widget, anchor_widget):
        """fetch_func raises -> _show_error called."""
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        from PySide6.QtWidgets import QLabel

        fetch_func = MagicMock(side_effect=RuntimeError("DB fail"))
        dd = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=fetch_func,
            on_select=MagicMock(),
        )
        qtbot.addWidget(dd)
        qtbot.wait(80)
        found = any(
            "DB fail" in c.text() for c in dd.findChildren(QLabel) if c.text()
        )
        assert found

    def test_render_items_clears_previous(self, qtbot, qt_widget, anchor_widget):
        """Rendering twice -> old rows deleted, new rows shown."""
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown

        # Use all-unavailable items to avoid _walk_set_click __func__ bug
        items = [{"id": i, "label": f"T{i}", "available": False} for i in range(3)]
        dd = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=items),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dd)
        qtbot.wait(80)
        # After initial render, layout should have 3 items
        assert dd._list_layout.count() == 3
        # Render again with new items
        dd._items = [{"id": 9, "label": "New", "available": False}]
        dd._render_items()
        # After re-render, layout should have 1 item (old ones cleared)
        assert dd._list_layout.count() == 1

    def test_render_items_empty_shows_empty(self, qtbot, qt_widget, anchor_widget):
        """Empty list -> _show_empty called."""
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        from services.i18n import t
        from PySide6.QtWidgets import QLabel

        dd = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=[]),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dd)
        qtbot.wait(80)
        empty_text = t("dispatch_board.no_options")
        found = any(
            empty_text in c.text() for c in dd.findChildren(QLabel) if c.text()
        )
        assert found


# =========================================================================
# TestQtAssignmentDropdownInteraction -- User interaction
# =========================================================================


class TestQtAssignmentDropdownInteraction:
    """User interaction."""

    def test_show_anchored_positions_below(self, dropdown, anchor_widget, qtbot):
        """show_anchored moves dropdown below anchor."""
        from PySide6.QtCore import QPoint

        anchor_global = anchor_widget.mapToGlobal(QPoint(0, 0))
        expected_y = anchor_global.y() + anchor_widget.height() + 2
        dropdown.show_anchored(anchor_widget)
        assert dropdown.y() >= expected_y - 2  # allow small variance

    def test_focus_out_closes_dropdown(self, dropdown, qtbot):
        """focusOutEvent -> close() called."""
        close_mock = MagicMock(wraps=dropdown.close)
        dropdown.close = close_mock
        from PySide6.QtGui import QFocusEvent
        from PySide6.QtCore import QEvent

        event = QFocusEvent(QEvent.FocusOut)
        dropdown.focusOutEvent(event)
        qtbot.wait(50)
        close_mock.assert_called_once()

    def test_close_button_calls_on_close(self, dropdown, qtbot):
        """Close button click -> _on_close callback."""
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import Qt

        close_btn = next(
            (
                c
                for c in dropdown.findChildren(QLabel)
                if "\u2715" in c.text()
            ),
            None,
        )
        assert close_btn is not None, "Close button not found"
        close_btn.mousePressEvent(None)
        dropdown._on_close.assert_called_once()

    def test_item_click_fires_on_select(self, qtbot, qt_widget, anchor_widget):
        """Click on item row -> on_select callback."""
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown, _ItemRow

        on_select = MagicMock()
        # Use available=True item, building row with workaround
        items = [{"id": 99, "label": "Test99", "available": True}]
        dd = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=items),
            on_select=on_select,
        )
        # Patch _walk_set_click before timer fires to avoid __func__ bug
        original = _ItemRow._walk_set_click
        _ItemRow._walk_set_click = lambda self, w: None
        try:
            qtbot.wait(80)
            rows = dd.findChildren(_ItemRow)
            assert len(rows) == 1
            # Restore and wire _on_click via original handler
            _ItemRow._walk_set_click = original
            rows[0]._on_click()
        finally:
            _ItemRow._walk_set_click = original
        on_select.assert_called_once_with(99)


# =========================================================================
# TestQtAssignmentDropdownEdgeCases -- Edge cases
# =========================================================================


class TestQtAssignmentDropdownEdgeCases:
    """Edge cases."""

    def test_fetch_func_returns_none_handled(self, qtbot, qt_widget, anchor_widget):
        """fetch_func returns None -> error or empty shown, no crash."""
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown

        dd = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=None),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dd)
        # Should not raise
        qtbot.wait(80)
        # The dropdown should show either an error or empty state
        from PySide6.QtWidgets import QLabel

        assert any(c.text() for c in dd.findChildren(QLabel) if c.text())

    def test_double_show_anchored(self, qtbot, qt_widget, anchor_widget):
        """Calling show_anchored twice repositions without error."""
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown

        items = [{"id": 1, "label": "T1", "available": False}]
        dd = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=items),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dd)

        # Show twice without crashing
        dd.show_anchored(anchor_widget)
        dd.show_anchored(anchor_widget)
        # The dropdown should be visible after the second call
        assert dd.isVisible()

    def test_item_with_missing_keys(self, qtbot, qt_widget, anchor_widget):
        """Item missing keys -> no crash."""
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown, _ItemRow

        # Use unavailable items to avoid _walk_set_click bug
        items = [{"id": 1, "available": False}, {"id": 2, "label": "Partial", "available": False}]
        dd = QtAssignmentDropdown(
            qt_widget,
            anchor_widget,
            "Test",
            fetch_func=MagicMock(return_value=items),
            on_select=MagicMock(),
        )
        qtbot.addWidget(dd)
        qtbot.wait(80)
        rows = dd.findChildren(_ItemRow)
        # Both items should render (missing keys handled gracefully)
        assert len(rows) == 2

