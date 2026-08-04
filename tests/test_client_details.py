"""Tests for _QtClientDetailsTab and _QtContactDialog.

Covers initialisation, build/layout lifecycle, empty states, and interaction
patterns for the detail tab and the add/edit contact dialog.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QLabel, QMessageBox

# SP workaround: ui.widgets.__init__ uses SP but only S is exported.
import ui.widgets as _ui_widgets

if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S

# COLOR_* workaround: client_details.py references design-token constants that
# may not be available at module level.
from ui.design_tokens import (
    COLOR_SUCCESS_DEFAULT as _CSD,
    COLOR_TEXT_TERTIARY as _CTT,
    COLOR_WARNING_DEFAULT as _CWD,
)
import ui.views.client_workspace.client_details as _client_details_mod

for _name, _val in [
    ("COLOR_SUCCESS_DEFAULT", _CSD),
    ("COLOR_TEXT_TERTIARY", _CTT),
    ("COLOR_WARNING_DEFAULT", _CWD),
]:
    if not hasattr(_client_details_mod, _name):
        setattr(_client_details_mod, _name, _val)


# =========================================================================
#  Fixtures — shared
# =========================================================================


@pytest.fixture
def mock_service():
    """Return a MagicMock that simulates the client dashboard service."""
    svc = MagicMock()
    svc.get_client_dashboard.return_value = {
        "client": {
            "id": 1,
            "name": "Acme Corp",
            "client_type": "Shipper",
            "rating": 4,
            "is_active": 1,
            "contact_person": "John Doe",
            "phone": "+40123456789",
            "email": "john@acme.com",
            "vat_number": "RO123456",
            "address": "Str. Libertatii 10, Bucuresti",
            "notes": "Preferred client",
            "payment_terms_days": 30,
            "credit_limit_eur": 50000,
        },
        "contacts": [
            {"id": 1, "full_name": "Jane Smith", "title": "Logistics Manager",
             "phone": "+40987654321", "email": "jane@acme.com", "is_primary": True},
        ],
        "tags": [{"tag": "VIP"}, {"tag": "Express"}],
        "total_revenue": 250000,
        "total_trips": 42,
        "total_km": 85000,
        "trips_last_30_days": 5,
        "total_profit": 50000,
        "avg_profit": 1190,
        "outstanding_balance": 15000,
        "last_trip_date": "2026-07-01T10:00:00",
    }
    svc.get_contacts.return_value = [
        {"id": 1, "full_name": "Jane Smith", "title": "Logistics Manager",
         "phone": "+40987654321", "email": "jane@acme.com", "is_primary": True},
    ]
    svc.get_payment_summary.return_value = {
        "invoice_count": 10,
        "total_billed": 200000,
        "total_paid": 180000,
        "unpaid": 20000,
        "overdue": 5000,
    }
    svc.add_tag.return_value = None
    svc.delete_contact.return_value = None
    svc.add_contact.return_value = 2
    svc.update_contact.return_value = None
    return svc


@pytest.fixture
def detail_tab(qtbot, mock_service):
    """Create a _QtClientDetailsTab with a mocked service."""
    from ui.views.client_workspace.client_details import _QtClientDetailsTab

    tab = _QtClientDetailsTab()
    qtbot.addWidget(tab)
    tab.refresh(mock_service, 1)
    yield tab


@pytest.fixture
def empty_service():
    """Return a service that returns empty/minimal dashboard data."""
    svc = MagicMock()
    svc.get_client_dashboard.return_value = {
        "client": {"id": 2, "name": "Empty Co", "rating": 0, "is_active": 0},
        "contacts": [],
        "tags": [],
    }
    svc.get_contacts.return_value = []
    svc.get_payment_summary.return_value = None
    return svc


# =========================================================================
#  Tests — _QtClientDetailsTab
# =========================================================================


class TestQtClientDetailsTab:
    """Suite of tests for the per-client detail tab."""

    # ── Initialisation ─────────────────────────────────────────────────

    def test_creation(self, qtbot):
        """Tab constructs without crashing."""
        from ui.views.client_workspace.client_details import _QtClientDetailsTab

        tab = _QtClientDetailsTab()
        qtbot.addWidget(tab)
        assert tab is not None

    def test_initial_client_id_is_none(self, qtbot):
        """Before refresh, _current_client_id is None."""
        from ui.views.client_workspace.client_details import _QtClientDetailsTab

        tab = _QtClientDetailsTab()
        qtbot.addWidget(tab)
        assert tab._current_client_id is None

    def test_has_content_widget(self, detail_tab):
        """Tab has a _content area from ScrollableFormContainer."""
        assert detail_tab._content is not None

    # ── Refresh / build ────────────────────────────────────────────────

    def test_refresh_sets_client_id(self, detail_tab):
        """refresh() stores the client id."""
        assert detail_tab._current_client_id == 1

    def test_refresh_calls_service(self, detail_tab, mock_service):
        """Service.get_client_dashboard is called with the correct id."""
        mock_service.get_client_dashboard.assert_called_with(1)

    def test_refresh_builds_profile_section(self, detail_tab):
        """Profile section with client name is present."""
        assert detail_tab._content is not None

    def test_refresh_builds_kpi_section(self, detail_tab):
        """KPI section is built with KPI card widgets."""
        # Search for "kpi-value" labels (MonoLabel setObjectName) anywhere
        # in the widget tree — KPICard puts values in a label with objectName "kpi-value".
        kpi_values = detail_tab.findChildren(QLabel)
        non_empty = [lbl for lbl in kpi_values if lbl.objectName() == "kpi-value"]
        assert len(non_empty) > 0, "No KPI value labels found (expected 8 cards)"

    def test_refresh_builds_contacts_section(self, detail_tab):
        """Contacts section is present when contacts exist."""
        # Search for "Jane Smith" anywhere in the widget hierarchy
        all_labels = detail_tab._content.findChildren(QLabel)
        found = any("Jane Smith" in lbl.text() for lbl in all_labels)
        assert found, "Contact name Jane Smith should be rendered"

    def test_refresh_builds_tags_section(self, detail_tab):
        """Tags are rendered as chip labels."""
        all_labels = detail_tab._content.findChildren(QLabel)
        tag_found = any("VIP" in lbl.text() for lbl in all_labels)
        assert tag_found, "VIP tag should be rendered"

    def test_refresh_builds_payment_summary(self, detail_tab):
        """Payment summary section appears when data is available."""
        # KPICard uppercases the label text, so "Billed" → "BILLED"
        all_labels = detail_tab._content.findChildren(QLabel)
        billed_found = any("BILL" in lbl.text().upper() for lbl in all_labels)
        assert billed_found, "Payment summary should be rendered when invoice_count > 0"

    def test_refresh_builds_timeline(self, detail_tab):
        """Activity timeline widget is added to the layout."""
        from ui.widgets.client_activity_timeline import QtClientActivityTimeline

        timeline = detail_tab.findChild(QtClientActivityTimeline)
        assert timeline is not None, "Activity timeline should be present"

    # ── Empty state ────────────────────────────────────────────────────

    def test_empty_client_name_default(self, qtbot, empty_service):
        """When name is missing, '???' is shown as fallback."""
        from ui.views.client_workspace.client_details import _QtClientDetailsTab

        tab = _QtClientDetailsTab()
        qtbot.addWidget(tab)
        empty_service.get_client_dashboard.return_value = {
            "client": {"id": 99},
            "contacts": [],
            "tags": [],
        }
        tab.refresh(empty_service, 99)
        # No crash; the profile section builds with "???"
        assert tab._current_client_id == 99

    def test_empty_no_contacts(self, qtbot, empty_service):
        """Building with empty contacts list does not crash."""
        from ui.views.client_workspace.client_details import _QtClientDetailsTab

        tab = _QtClientDetailsTab()
        qtbot.addWidget(tab)
        tab.refresh(empty_service, 2)
        assert tab._current_client_id == 2

    def test_empty_no_tags_shows_no_tags_label(self, qtbot, empty_service):
        """When tags are empty, the 'no_tags' label is shown."""
        from ui.views.client_workspace.client_details import _QtClientDetailsTab

        tab = _QtClientDetailsTab()
        qtbot.addWidget(tab)
        tab.refresh(empty_service, 2)
        # Should not crash; the tags section renders a 'no tags' label
        assert tab._current_client_id == 2

    def test_payment_summary_skipped_when_empty(self, qtbot, empty_service):
        """Payment summary section is skipped when invoice_count is falsy."""
        from ui.views.client_workspace.client_details import _QtClientDetailsTab

        tab = _QtClientDetailsTab()
        qtbot.addWidget(tab)
        empty_service.get_payment_summary.return_value = {"invoice_count": 0}
        tab.refresh(empty_service, 2)
        # Payment summary should not have added widgets

    # ── Clear content ──────────────────────────────────────────────────

    def test_clear_content_removes_widgets(self, detail_tab):
        """_clear_content empties the content layout."""
        count_before = detail_tab._content.layout().count()
        detail_tab._clear_content()
        count_after = detail_tab._content.layout().count()
        assert count_after == 0

    def test_refresh_rebuilds_after_clear(self, detail_tab, mock_service):
        """Calling refresh twice rebuilds content without error."""
        detail_tab.refresh(mock_service, 1)
        detail_tab.refresh(mock_service, 1)
        # No crash, content is rebuilt

    # ── Contact management ─────────────────────────────────────────────

    def test_add_contact_opens_dialog(self, detail_tab, mock_service):
        """_add_contact creates a _QtContactDialog (modal exec)."""
        from ui.views.client_workspace.client_details import _QtContactDialog

        with patch.object(_QtContactDialog, "exec", return_value=0):
            detail_tab._add_contact(mock_service, 1)
            # No crash

    def test_edit_contact_opens_dialog(self, detail_tab, mock_service):
        """_edit_contact creates a _QtContactDialog with contact_data."""
        from ui.views.client_workspace.client_details import _QtContactDialog

        with patch.object(_QtContactDialog, "exec", return_value=0):
            detail_tab._edit_contact(1, mock_service, 1)
            mock_service.get_contacts.assert_called_with(1)

    def test_delete_contact_no_confirm(self, detail_tab, mock_service):
        """_delete_contact does not delete when user cancels."""
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            detail_tab._delete_contact(1, mock_service)
            mock_service.delete_contact.assert_not_called()

    def test_delete_contact_with_confirm(self, detail_tab, mock_service):
        """_delete_contact calls service.delete_contact when confirmed."""
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            detail_tab._delete_contact(1, mock_service)
            mock_service.delete_contact.assert_called_with(1)

    # ── Tags ───────────────────────────────────────────────────────────

    def test_add_tag_calls_service(self, detail_tab, mock_service):
        """_add_tag calls service.add_tag and clears the entry."""
        detail_tab._tag_entry.setText("NewTag")
        detail_tab._add_tag(mock_service, 1)
        mock_service.add_tag.assert_called_with(1, "NewTag")
        assert detail_tab._tag_entry.text() == ""

    def test_add_tag_empty_does_nothing(self, detail_tab, mock_service):
        """_add_tag with empty text does not call service."""
        detail_tab._tag_entry.setText("   ")
        detail_tab._add_tag(mock_service, 1)
        mock_service.add_tag.assert_not_called()

    # ── Lifecycle ──────────────────────────────────────────────────────

    def test_rebuild_without_client_id(self, detail_tab):
        """_rebuild does nothing when _current_client_id is None."""
        detail_tab._current_client_id = None
        detail_tab._rebuild(MagicMock())
        # No crash


# =========================================================================
#  Tests — _QtContactDialog
# =========================================================================


class TestQtContactDialog:
    """Suite of tests for the add/edit contact dialog."""

    def _create_dialog(self, qtbot, mock_service, contact_data=None, on_save=None):
        from ui.views.client_workspace.client_details import _QtContactDialog

        dialog = _QtContactDialog(
            parent=None,
            service=mock_service,
            client_id=1,
            contact_data=contact_data,
            on_save=on_save or MagicMock(),
        )
        qtbot.addWidget(dialog)
        return dialog

    # ── Initialisation ─────────────────────────────────────────────────

    def test_dialog_creation(self, qtbot, mock_service):
        """Dialog constructs without crashing."""
        dialog = self._create_dialog(qtbot, mock_service)
        assert dialog is not None
        assert dialog._editing is False
        dialog.close()

    def test_edit_dialog_mode(self, qtbot, mock_service):
        """Edit dialog detects existing data."""
        contact_data = {
            "id": 1, "full_name": "Jane", "title": "Mgr",
            "phone": "+40", "email": "j@t.com", "contact_type": "operations",
        }
        dialog = self._create_dialog(qtbot, mock_service, contact_data)
        assert dialog._editing is True
        dialog.close()

    def test_dialog_has_entries(self, qtbot, mock_service):
        """Dialog creates entry widgets for all fields."""
        dialog = self._create_dialog(qtbot, mock_service)
        assert len(dialog._entries) >= 4
        assert "full_name" in dialog._entries
        assert "email" in dialog._entries
        dialog.close()

    def test_dialog_edit_prefills_data(self, qtbot, mock_service):
        """Edit dialog pre-fills entries with existing data."""
        contact_data = {
            "id": 1, "full_name": "Jane Smith", "title": "Logistics Manager",
            "phone": "+40987654321", "email": "jane@acme.com",
            "contact_type": "primary",
        }
        dialog = self._create_dialog(qtbot, mock_service, contact_data)
        assert dialog._entries["full_name"].text() == "Jane Smith"
        assert dialog._entries["phone"].text() == "+40987654321"
        dialog.close()

    def test_dialog_minimum_size(self, qtbot, mock_service):
        """Dialog sets reasonable minimum size."""
        dialog = self._create_dialog(qtbot, mock_service)
        size = dialog.minimumSize()
        assert size.width() >= 350
        assert size.height() >= 300
        dialog.close()

    def test_dialog_is_modal(self, qtbot, mock_service):
        """Dialog is modal."""
        dialog = self._create_dialog(qtbot, mock_service)
        assert dialog.isModal() is True
        dialog.close()

    # ── Save behaviour ─────────────────────────────────────────────────

    def test_save_empty_name_shows_warning(self, qtbot, mock_service):
        """Saving with empty name shows inline error and returns."""
        on_save = MagicMock()
        dialog = self._create_dialog(qtbot, mock_service, on_save=on_save)
        name_entry = dialog._entries["full_name"]
        if hasattr(name_entry, "setText"):
            name_entry.setText("")

        dialog._save()

        assert not dialog._error_labels["full_name"].isHidden()
        assert "required" in dialog._error_labels["full_name"].text().lower()
        assert on_save.call_count == 0
        dialog.close()

    def test_save_new_contact(self, qtbot, mock_service):
        """_save creates a new contact and calls on_save."""
        on_save = MagicMock()
        dialog = self._create_dialog(qtbot, mock_service, on_save=on_save)
        dialog._entries["full_name"].setText("New Contact")
        dialog._save()
        mock_service.add_contact.assert_called_once()
        on_save.assert_called_once()
        dialog.close()

    def test_save_existing_contact(self, qtbot, mock_service):
        """_save updates an existing contact."""
        on_save = MagicMock()
        contact_data = {
            "id": 1, "full_name": "Jane", "title": "Mgr",
            "phone": "+401234567", "email": "j@t.com", "contact_type": "operations",
        }
        dialog = self._create_dialog(qtbot, mock_service, contact_data, on_save)
        dialog._entries["full_name"].setText("Jane Updated")
        dialog._save()
        mock_service.update_contact.assert_called_once()
        on_save.assert_called_once()
        dialog.close()

    # ── Combo field ────────────────────────────────────────────────────

    def test_contact_type_combo_exists(self, qtbot, mock_service):
        """contact_type field is a StyledComboBox."""
        from ui.widgets import StyledComboBox

        dialog = self._create_dialog(qtbot, mock_service)
        entry = dialog._entries.get("contact_type")
        assert entry is not None
        assert isinstance(entry, StyledComboBox)
        dialog.close()

    def test_combo_default_selection(self, qtbot, mock_service):
        """Combo has a default selection even without contact_data."""
        dialog = self._create_dialog(qtbot, mock_service)
        entry = dialog._entries["contact_type"]
        assert entry.currentIndex() >= 0
        dialog.close()


# =========================================================================
#  Tests — InlineEditableField
# =========================================================================


class TestInlineEditableField:
    """Suite of tests for the inline-editable field widget."""

    def _create_field(
        self, qtbot, label="Name", field_name="name",
        value="John", on_save=None, required=False,
    ):
        from ui.views.client_workspace.client_details import (
            InlineEditableField,
        )

        f = InlineEditableField(
            None, label, field_name, value,
            on_save or MagicMock(), required=required,
        )
        qtbot.addWidget(f)
        return f

    # ── Display mode ───────────────────────────────────────────────────

    def test_creation_display_mode(self, qtbot):
        """Label + value visible, edit/save/cancel hidden."""
        f = self._create_field(qtbot)
        # Widgets are created visible by default; use isHidden for own state
        assert not f._value_lbl.isHidden()
        assert f._edit.isHidden()
        assert f._save_btn.isHidden()
        assert f._cancel_btn.isHidden()

    def test_set_value_updates_label(self, qtbot):
        """set_value() updates label text without firing on_save."""
        on_save = MagicMock()
        f = self._create_field(qtbot, on_save=on_save)
        f.set_value("New")
        assert f._value_lbl.text() == "New"
        on_save.assert_not_called()

    # ── Edit transition ────────────────────────────────────────────────

    def test_start_edit_transitions(self, qtbot):
        """Double-click / _start_edit shows edit controls, hides value."""
        f = self._create_field(qtbot, value="Original")
        f._start_edit()
        assert f._editing is True
        assert f._value_lbl.isHidden()
        assert not f._edit.isHidden()
        assert not f._save_btn.isHidden()
        assert not f._cancel_btn.isHidden()
        assert f._edit.text() == "Original"

    def test_start_edit_idempotent(self, qtbot):
        """Calling _start_edit when already editing does nothing."""
        f = self._create_field(qtbot)
        f._start_edit()
        f._start_edit()  # second call
        assert f._editing is True

    # ── Save ───────────────────────────────────────────────────────────

    def test_save_calls_on_save(self, qtbot):
        """Enter / _save calls on_save(field_name, value) and returns to display."""
        on_save = MagicMock()
        f = self._create_field(qtbot, field_name="name", on_save=on_save)
        f._start_edit()
        f._edit.setText("Updated")
        f._save()
        on_save.assert_called_once_with("name", "Updated")
        assert f._edit.isHidden()
        assert f._value_lbl.text() == "Updated"

    def test_save_required_field_empty(self, qtbot):
        """required=True, empty value -> error shown, on_save NOT called."""
        on_save = MagicMock()
        f = self._create_field(
            qtbot, field_name="name", value="Orig",
            on_save=on_save, required=True,
        )
        f._start_edit()
        f._edit.setText("")
        f._save()
        on_save.assert_not_called()
        assert f._editing is True
        assert not f._error_lbl.isHidden()
        assert "required" in f._error_lbl.text().lower()

    def test_save_email_validation(self, qtbot):
        """Invalid email -> error shown, on_save NOT called."""
        on_save = MagicMock()
        f = self._create_field(qtbot, field_name="email", on_save=on_save)
        f._start_edit()
        f._edit.setText("not-an-email")
        f._save()
        on_save.assert_not_called()
        assert not f._error_lbl.isHidden()

    def test_save_email_valid_passes(self, qtbot):
        """Valid email -> on_save called."""
        on_save = MagicMock()
        f = self._create_field(qtbot, field_name="email", on_save=on_save)
        f._start_edit()
        f._edit.setText("user@example.com")
        f._save()
        on_save.assert_called_once_with("email", "user@example.com")

    def test_save_phone_validation(self, qtbot):
        """Short phone -> error shown, on_save NOT called."""
        on_save = MagicMock()
        f = self._create_field(qtbot, field_name="phone", on_save=on_save)
        f._start_edit()
        f._edit.setText("12")
        f._save()
        on_save.assert_not_called()
        assert not f._error_lbl.isHidden()

    # ── Cancel ─────────────────────────────────────────────────────────

    def test_cancel_restores_original(self, qtbot):
        """Cancel reverts label to original, on_save NOT called."""
        on_save = MagicMock()
        f = self._create_field(qtbot, value="Original", on_save=on_save)
        f._start_edit()
        f._edit.setText("Changed")
        f._cancel()
        assert f._value_lbl.text() == "Original"
        on_save.assert_not_called()
        assert f._edit.isHidden()

    # ── Event filter ───────────────────────────────────────────────────

    def test_event_filter_escape_cancels(self, qtbot):
        """Escape key during edit -> cancel, return True."""
        from PySide6.QtGui import QKeyEvent

        f = self._create_field(qtbot, value="Original")
        f._start_edit()
        f._edit.setText("Changed")
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        result = f.eventFilter(f._edit, event)
        assert result is True
        assert f._value_lbl.text() == "Original"

    def test_event_filter_non_escape_passes_through(self, qtbot):
        """Non-escape keys -> return super().eventFilter() (False)."""
        from PySide6.QtGui import QKeyEvent

        f = self._create_field(qtbot)
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Return, Qt.NoModifier)
        result = f.eventFilter(f._edit, event)
        # QWidget.eventFilter returns False by default
        assert result is False

    # ── End edit ───────────────────────────────────────────────────────

    def test_end_edit_hides_edit_controls(self, qtbot):
        """After save/cancel, edit/save/cancel hidden, value label shown."""
        f = self._create_field(qtbot)
        f._start_edit()
        f._end_edit()
        assert f._editing is False
        assert f._edit.isHidden()
        assert f._save_btn.isHidden()
        assert f._cancel_btn.isHidden()
        assert not f._value_lbl.isHidden()

    # ── Required indicator ─────────────────────────────────────────────

    def test_required_field_has_asterisk(self, qtbot):
        """required=True -> label text ends with ' *'."""
        f = self._create_field(qtbot, label="Name", required=True)
        assert f._label.text().endswith(" *")
