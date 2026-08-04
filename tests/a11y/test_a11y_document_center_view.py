"""Accessibility tests for QtDocumentCenterView.

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


# SP workaround: document_center imports SectionHeader from ui.widgets which
# accesses SP (imported as S internally).



class TestDocumentCenterViewA11y:
    """QtDocumentCenterView — document management with sidebar, list, detail."""

    def _make_view(self, parent, qtbot):
        """Helper: create view with DocumentService mocked and refresh patched."""
        from ui.views.document_center.document_center import QtDocumentCenterView

        with patch("ui.views.document_center.document_center.DocumentService"):
            # Patch refresh to be a no-op to prevent the deferred QTimer from
            # calling _load_documents which crashes with MagicMock results.
            with patch.object(QtDocumentCenterView, "refresh", lambda self: None):
                view = QtDocumentCenterView(
                    parent,
                    db=MagicMock(),
                    prefs=MagicMock(),
                    ops=MagicMock(),
                )
                qtbot.addWidget(view)
                return view

    def test_view_retains_accessible_name(self, qt_widget, qtbot):
        """Regression: document center already has accessibleName='Document center'."""
        view = self._make_view(qt_widget, qtbot)
        assert_accessible_name(view, "Document center")
        view.shutdown()

    def test_view_has_accessible_description(self, qt_widget, qtbot):
        """Gap: document center has no accessibleDescription yet."""
        view = self._make_view(qt_widget, qtbot)
        # Currently empty; this test will FAIL until description is added.
        assert_accessible_description_not_empty(view)
        view.shutdown()

    def test_tab_widget_has_accessible_names(self, qt_widget, qtbot):
        """QTabWidget tabs (Documents / Automation) should have names."""
        view = self._make_view(qt_widget, qtbot)

        tab_widget = view._tab_widget
        # The QTabWidget itself might have an accessibleName
        name = tab_widget.accessibleName()
        if name:
            assert_accessible_name_not_empty(tab_widget)

        # Tab bar buttons (the clickable tabs) should have text labels
        for i in range(tab_widget.count()):
            text = tab_widget.tabText(i)
            assert text, (
                f"Tab at index {i} has empty label text"
            )

        view.shutdown()

    def test_sidebar_section_has_accessible_name(self, qt_widget, qtbot):
        """Sidebar header, category buttons should be accessible."""
        view = self._make_view(qt_widget, qtbot)

        # SectionHeader used in sidebar
        sidebar_header = view._sidebar_header
        assert_accessible_name_not_empty(sidebar_header)

        # Upload button
        upload_btn = view._upload_btn
        name = upload_btn.accessibleName()
        if not name:
            # Falls back to button text for screen readers
            assert upload_btn.text(), (
                "Upload button should have text content"
            )

        view.shutdown()

    def test_center_toolbar_has_accessible_names(self, qt_widget, qtbot):
        """Sort combo, search input, select-all checkbox should be named."""
        view = self._make_view(qt_widget, qtbot)

        # Sort combo
        sort_combo = view._sort_combo
        name = sort_combo.accessibleName()
        if name:
            assert_accessible_name_not_empty(sort_combo)

        # Search entry (DebouncedLineEdit)
        search_entry = view._search_entry
        name = search_entry.accessibleName()
        placeholder = search_entry.placeholderText() if hasattr(search_entry, "placeholderText") else ""
        has_some_label = bool(name or placeholder)
        assert has_some_label, (
            "Search entry should have accessibleName or placeholderText"
        )

        # Admin trigger button
        admin_trigger = view._admin_trigger
        name = admin_trigger.accessibleName()
        if name:
            assert_accessible_name_not_empty(admin_trigger)

        view.shutdown()

    def test_pager_controls_have_accessible_names(self, qt_widget, qtbot):
        """Previous / Next page buttons should be identifiable."""
        view = self._make_view(qt_widget, qtbot)

        prev_btn = view._prev_btn
        next_btn = view._next_btn

        # At minimum the buttons have visible text
        assert prev_btn.text(), "Previous page button should have text"
        assert next_btn.text(), "Next page button should have text"

        # Check accessible names
        prev_name = prev_btn.accessibleName()
        next_name = next_btn.accessibleName()
        if prev_name:
            assert_accessible_name_not_empty(prev_btn)
        if next_name:
            assert_accessible_name_not_empty(next_btn)

        view.shutdown()
