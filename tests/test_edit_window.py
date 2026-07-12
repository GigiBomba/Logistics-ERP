"""Tests for the Qt edit-window dialog.

Covers construction, UI layout, form fields, save logic
(including truck-number resolution), i18n lifecycle, and
error handling.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from ui.dialogs.edit_window import QtEditWindow
from ui.widgets import ActionButton, StyledLineEdit


# ── Helpers ──────────────────────────────────────────────────────────────

def _dummy_trip_data() -> dict:
    return {
        "truck_number": "AB-12-34",
        "driver_name": "John Doe",
        "client_name": "Acme Corp",
        "distance_km": 450,
        "net_profit": 1250.50,
    }


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def edit_window(qt_widget, qtbot):
    """Provide a properly mocked QtEditWindow instance."""
    db = MagicMock()
    trip_service = MagicMock()
    trip_service.get_by_id.return_value = _dummy_trip_data()

    with patch(
        "ui.dialogs.edit_window.TripService",
        return_value=trip_service,
    ):
        dlg = QtEditWindow(
            parent=qt_widget,
            db=db,
            trip_id=42,
            callback=MagicMock(),
        )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


# ── Tests ────────────────────────────────────────────────────────────────

class TestQtEditWindowInit:
    """Construction and initial state."""

    def test_creation(self, edit_window):
        assert isinstance(edit_window, QtEditWindow)
        assert edit_window.windowTitle() != ""

    def test_is_modal(self, edit_window):
        assert edit_window.windowModality() == Qt.ApplicationModal

    def test_minimum_size_set(self, edit_window):
        assert edit_window.minimumWidth() == 500
        assert edit_window.minimumHeight() == 600

    def test_trip_id_stored(self, edit_window):
        assert edit_window._trip_id == 42

    def test_callback_stored(self, edit_window):
        assert edit_window._callback is not None

    def test_trip_data_loaded(self, edit_window):
        assert edit_window._data["truck_number"] == "AB-12-34"

    def test_trip_data_loaded_from_service(self, edit_window):
        assert edit_window._data["driver_name"] == "John Doe"

    def test_i18n_listener_registered(self, edit_window):
        assert edit_window._language_callback is not None


class TestQtEditWindowUI:
    """UI element presence and layout."""

    def test_has_form_entries(self, edit_window):
        assert len(edit_window._entries) == 5
        for key in ("truck_number", "driver_name", "client_name", "distance_km", "net_profit"):
            assert key in edit_window._entries

    def test_entries_are_styled_line_edit(self, edit_window):
        for entry in edit_window._entries.values():
            assert isinstance(entry, StyledLineEdit)

    def test_form_fields_populated(self, edit_window):
        assert edit_window._entries["truck_number"].text() == "AB-12-34"
        assert edit_window._entries["driver_name"].text() == "John Doe"
        assert edit_window._entries["client_name"].text() == "Acme Corp"

    def test_has_save_button(self, edit_window):
        """Should have at least one ActionButton (the Save button)."""
        buttons = edit_window.findChildren(ActionButton)
        assert len(buttons) >= 1

    def test_save_button_displays_text(self, edit_window):
        texts = []
        for w in edit_window.findChildren(QPushButton):
            texts.append(w.text())
        combined = " ".join(texts).lower()
        assert "save" in combined or "salveaz" in combined

    def test_has_scrollable_form_container(self, edit_window):
        from ui.widgets import ScrollableFormContainer
        containers = edit_window.findChildren(ScrollableFormContainer)
        assert len(containers) >= 1


class TestQtEditWindowSave:
    """Save logic."""

    def test_save_calls_trip_service(self, edit_window):
        with patch.object(edit_window._trip_service, "update") as mock_update:
            edit_window._save()
            assert mock_update.called
            args, kwargs = mock_update.call_args
            assert args[0] == 42  # trip_id

    def test_save_calls_callback(self, edit_window):
        with patch.object(edit_window._trip_service, "update"):
            edit_window._save()
            edit_window._callback.assert_called_once()

    def test_save_accepts_dialog(self, edit_window):
        with patch.object(edit_window._trip_service, "update"):
            with patch.object(edit_window, "accept") as mock_accept:
                edit_window._save()
                mock_accept.assert_called_once()

    def test_save_collects_form_data(self, edit_window):
        edit_window._entries["truck_number"].setText("CD-56-78")
        with patch.object(edit_window._trip_service, "update") as mock_update:
            edit_window._save()
            _, kwargs = mock_update.call_args
            new_data = kwargs if len(mock_update.call_args[0]) <= 1 else mock_update.call_args[0][1]
            if len(mock_update.call_args[0]) > 1:
                new_data = mock_update.call_args[0][1]
            assert new_data.get("truck_number") == "CD-56-78"

    def test_save_resolves_truck_number_to_id(self, edit_window):
        """When truck_number changes, _save should resolve to truck_id."""
        with patch.object(edit_window._trip_service, "update"):
            with patch(
                "ui.dialogs.edit_window.FleetRepository",
            ) as mock_fleet_repo_cls:
                mock_repo = MagicMock()
                mock_repo.get_by_plate.return_value = {"id": 99}
                mock_fleet_repo_cls.return_value = mock_repo

                edit_window._entries["truck_number"].setText("CD-56-78")
                edit_window._save()
                mock_repo.get_by_plate.assert_called_once_with("CD-56-78")

    def test_save_truck_number_empty_sets_none(self, edit_window):
        with patch.object(edit_window._trip_service, "update") as mock_update:
            edit_window._entries["truck_number"].setText("")
            edit_window._save()
            _, kwargs = mock_update.call_args
            new_data = kwargs if len(mock_update.call_args[0]) <= 1 else mock_update.call_args[0][1]
            if len(mock_update.call_args[0]) > 1:
                new_data = mock_update.call_args[0][1]
            assert new_data.get("truck_id") is None

    def test_save_exception_shows_critical_message(self, edit_window):
        with patch.object(
            edit_window._trip_service, "update",
            side_effect=ValueError("DB failure"),
        ):
            with patch("ui.dialogs.edit_window.QMessageBox.critical") as mock_crit:
                edit_window._save()
                mock_crit.assert_called_once()

    def test_save_exception_does_not_accept(self, edit_window):
        with patch.object(
            edit_window._trip_service, "update",
            side_effect=ValueError("DB failure"),
        ):
            with patch.object(edit_window, "accept") as mock_accept:
                with patch("ui.dialogs.edit_window.QMessageBox.critical"):
                    edit_window._save()
                    mock_accept.assert_not_called()


class TestQtEditWindowI18n:
    """Internationalisation lifecycle."""

    def test_i18n_callback_updates_title(self, edit_window):
        edit_window._on_language_changed("ro")
        assert "42" in edit_window.windowTitle()

    def test_close_event_unregisters_listener(self, edit_window):
        with patch(
            "ui.dialogs.edit_window.unregister_listener",
        ) as mock_unreg:
            edit_window.close()
            mock_unreg.assert_called_once_with(edit_window._language_callback)

    def test_rebuild_form_labels_updates_labels(self, edit_window):
        edit_window._rebuild_form_labels()
        # Should not raise; labels get updated text
        for key, entry in edit_window._entries.items():
            parent = entry.parent()
            if parent and parent.layout():
                item = parent.layout().itemAt(0)
                if item and item.widget():
                    assert len(item.widget().text()) > 0


class TestQtEditWindowLifecycle:
    """Full lifecycle."""

    def test_construction_to_close(self, qt_widget, qtbot):
        db = MagicMock()
        trip_service = MagicMock()
        trip_service.get_by_id.return_value = _dummy_trip_data()
        with patch("ui.dialogs.edit_window.TripService", return_value=trip_service):
            dlg = QtEditWindow(parent=qt_widget, db=db, trip_id=1, callback=MagicMock())
        qtbot.addWidget(dlg)
        assert dlg._data is not None
        dlg.close()

    def test_save_modified_data(self, qt_widget, qtbot):
        db = MagicMock()
        trip_service = MagicMock()
        trip_service.get_by_id.return_value = _dummy_trip_data()
        callback = MagicMock()
        with patch("ui.dialogs.edit_window.TripService", return_value=trip_service):
            dlg = QtEditWindow(parent=qt_widget, db=db, trip_id=1, callback=callback)
        qtbot.addWidget(dlg)

        dlg._entries["driver_name"].setText("Jane Smith")
        with patch.object(dlg._trip_service, "update"):
            dlg._save()
            callback.assert_called_once()

        dlg.close()

    def test_multiple_saves(self, edit_window):
        with patch.object(edit_window._trip_service, "update"):
            edit_window._save()
            edit_window._save()
            assert edit_window._trip_service.update.call_count == 1
