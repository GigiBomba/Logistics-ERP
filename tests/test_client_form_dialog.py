"""Tests for QtClientFormDialog — client add/edit dialog.

Separated from ``test_client_manager_view.py`` because running both in the
same pytest session can trigger Qt event-loop interference.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_client_service():
    svc = MagicMock()
    svc.get_all.return_value = []
    svc.search.return_value = []
    svc.get_trip_count.return_value = 0
    svc.create.return_value = 1
    svc._repo.get_by_name.return_value = None
    return svc


# =========================================================================
# Tests
# =========================================================================


class TestQtClientFormDialog:
    """Suite of tests for the client add/edit dialog."""

    def _create_dialog(self, qtbot, mock_client_service, client_data=None):
        from ui.views.client_manager import QtClientFormDialog

        dialog = QtClientFormDialog(
            parent=None,
            service=mock_client_service,
            client_data=client_data,
            on_save=MagicMock(),
        )
        qtbot.addWidget(dialog)
        return dialog

    def test_dialog_creation(self, qtbot, mock_client_service):
        """Dialog constructs without crashing."""
        dialog = self._create_dialog(qtbot, mock_client_service)
        assert dialog is not None
        assert dialog._editing is False
        dialog.close()

    def test_edit_dialog_mode(self, qtbot, mock_client_service):
        """Edit dialog detects existing data."""
        client_data = {"id": 1, "name": "Test", "contact_person": "",
                       "phone": "", "email": "", "address": "",
                       "vat_number": "", "notes": ""}
        dialog = self._create_dialog(qtbot, mock_client_service, client_data)
        assert dialog._editing is True
        dialog.close()

    def test_dialog_has_entries(self, qtbot, mock_client_service):
        """Dialog creates entry widgets for all fields."""
        dialog = self._create_dialog(qtbot, mock_client_service)
        assert len(dialog._entries) >= 4
        assert "name" in dialog._entries
        assert "phone" in dialog._entries
        dialog.close()

    def test_dialog_edit_prefills_data(self, qtbot, mock_client_service):
        """Edit dialog pre-fills entries with existing data."""
        client_data = {
            "id": 1, "name": "Existing", "contact_person": "Contact",
            "phone": "+40123", "email": "e@test.com", "address": "Addr",
            "vat_number": "RO123", "notes": "Note",
        }
        dialog = self._create_dialog(qtbot, mock_client_service, client_data)
        assert dialog._entries["name"].text() == "Existing"
        assert dialog._entries["phone"].text() == "+40123"
        dialog.close()

    def test_save_empty_name_shows_warning(self, qtbot, mock_client_service, monkeypatch):
        """Saving with empty name shows warning and returns."""
        monkeypatch.setattr("ui.views.client_manager.QMessageBox", MagicMock())
        dialog = self._create_dialog(qtbot, mock_client_service)
        dialog._entries["name"].setText("")
        dialog._save()
        assert dialog.on_save.call_count == 0
        dialog.close()

    def test_save_new_client(self, qtbot, mock_client_service):
        """_save creates a new client and calls on_save."""
        mock_client_service.create.return_value = 1
        mock_client_service._repo.get_by_name.return_value = None

        dialog = self._create_dialog(qtbot, mock_client_service)
        dialog._entries["name"].setText("New Client")
        dialog._entries["phone"].setText("+4012345")
        dialog._save()

        mock_client_service.create.assert_called()
        dialog.on_save.assert_called_once()
        dialog.close()

    def test_save_duplicate_name_shows_warning(self, qtbot, mock_client_service, monkeypatch):
        """_save shows warning when duplicate name exists."""
        monkeypatch.setattr("ui.views.client_manager.QMessageBox", MagicMock())
        mock_client_service._repo.get_by_name.return_value = {"id": 99, "name": "Existing"}

        dialog = self._create_dialog(qtbot, mock_client_service)
        dialog._entries["name"].setText("Existing")
        dialog._save()

        assert mock_client_service.create.call_count == 0
        assert dialog.on_save.call_count == 0
        dialog.close()

    def test_save_existing_client(self, qtbot, mock_client_service):
        """_save updates an existing client."""
        client_data = {
            "id": 1, "name": "Existing", "contact_person": "",
            "phone": "", "email": "", "address": "",
            "vat_number": "", "notes": "",
        }
        dialog = self._create_dialog(qtbot, mock_client_service, client_data)
        dialog._entries["name"].setText("Updated Name")
        dialog._save()
        mock_client_service.update.assert_called()
        dialog.on_save.assert_called_once()
        dialog.close()

    def test_dialog_minimum_size(self, qtbot, mock_client_service):
        """Dialog sets reasonable minimum size."""
        dialog = self._create_dialog(qtbot, mock_client_service)
        size = dialog.minimumSize()
        assert size.width() >= 400
        assert size.height() >= 400
        dialog.close()

    def test_dialog_is_modal(self, qtbot, mock_client_service):
        """Dialog is modal."""
        dialog = self._create_dialog(qtbot, mock_client_service)
        assert dialog.isModal() is True
        dialog.close()
