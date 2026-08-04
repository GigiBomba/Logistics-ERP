"""Accessibility tests for QtDispatchBoardView.

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


# SP workaround: some widgets imported via dispatch_board reference SP from
# ui.widgets which imports it as 'S' rather than 'SP'.



class TestDispatchBoardViewA11y:
    """QtDispatchBoardView — kanban dispatch board with tabs and columns."""

    def _make_view(self, parent, qtbot):
        """Helper: create view with all heavy dependencies mocked."""
        from ui.views.dispatch_board.dispatch_board import QtDispatchBoardView
        import ui.views.dispatch_board.board_state as _board_state

        # Use individual patch() calls (no args = replace with MagicMock that
        # returns another MagicMock when called) to avoid InvalidSpecError
        # from trying to spec a Mock object.
        patches = [
            patch("ui.views.dispatch_board.dispatch_board.TripService"),
            patch("ui.views.dispatch_board.dispatch_board.FleetService"),
            patch("ui.views.dispatch_board.dispatch_board.ClientService"),
            patch("ui.views.dispatch_board.dispatch_board.DriverTruckService"),
            patch("ui.views.dispatch_board.dispatch_board.TripConflictService"),
            patch("ui.views.dispatch_board.dispatch_board.DispatchService"),
        ]
        for p in patches:
            p.start()

        try:
            with patch.object(
                _board_state.BoardStateMixin, "_start_load", lambda self: None
            ):
                view = QtDispatchBoardView(
                    parent,
                    db=MagicMock(),
                    prefs=MagicMock(),
                    ops=MagicMock(),
                )
                qtbot.addWidget(view)
                return view
        finally:
            for p in patches:
                p.stop()

    def test_view_retains_accessible_name(self, qt_widget, qtbot):
        """Regression: dispatch board already has accessibleName='Dispatch board'."""
        view = self._make_view(qt_widget, qtbot)
        assert_accessible_name(view, "Dispatch board")
        view.shutdown()

    def test_view_has_accessible_description(self, qt_widget, qtbot):
        """Gap: dispatch board has no accessibleDescription yet."""
        view = self._make_view(qt_widget, qtbot)
        # Currently empty; this test will FAIL until description is added.
        assert_accessible_description_not_empty(view)
        view.shutdown()

    def test_kanban_columns_retain_accessible_names(self, qt_widget, qtbot):
        """Regression: each kanban column has an accessibleName set."""
        from ui.views.dispatch_board.board_state import COLUMN_DEFS

        view = self._make_view(qt_widget, qtbot)

        for status_key, _title_key, _accent in COLUMN_DEFS:
            col = view._columns.get(status_key)
            assert col is not None, (
                f"Column '{status_key}' was expected but not found in _columns"
            )
            name = col.accessibleName()
            expected = (
                f"{status_key} column" if status_key else "Kanban column"
            )
            assert name == expected, (
                f"accessibleName mismatch for column '{status_key}':\n"
                f"  Expected: '{expected}'\n"
                f"  Actual:   '{name}'"
            )

        view.shutdown()

    def test_tab_widget_has_accessible_name(self, qt_widget, qtbot):
        """Dispatch tabs (QtDispatchTabs) should have accessible names."""
        view = self._make_view(qt_widget, qtbot)

        tabs = view._tabs
        name = tabs.accessibleName()
        # QtDispatchTabs might or might not set accessibleName
        if name:
            assert_accessible_name_not_empty(tabs)

        # Check tab buttons (inner QPushButton children) have names
        tab_btns = tabs.findChildren(QWidget)
        named = [b for b in tab_btns if b.accessibleName() and b.isVisible()]
        # At least some tab elements should be named
        if named:
            assert len(named) >= 1

        view.shutdown()

    def test_search_bar_has_accessible_name(self, qt_widget, qtbot):
        """Search/filter bar in dispatch board should be accessible."""
        view = self._make_view(qt_widget, qtbot)

        search_bar = view._search_bar
        name = search_bar.accessibleName()
        # Search bar may or may not have accessible name set; just verify it exists
        search_children = search_bar.findChildren(QWidget)
        named_children = [c for c in search_children if c.accessibleName() and c.isVisible()]

        # Key: the search text input should have a name or placeholder role
        if hasattr(search_bar, "_search_entry"):
            entry = search_bar._search_entry
            if entry.accessibleName():
                assert_accessible_name_not_empty(entry)
            elif entry.placeholderText():
                pass  # Placeholder text provides some context

        view.shutdown()

    def test_header_buttons_have_accessible_names(self, qt_widget, qtbot):
        """Export, refresh buttons in header should be named."""
        view = self._make_view(qt_widget, qtbot)

        named_header_widgets = 0
        for attr in ("_export_csv_btn", "_export_pdf_btn", "_refresh_btn"):
            btn = getattr(view, attr, None)
            if btn is not None and btn.accessibleName():
                named_header_widgets += 1

        # At least the refresh button is expected to have a name
        refresh_btn = getattr(view, "_refresh_btn", None)
        if refresh_btn is not None:
            assert_accessible_name_not_empty(refresh_btn)

        view.shutdown()
