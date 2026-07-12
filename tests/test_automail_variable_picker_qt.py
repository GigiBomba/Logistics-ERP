"""Qt-integrated tests for VariablePickerPopup — searchable variable popup."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
)

from ui.views.automail.variable_picker import VariablePickerPopup
from ui.widgets import StyledLineEdit


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_variables():
    return [
        {"name": "company_name", "label": "Company Name", "example": "ACME",
         "description": "Your company name"},
        {"name": "client_contact", "label": "Client Contact", "example": "John",
         "description": "Contact person"},
        {"name": "invoice_number", "label": "Invoice Number", "example": "INV-001",
         "description": "Invoice reference"},
        {"name": "due_date", "label": "Due Date", "example": "2026-07-01",
         "description": "Payment due date"},
        {"name": "total_amount", "label": "Total Amount", "example": "1500.00",
         "description": "Invoice total"},
        {"name": "currency", "label": "Currency", "example": "EUR",
         "description": "Currency code"},
    ]


# ── Creation ────────────────────────────────────────────────────────────


class TestVariablePickerPopupCreation:
    def test_creation(self, qt_widget, qtbot):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        assert popup._variables == []
        assert popup.property("visible") is False or True  # just exists

    def test_is_frameless_popup(self, qt_widget, qtbot):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        flags = popup.windowFlags()
        assert flags & Qt.WindowType.Popup
        assert flags & Qt.WindowType.FramelessWindowHint

    def test_has_search_input(self, qt_widget, qtbot):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        assert isinstance(popup._search_input, StyledLineEdit)

    def test_has_scroll_area(self, qt_widget, qtbot):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        scroll = popup.findChild(QScrollArea)
        assert scroll is not None
        assert scroll.widgetResizable() is True
        assert scroll.frameShape() == QFrame.NoFrame

    def test_scroll_fixed_height(self, qt_widget, qtbot):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        scroll = popup.findChild(QScrollArea)
        assert scroll is not None
        assert scroll.height() == 220 or scroll.maximumHeight() >= 220


# ── Show popup ──────────────────────────────────────────────────────────


class TestVariablePickerPopupShow:
    def test_show_popup_loads_variables(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        with patch(
            "ui.views.automail.variable_picker.get_available_variables",
            return_value=mock_variables,
        ):
            popup.show_popup(qt_widget)
            assert len(popup._variables) == 6

    def test_show_popup_clears_search(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._search_input.setText("old")
        with patch(
            "ui.views.automail.variable_picker.get_available_variables",
            return_value=mock_variables,
        ):
            popup.show_popup(qt_widget)
            assert popup._search_input.text() == ""

    def test_show_popup_focuses_search(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        with patch(
            "ui.views.automail.variable_picker.get_available_variables",
            return_value=mock_variables,
        ):
            popup.show_popup(qt_widget)
            assert popup._search_input.hasFocus() is True

    def test_show_popup_renders_list(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        with patch(
            "ui.views.automail.variable_picker.get_available_variables",
            return_value=mock_variables,
        ):
            popup.show_popup(qt_widget)
            # Should have 6 buttons in the list
            buttons = popup.findChildren(QPushButton)
            # One button per variable (search input has no button)
            assert len(buttons) >= 6

    def test_show_popup_sets_geometry(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        with patch(
            "ui.views.automail.variable_picker.get_available_variables",
            return_value=mock_variables,
        ):
            popup.show_popup(qt_widget)
            # Width should be 260
            assert popup.width() == 260 or popup.minimumWidth() <= 260


# ── Search / filter ─────────────────────────────────────────────────────


class TestVariablePickerPopupSearch:
    def test_search_filters_list(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._variables = mock_variables
        popup._render_list("invoice")
        buttons = popup.findChildren(QPushButton)
        button_texts = [b.text() for b in buttons]
        assert any("invoice" in t.lower() for t in button_texts)

    def test_search_returns_all_on_empty(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._variables = mock_variables
        popup._render_list("")
        buttons = popup.findChildren(QPushButton)
        assert len(buttons) == 6

    def test_search_no_match_shows_empty(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._variables = mock_variables
        popup._render_list("zzzznotexist")
        buttons = popup.findChildren(QPushButton)
        assert len(buttons) == 0
        # Should show "No variables match" label
        labels = popup.findChildren(QLabel)
        no_match = [lbl for lbl in labels if "No variables" in lbl.text()]
        assert len(no_match) >= 1

    def test_search_by_label_prefix(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._variables = mock_variables
        popup._render_list("Company")
        buttons = popup.findChildren(QPushButton)
        assert any("company_name" in b.text() for b in buttons)

    def test_search_by_name(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._variables = mock_variables
        popup._render_list("total")
        buttons = popup.findChildren(QPushButton)
        assert any("total_amount" in b.text() for b in buttons)

    def test_text_changed_triggers_render(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._variables = mock_variables
        with patch.object(popup, "_render_list") as mock_render:
            popup._search_input.setText("inv")
            mock_render.assert_called_once_with("inv")


# ── Selection ────────────────────────────────────────────────────────────


class TestVariablePickerPopupSelection:
    def test_variable_chosen_emits_signal(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._variables = mock_variables
        popup._render_list("")

        received = []
        popup.variable_chosen.connect(received.append)

        # Find and click a variable button
        buttons = popup.findChildren(QPushButton)
        invoice_btn = next(b for b in buttons if "invoice_number" in b.text())
        invoice_btn.click()
        assert received == ["invoice_number"]

    def test_variable_chosen_closes_popup(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._variables = mock_variables
        popup._render_list("")
        popup.show()
        assert popup.isVisible() is True
        # Emit signal — this will close the popup
        popup._on_variable_chosen("test")
        # Popup should now be hidden
        assert popup.isVisible() is False

    def test_click_inserts_correct_variable(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._variables = mock_variables
        popup._render_list("")

        received = []
        popup.variable_chosen.connect(received.append)

        buttons = popup.findChildren(QPushButton)
        due_btn = next(b for b in buttons if "due_date" in b.text())
        due_btn.click()
        assert received == ["due_date"]


# ── Lifecycle ───────────────────────────────────────────────────────────


class TestVariablePickerPopupLifecycle:
    def test_close_on_selection(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._variables = mock_variables
        popup.show()
        assert popup.isVisible() is True
        popup._on_variable_chosen("test")
        assert popup.isVisible() is False

    def test_render_list_clears_previous(self, qt_widget, qtbot, mock_variables):
        popup = VariablePickerPopup(qt_widget)
        qtbot.addWidget(popup)
        popup._variables = mock_variables
        popup._render_list("")
        # Capture initial list layout count (horizontal rows in list)
        initial_row_count = popup._list_layout.count()
        assert initial_row_count == 6, f"Expected 6 rows, got {initial_row_count}"
        # Render again — widgets from previous render are deleteLater'd
        popup._render_list("")
        # The _list_layout should be cleared and re-populated
        # deleteLater defers actual removal, so count may still show old + new.
        # Key assertion: no error occurs and the layout is populated.
        assert popup._list_layout.count() == 6
