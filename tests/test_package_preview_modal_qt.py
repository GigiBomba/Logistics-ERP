"""Tests for PackagePreviewDialog — trip document reordering modal."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QPushButton,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_trip_repo():
    repo = MagicMock()
    repo.get_by_id.return_value = {
        "id": 42,
        "client_name": "TestClient",
        "start_date": "2025-01-01",
        "end_date": "2025-01-10",
    }
    return repo


@pytest.fixture
def mock_doc_repo():
    return MagicMock()


@pytest.fixture
def mock_documents():
    return [
        {"id": "1", "title": "Invoice", "file_name": "invoice.pdf", "file_size": 204800},
        {"id": "2", "title": "CMR", "file_name": "cmr.pdf", "file_size": 10240},
    ]


@pytest.fixture
def dialog_no_trip(qt_widget, qtbot):
    """PackagePreviewDialog without a trip_id."""
    from ui.views.package_preview_modal import PackagePreviewDialog

    dlg = PackagePreviewDialog(
        parent=qt_widget,
        db=MagicMock(),
        trip_id=None,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


@pytest.fixture
def dialog_with_trip(qt_widget, qtbot, mock_trip_repo, mock_doc_repo, mock_documents):
    """PackagePreviewDialog with a trip_id and mocked documents."""
    from ui.views.package_preview_modal import PackagePreviewDialog

    with patch(
        "ui.views.package_preview_modal.PackageBuilder",
    ) as mock_builder_cls:
        mock_builder = mock_builder_cls.return_value
        mock_builder.list_trip_documents.return_value = mock_documents

        dlg = PackagePreviewDialog(
            parent=qt_widget,
            db=MagicMock(),
            trip_id=42,
            trip_repo=mock_trip_repo,
            doc_repo=mock_doc_repo,
        )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


@pytest.fixture
def dialog_empty(qt_widget, qtbot):
    """PackagePreviewDialog with a trip_id that returns no documents."""
    from ui.views.package_preview_modal import PackagePreviewDialog

    with patch(
        "ui.views.package_preview_modal.PackageBuilder",
    ) as mock_builder_cls:
        mock_builder = mock_builder_cls.return_value
        mock_builder.list_trip_documents.return_value = []

        dlg = PackagePreviewDialog(
            parent=qt_widget,
            db=MagicMock(),
            trip_id=99,
        )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


# =========================================================================
# Tests
# =========================================================================


class TestPackagePreviewDialogInit:
    """Construction and basic attributes."""

    def test_creation_no_trip(self, dialog_no_trip):
        assert dialog_no_trip is not None
        assert dialog_no_trip.trip_id is None

    def test_creation_with_trip(self, dialog_with_trip):
        assert dialog_with_trip is not None
        assert dialog_with_trip.trip_id == 42
        assert dialog_with_trip._trip_repo is not None
        assert dialog_with_trip._doc_repo is not None

    def test_dialog_not_modal_by_default(self, dialog_no_trip):
        """PackagePreviewDialog is not modal (caller decides modality)."""
        # QDialog default is non-modal — the test validates the default
        assert not dialog_no_trip.isModal()

    def test_minimum_size_set(self, dialog_no_trip):
        assert dialog_no_trip.minimumSize().width() >= 640
        assert dialog_no_trip.minimumSize().height() >= 480


class TestPackagePreviewDialogUiElements:
    """Verify UI widgets are present and configured."""

    def test_header_label_exists(self, dialog_no_trip):
        assert hasattr(dialog_no_trip, "_header")
        assert isinstance(dialog_no_trip._header, QLabel)

    def test_list_widget_exists(self, dialog_no_trip):
        assert hasattr(dialog_no_trip, "_list")
        assert isinstance(dialog_no_trip._list, QListWidget)

    def test_up_button_exists(self, dialog_no_trip):
        assert hasattr(dialog_no_trip, "_up_btn")
        assert isinstance(dialog_no_trip._up_btn, QPushButton)

    def test_down_button_exists(self, dialog_no_trip):
        assert hasattr(dialog_no_trip, "_down_btn")
        assert isinstance(dialog_no_trip._down_btn, QPushButton)

    def test_download_zip_button_exists(self, dialog_no_trip):
        assert hasattr(dialog_no_trip, "_download_zip_btn")
        assert isinstance(dialog_no_trip._download_zip_btn, QPushButton)

    def test_download_pdf_button_exists(self, dialog_no_trip):
        assert hasattr(dialog_no_trip, "_download_pdf_btn")
        assert isinstance(dialog_no_trip._download_pdf_btn, QPushButton)

    def test_continue_button_exists(self, dialog_no_trip):
        assert hasattr(dialog_no_trip, "_continue_btn")
        assert isinstance(dialog_no_trip._continue_btn, QPushButton)

    def test_cancel_button_exists(self, dialog_no_trip):
        assert hasattr(dialog_no_trip, "_cancel_btn")
        assert isinstance(dialog_no_trip._cancel_btn, QPushButton)

    def test_list_drag_drop_mode(self, dialog_no_trip):
        assert dialog_no_trip._list.dragDropMode() == QAbstractItemView.InternalMove


class TestPackagePreviewDialogDocumentLoading:
    """Document loading and list population."""

    def test_empty_state_placeholder(self, dialog_empty):
        """When no documents, a placeholder item is shown and Continue is disabled."""
        assert dialog_empty._list.count() >= 1
        assert not dialog_empty._continue_btn.isEnabled()

    def test_documents_populated(self, dialog_with_trip):
        """Documents appear in the list when trip has documents."""
        assert dialog_with_trip._list.count() == 2
        assert dialog_with_trip._continue_btn.isEnabled()

    def test_document_item_has_user_data(self, dialog_with_trip):
        """Each list item stores the document ID in Qt.UserRole."""
        item0 = dialog_with_trip._list.item(0)
        assert item0.data(Qt.UserRole) == 1
        item1 = dialog_with_trip._list.item(1)
        assert item1.data(Qt.UserRole) == 2

    def test_loaded_documents_by_id_populated(self, dialog_with_trip):
        assert len(dialog_with_trip._documents_by_id) == 2
        assert 1 in dialog_with_trip._documents_by_id
        assert 2 in dialog_with_trip._documents_by_id


class TestPackagePreviewDialogReorder:
    """Move up/down operations."""

    def test_move_up_first_item_noop(self, dialog_with_trip):
        """Moving up the first item does nothing."""
        dialog_with_trip._list.setCurrentRow(0)
        original_order = dialog_with_trip._doc_ids.copy()
        dialog_with_trip._on_move_up()
        assert dialog_with_trip._doc_ids == original_order

    def test_move_down_second_item(self, dialog_with_trip):
        """Moving down the first item swaps positions."""
        dialog_with_trip._list.setCurrentRow(0)
        dialog_with_trip._on_move_down()
        assert dialog_with_trip._doc_ids == [2, 1]

    def test_move_up_second_item(self, dialog_with_trip):
        """Moving up the second item swaps positions."""
        dialog_with_trip._list.setCurrentRow(1)
        dialog_with_trip._on_move_up()
        assert dialog_with_trip._doc_ids == [2, 1]

    def test_move_down_last_item_noop(self, dialog_with_trip):
        """Moving down the last item does nothing."""
        dialog_with_trip._list.setCurrentRow(1)
        original_order = dialog_with_trip._doc_ids.copy()
        dialog_with_trip._on_move_down()
        assert dialog_with_trip._doc_ids == original_order


class TestPackagePreviewDialogActions:
    """Continue, cancel, and download actions."""

    def test_continue_emits_signal_and_accepts(self, dialog_with_trip, qtbot):
        """Clicking Continue emits continue_to_email signal and accepts."""
        with qtbot.waitSignal(dialog_with_trip.continue_to_email, timeout=1000) as blocker:
            dialog_with_trip._on_continue()
        assert blocker.signal_triggered
        args = blocker.args
        assert args[0] == 42  # trip_id
        assert args[1] == [1, 2]  # ordered doc_ids
        assert len(args[2]) == 2  # ordered documents
        assert dialog_with_trip.result() == 1  # QDialog.Accepted

    def test_continue_with_no_docs_shows_message(self, dialog_empty, qtbot, monkeypatch):
        """Continue with empty list should not emit signal."""
        messages = []
        monkeypatch.setattr(
            "ui.views.package_preview_modal.QMessageBox.information",
            lambda *a, **kw: messages.append("shown"),
        )
        dialog_empty._on_continue()
        assert len(messages) == 1
        assert dialog_empty.result() != 1  # not accepted

    def test_cancel_closes_dialog(self, dialog_no_trip):
        dialog_no_trip.reject()
        assert dialog_no_trip.result() == 0  # QDialog.Rejected

    def test_get_ordered_documents(self, dialog_with_trip):
        docs = dialog_with_trip.get_ordered_documents()
        assert len(docs) == 2
        # IDs are strings from mock data (documents come from DB as strings)
        assert str(docs[0].get("id")) == "1"
        assert str(docs[1].get("id")) == "2"

    def test_get_ordered_document_ids(self, dialog_with_trip):
        ids = dialog_with_trip.get_ordered_document_ids()
        assert ids == [1, 2]

    def test_download_zip_calls_builder(self, dialog_with_trip):
        with patch(
            "ui.views.package_preview_modal.PackageBuilder.build_zip",
            return_value="/tmp/test.zip",
        ) as mock_build:
            with patch(
                "ui.views.package_preview_modal.QMessageBox.information",
            ):
                dialog_with_trip._on_download_zip()
                mock_build.assert_called_once()

    def test_download_pdf_calls_builder(self, dialog_with_trip):
        with patch(
            "ui.views.package_preview_modal.PackageBuilder.build_combined_pdf",
            return_value="/tmp/test.pdf",
        ) as mock_build:
            with patch(
                "ui.views.package_preview_modal.QMessageBox.information",
            ):
                dialog_with_trip._on_download_pdf()
                mock_build.assert_called_once()

    def test_download_zip_empty_shows_warning(self, dialog_with_trip, monkeypatch):
        """Download ZIP with no result shows warning."""
        warnings = []
        monkeypatch.setattr(
            "ui.views.package_preview_modal.QMessageBox.warning",
            lambda *a, **kw: warnings.append("shown"),
        )
        with patch(
            "ui.views.package_preview_modal.PackageBuilder.build_zip",
            return_value=None,
        ):
            dialog_with_trip._on_download_zip()
            assert len(warnings) == 1


class TestPackagePreviewDialogLifecycle:
    """Lifecycle and edge-case behaviour."""

    def test_refresh_id_order_skips_placeholder(self, dialog_empty):
        """_refresh_id_order gracefully handles items without integer data."""
        dialog_empty._refresh_id_order()
        assert dialog_empty._doc_ids == []

    def test_document_with_file_size_displayed(self, dialog_with_trip):
        """File size is rendered in the list item label."""
        item0 = dialog_with_trip._list.item(0)
        assert "KB" in item0.text() or "B" in item0.text()
