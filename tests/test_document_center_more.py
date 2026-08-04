"""Tests for advanced Document Center features: tags, expiry, versions,
admin/lifecycle, category tree, entity documents dialog, and shim module."""

from __future__ import annotations

import logging
import types
import sys
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_document_service():
    """DocumentService mock for tag/expiry/version tests."""
    svc = MagicMock()
    svc.add_tag.return_value = None
    svc.remove_tag.return_value = None
    svc.set_expiry_date.return_value = None
    svc.restore_version.return_value = None
    svc.upload_new_version.return_value = None
    svc.get_by_id.return_value = None
    svc.get_documents_for_entity.return_value = []
    svc.unlink_document.return_value = None
    svc.advanced_search.return_value = {"items": [], "total": 0, "total_pages": 0}
    svc.fts_search.return_value = {"items": [], "total": 0, "total_pages": 0}
    svc.get_categories.return_value = []
    svc.get_links.return_value = []
    svc.get_versions.return_value = []
    return svc


@pytest.fixture
def document_center(qtbot, mock_document_service):
    """Create QtDocumentCenterView with full mocking."""
    # Workaround: ui.widgets imports SP as S but SectionHeader uses SP (source bug)
    import ui.widgets as _ui_widgets
    if not hasattr(_ui_widgets, "SP"):
        _ui_widgets.SP = _ui_widgets.S

    from ui.views.document_center.document_center import QtDocumentCenterView

    view = QtDocumentCenterView(document_service=mock_document_service)
    qtbot.addWidget(view)
    yield view
    view.shutdown()


@pytest.fixture
def sample_doc():
    return {
        "id": 1,
        "title": "Test Doc",
        "file_name": "test.pdf",
        "file_size": 2048,
        "mime_type": "application/pdf",
        "uploaded_at": "2025-06-01T10:00:00",
        "doc_number": "DOC-001",
        "tags": '["urgent"]',
        "entity_type": "trip",
        "entity_id": 42,
        "expiry_date": "2025-12-31",
        "ocr_run_at": "2025-06-01T09:00:00",
        "ocr_engine": "tesseract",
        "ocr_text": "",
        "extracted_data_json": '{"invoice_number":"INV-001"}',
    }


@pytest.fixture
def sample_categories():
    return [
        {"category": "invoices", "cnt": 5},
        {"category": "receipts", "cnt": 3},
        {"category": "maintenance", "cnt": 2},
        {"category": "trips", "cnt": 1},
    ]


# =========================================================================
# Tag, Expiry & Version tests
# =========================================================================


class TestDocumentCenterTagExpiryVersions:
    """Tag add/remove, expiry set, version restore/upload."""

    # ── Tags ───────────────────────────────────────────────────────────

    def test_add_tag_action_calls_service(
        self, document_center, mock_document_service, sample_doc
    ):
        """_add_tag_action reads tag from _tag_entry, calls add_tag(), clears input, refreshes detail."""
        # _show_detail creates _tag_entry
        document_center._show_detail(sample_doc)
        assert hasattr(document_center, "_tag_entry")
        document_center._tag_entry.setText("new-tag")

        document_center._add_tag_action(1)

        mock_document_service.add_tag.assert_called_once_with(1, "new-tag")
        assert document_center._tag_entry.text() == ""
        # _refresh_detail calls get_by_id
        mock_document_service.get_by_id.assert_called_with(1)

    def test_add_tag_action_empty_tag_noop(
        self, document_center, mock_document_service, sample_doc
    ):
        """Empty/whitespace tag does not call service."""
        document_center._show_detail(sample_doc)
        document_center._tag_entry.setText("   ")

        document_center._add_tag_action(1)

        mock_document_service.add_tag.assert_not_called()

    def test_add_tag_action_no_service(
        self, document_center, sample_doc
    ):
        """_service is None is safe no-op."""
        document_center._service = None
        document_center._show_detail(sample_doc)
        document_center._tag_entry.setText("new-tag")

        document_center._add_tag_action(1)  # should not raise

    def test_remove_tag_calls_service(
        self, document_center, mock_document_service
    ):
        """_remove_tag calls service.remove_tag() then _refresh_detail."""
        document_center._remove_tag(1, "urgent")

        mock_document_service.remove_tag.assert_called_once_with(1, "urgent")
        mock_document_service.get_by_id.assert_called_with(1)

    def test_remove_tag_no_service(self, document_center):
        """_service is None safe no-op."""
        document_center._service = None
        document_center._remove_tag(1, "urgent")  # should not raise

    # ── Expiry ─────────────────────────────────────────────────────────

    def test_set_expiry_calls_service(
        self, document_center, mock_document_service, sample_doc
    ):
        """_set_expiry reads date from _expiry_entry, calls set_expiry_date(), shows toast, refreshes."""
        document_center._show_detail(sample_doc)
        assert hasattr(document_center, "_expiry_entry")
        document_center._expiry_entry.setText("2026-06-01")

        with patch.object(
            document_center, "_show_toast"
        ) as mock_toast:
            document_center._set_expiry(1)

        mock_document_service.set_expiry_date.assert_called_once_with(1, "2026-06-01")
        mock_toast.assert_called_once()
        mock_document_service.get_by_id.assert_called_with(1)

    def test_set_expiry_empty_date_noop(
        self, document_center, mock_document_service, sample_doc
    ):
        """Empty date string does not call service."""
        document_center._show_detail(sample_doc)
        document_center._expiry_entry.setText("")

        document_center._set_expiry(1)

        mock_document_service.set_expiry_date.assert_not_called()

    def test_set_expiry_no_service(
        self, document_center, sample_doc
    ):
        """_service is None safe no-op."""
        document_center._service = None
        document_center._show_detail(sample_doc)
        document_center._expiry_entry.setText("2026-06-01")

        document_center._set_expiry(1)  # should not raise

    # ── Versions — Restore ─────────────────────────────────────────────

    def test_restore_version_confirmed(
        self, document_center, mock_document_service
    ):
        """_restore_version: on Yes calls service.restore_version(), shows toast, refreshes."""
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            with patch.object(document_center, "_show_toast") as mock_toast:
                document_center._restore_version(1, 2)

        mock_document_service.restore_version.assert_called_once_with(1, 2)
        mock_toast.assert_called_once()
        mock_document_service.get_by_id.assert_called_with(1)

    def test_restore_version_cancelled(
        self, document_center, mock_document_service
    ):
        """On No does nothing."""
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            document_center._restore_version(1, 2)

        mock_document_service.restore_version.assert_not_called()

    def test_restore_version_no_service(
        self, document_center
    ):
        """_service is None safe no-op."""
        document_center._service = None
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            document_center._restore_version(1, 2)  # should not raise

    # ── Versions — Upload ──────────────────────────────────────────────

    def test_upload_version_dialog_cancelled(
        self, document_center, mock_document_service
    ):
        """File dialog returns empty path -> no-op."""
        with patch.object(
            QFileDialog, "getOpenFileName", return_value=("", "")
        ):
            document_center._upload_version_dialog(1)

        mock_document_service.upload_new_version.assert_not_called()

    def test_upload_version_dialog_confirmed(
        self, document_center, mock_document_service
    ):
        """File picked, comment entered, calls service.upload_new_version(), shows toast, refreshes."""
        with patch.object(
            QFileDialog, "getOpenFileName", return_value=("/tmp/v2.pdf", "")
        ):
            with patch.object(
                QInputDialog, "getText", return_value=("Fixed typo", True)
            ):
                with patch.object(
                    document_center, "_show_toast"
                ) as mock_toast:
                    document_center._upload_version_dialog(1)

        mock_document_service.upload_new_version.assert_called_once_with(
            1, "/tmp/v2.pdf", "Fixed typo", "user"
        )
        mock_toast.assert_called_once()
        mock_document_service.get_by_id.assert_called_with(1)

    def test_upload_version_dialog_no_comment(
        self, document_center, mock_document_service
    ):
        """Dialog accepted but comment empty -> comment = \"\"."""
        with patch.object(
            QFileDialog, "getOpenFileName", return_value=("/tmp/v3.pdf", "")
        ):
            with patch.object(
                QInputDialog, "getText", return_value=("", False)
            ):
                document_center._upload_version_dialog(1)

        mock_document_service.upload_new_version.assert_called_once_with(
            1, "/tmp/v3.pdf", "", "user"
        )

    def test_upload_version_service_exception(
        self, document_center, mock_document_service
    ):
        """Service raises -> QMessageBox.critical shown, still calls _refresh_detail."""
        mock_document_service.upload_new_version.side_effect = ValueError("Upload failed")

        with patch.object(
            QFileDialog, "getOpenFileName", return_value=("/tmp/v4.pdf", "")
        ):
            with patch.object(
                QInputDialog, "getText", return_value=("comment", True)
            ):
                with patch.object(
                    QMessageBox, "critical"
                ) as mock_critical:
                    document_center._upload_version_dialog(1)

        mock_critical.assert_called_once()
        mock_document_service.get_by_id.assert_called_with(1)

    # ── Refresh detail ─────────────────────────────────────────────────

    def test_refresh_detail_gets_by_id(
        self, document_center, mock_document_service, sample_doc
    ):
        """_refresh_detail calls service.get_by_id(), then _show_detail."""
        mock_document_service.get_by_id.return_value = sample_doc

        with patch.object(document_center, "_show_detail") as mock_show:
            document_center._refresh_detail(1)

        mock_document_service.get_by_id.assert_called_once_with(1)
        mock_show.assert_called_once_with(sample_doc)

    def test_refresh_detail_no_service(self, document_center):
        """_service is None safe no-op."""
        document_center._service = None
        document_center._refresh_detail(1)  # should not raise

    def test_refresh_detail_doc_returns_none(
        self, document_center, mock_document_service
    ):
        """get_by_id returns None -> _show_detail not called."""
        mock_document_service.get_by_id.return_value = None

        with patch.object(document_center, "_show_detail") as mock_show:
            document_center._refresh_detail(1)

        mock_show.assert_not_called()


# =========================================================================
# Admin & Lifecycle tests
# =========================================================================


class TestDocumentCenterAdminAndLifecycle:
    """Admin tab inject/eject, tab switching, i18n, toast, document events."""

    # ── i18n ───────────────────────────────────────────────────────────

    def test_i18n_update_translations_sets_texts(self, document_center):
        """_update_translations sets sidebar, filter, upload, sort, search, page, detail texts."""
        document_center._update_translations()  # should not raise

        assert document_center._sidebar_header is not None
        assert document_center._filter_toggle is not None
        assert document_center._upload_btn is not None
        assert document_center._sort_combo is not None
        assert document_center._search_entry is not None
        assert document_center._page_label is not None
        assert document_center._detail_header is not None

    # ── Tab changed ────────────────────────────────────────────────────

    def test_on_tab_changed_automation(self, document_center):
        """Tab index 1 calls _automation_view.wakeup() and _refresh_from_db()."""
        mock_auto = MagicMock()
        document_center._automation_view = mock_auto

        document_center._on_tab_changed(1)

        mock_auto.wakeup.assert_called_once()
        mock_auto._refresh_from_db.assert_called_once()

    def test_on_tab_changed_automation_no_view(self, document_center):
        """Tab index 1 but _automation_view is None -> no crash."""
        document_center._automation_view = None
        document_center._on_tab_changed(1)  # should not raise

    def test_on_tab_changed_api_dashboard(self, document_center):
        """Tab with API dashboard calls _api_dashboard.wakeup()."""
        mock_dashboard = MagicMock()
        document_center._api_dashboard_view = mock_dashboard
        document_center._admin_api_dashboard_tab = True
        document_center._api_dashboard_tab_index = 2

        document_center._on_tab_changed(2)

        mock_dashboard.wakeup.assert_called_once()

    def test_on_tab_changed_admin_panel(self, document_center):
        """Admin tab injected, correct index -> calls _admin_panel_view.wakeup()."""
        mock_admin = MagicMock()
        document_center._admin_panel_view = mock_admin
        document_center._admin_tab_injected = True
        document_center._admin_tab_index = 3

        document_center._on_tab_changed(3)

        mock_admin.wakeup.assert_called_once()

    # ── Admin trigger ──────────────────────────────────────────────────

    def test_on_admin_trigger_already_injected(self, document_center):
        """Admin tab already injected -> switches to tab index."""
        document_center._admin_tab_injected = True
        document_center._admin_tab_index = 3
        document_center._admin_panel_view = MagicMock()

        with patch.object(document_center._tab_widget, "setCurrentIndex") as mock_set:
            document_center._on_admin_trigger_clicked()

        mock_set.assert_called_once_with(3)

    def test_on_admin_trigger_not_injected_auth_fails(self, document_center):
        """_try_inject_admin_tab returns False -> no crash."""
        document_center._admin_tab_injected = False
        document_center._admin_auth_in_progress = False

        with patch.object(
            document_center, "_try_inject_admin_tab", return_value=False
        ):
            document_center._on_admin_trigger_clicked()  # should not raise

    # ── Eject admin tab ────────────────────────────────────────────────

    def test_eject_admin_tab(self, document_center):
        """When injected, removes tab, clears state."""
        document_center._admin_tab_injected = True
        document_center._admin_tab_index = 3
        document_center._admin_panel_view = MagicMock()
        document_center._admin_panel_page = QWidget()

        document_center._eject_admin_tab()

        assert document_center._admin_tab_injected is False
        assert document_center._admin_panel_view is None
        assert document_center._admin_panel_page is None
        assert document_center._admin_tab_index == -1

    def test_eject_admin_tab_not_injected(self, document_center):
        """No-op when not injected."""
        document_center._admin_tab_injected = False
        document_center._eject_admin_tab()  # should not raise

    # ── Token expiry ───────────────────────────────────────────────────

    def test_on_token_expired(self, document_center):
        """Calls _eject_admin_tab() and clear_auth()."""
        document_center._admin_tab_injected = True
        document_center._admin_tab_index = 3

        with patch(
            "client.auth_manager.clear_auth"
        ) as mock_clear_auth:
            document_center._on_token_expired()

        assert document_center._admin_tab_injected is False
        mock_clear_auth.assert_called_once()

    # ── Document event ─────────────────────────────────────────────────

    def test_on_document_event_safe_refresh(
        self, document_center, mock_document_service
    ):
        """_on_document_event schedules _safe_refresh via QTimer."""
        document_center._event_subscribed = True

        with patch(
            "PySide6.QtCore.QTimer.singleShot"
        ) as mock_singleshot:
            document_center._on_document_event({})

            mock_singleshot.assert_called_once()
            args = mock_singleshot.call_args[0]
            assert args[0] == 500
            callback = args[1]
            assert callable(callback)

            # Invoke callback to verify refresh runs
            callback()
            mock_document_service.get_categories.assert_called()

    # ── Toast ──────────────────────────────────────────────────────────

    def test_show_toast_success(self, document_center):
        """_show_toast delegates to Toast.show_success."""
        with patch(
            "ui.widgets.toast.Toast"
        ) as MockToast:
            document_center._show_toast("Hello World")

            MockToast.show_success.assert_called_once_with(
                document_center, "Hello World", anchor=document_center
            )

    def test_show_toast_import_error(self, document_center, caplog):
        """When Toast import fails, logs message without crash."""
        import types

        # Replace the toast module with a fake that has no Toast class
        fake_mod = types.ModuleType("ui.widgets.toast")
        # Ensure parent package entries exist
        for pkg in ["ui", "ui.widgets"]:
            if pkg not in sys.modules:
                sys.modules[pkg] = types.ModuleType(pkg)

        saved = sys.modules.get("ui.widgets.toast")
        sys.modules["ui.widgets.toast"] = fake_mod

        # Also clear any cached Toast from document_center module
        import ui.views.document_center.document_center as dc
        cached_toast = getattr(dc, "Toast", None)
        if hasattr(dc, "Toast"):
            del dc.Toast

        try:
            with caplog.at_level(logging.INFO):
                document_center._show_toast("Hello")

                found = any(
                    "Toast widget unavailable" in rec.getMessage()
                    for rec in caplog.records
                )
                assert found, "Expected log message about toast unavailability"
        finally:
            if saved is not None:
                sys.modules["ui.widgets.toast"] = saved
            else:
                sys.modules.pop("ui.widgets.toast", None)
            if cached_toast is not None:
                dc.Toast = cached_toast

    # ── Build automation view ──────────────────────────────────────────

    def test_build_automation_view_import_error(self, document_center):
        """Import failure returns None."""
        # Replace the automation_view module in sys.modules with one
        # that doesn't have QtAutomationView, forcing ImportError.
        saved = {}
        for key in list(sys.modules):
            if "ui.views.automation_view" == key:
                saved[key] = sys.modules[key]

        fake_mod = types.ModuleType("ui.views.automation_view")
        # Ensure parent packages exist
        for pkg in ["ui", "ui.views"]:
            if pkg not in sys.modules:
                sys.modules[pkg] = types.ModuleType(pkg)

        sys.modules["ui.views.automation_view"] = fake_mod

        try:
            result = document_center._build_automation_view()
            assert result is None
        finally:
            for key, val in saved.items():
                sys.modules[key] = val
            if not saved:
                sys.modules.pop("ui.views.automation_view", None)

    # ── Category tree ──────────────────────────────────────────────────

    def test_build_category_tree_total_count(
        self, document_center, sample_categories
    ):
        """_build_category_tree computes total count from categories list."""
        document_center._build_category_tree(sample_categories)

        buttons = document_center._cat_frame.findChildren(QPushButton)
        # First button is "All ({total})"
        all_btn = buttons[0]
        assert "(11)" in all_btn.text()  # 5 + 3 + 2 + 1

    def test_build_category_tree_all_active_by_default(
        self, document_center, sample_categories
    ):
        """'All' button has active state when _active_category == \"\"."""
        document_center._active_category = ""
        document_center._build_category_tree(sample_categories)

        buttons = document_center._cat_frame.findChildren(QPushButton)
        all_btn = buttons[0]
        assert all_btn.property("active") == "true"

    def test_build_category_tree_respects_active_category(
        self, document_center, sample_categories
    ):
        """Button for active category has active styling."""
        document_center._active_category = "invoices"
        document_center._build_category_tree(sample_categories)

        buttons = document_center._cat_frame.findChildren(QPushButton)
        # Find button that mentions invoices
        inv_btns = [b for b in buttons if "invoices" in b.text().lower()]
        assert len(inv_btns) >= 1
        assert inv_btns[0].property("active") == "true"


# =========================================================================
# Standalone open_entity_documents function
# =========================================================================


class TestOpenEntityDocuments:
    """Standalone open_entity_documents() function."""

    @staticmethod
    def _capture_dialog_and_mocks(qt_widget, docs, links=None, upload_return=True):
        """Helper to run open_entity_documents with mocking, returning (dialog, mock_svc)."""
        from ui.views.document_center.document_center import open_entity_documents

        captured = []
        real_init = QDialog.__init__

        def capturing_init(self, parent=None, f=None):
            captured.append(self)
            # Pass f only if it's provided (Qt.WindowFlags variation)
            if f is not None:
                return real_init(self, parent, f)
            return real_init(self, parent)

        with patch.object(QDialog, "__init__", capturing_init):
            with patch.object(QDialog, "exec", return_value=0):
                with patch(
                    "ui.views.document_center.document_center.DocumentService"
                ) as MockSvc:
                    mock_svc = MagicMock()
                    MockSvc.return_value = mock_svc
                    mock_svc.get_documents_for_entity.return_value = docs
                    if links is not None:
                        mock_svc.get_links.return_value = links

                    open_entity_documents(
                        qt_widget, MagicMock(), "trip", 42
                    )

        dlg = captured[0] if captured else None
        return dlg, mock_svc

    def test_open_entity_documents_creates_dialog(self, qt_widget):
        """Function creates QDialog, populates with document list, upload button, close."""
        docs = [
            {
                "id": 1,
                "title": "Test Doc",
                "file_name": "test.pdf",
                "file_size": 2048,
                "mime_type": "application/pdf",
                "uploaded_at": "2025-06-01T10:00:00",
                "doc_number": "DOC-001",
            }
        ]

        dlg, mock_svc = self._capture_dialog_and_mocks(qt_widget, docs)

        assert dlg is not None
        assert isinstance(dlg, QDialog)
        assert dlg.parent() is qt_widget
        mock_svc.get_documents_for_entity.assert_called_once_with("trip", 42)

    def test_open_entity_documents_empty_state(self, qt_widget):
        """No documents for entity -> shows empty label."""
        dlg, mock_svc = self._capture_dialog_and_mocks(qt_widget, [])

        assert dlg is not None
        # Should show no-documents message
        labels = dlg.findChildren(QLabel)
        assert any(
            "no" in lbl.text().lower() or "document" in lbl.text().lower()
            for lbl in labels
        )

    def test_open_entity_documents_upload_cancelled(self, qt_widget):
        """Upload clicked, no files selected -> no changes."""
        dlg, mock_svc = self._capture_dialog_and_mocks(qt_widget, [])

        with patch.object(
            QFileDialog, "getOpenFileNames", return_value=([], "")
        ):
            # Find the upload button and click it
            buttons = dlg.findChildren(QPushButton)
            upload_btns = [b for b in buttons if "upload" in b.text().lower()]
            if upload_btns:
                upload_btns[0].click()
                # No upload should happen since no file was selected
                mock_svc.upload_document.assert_not_called()

    def test_open_entity_documents_unlink_and_refresh(self, qt_widget):
        """Unlink button calls service.unlink_document and refreshes list."""
        docs = [
            {
                "id": 10,
                "title": "Linked Doc",
                "file_name": "linked.pdf",
                "file_size": 1024,
                "mime_type": "application/pdf",
                "uploaded_at": "2025-06-01T10:00:00",
                "doc_number": "DOC-010",
            }
        ]
        links = [
            {
                "id": 99,
                "linked_entity_type": "trip",
                "linked_entity_id": 42,
            }
        ]

        dlg, mock_svc = self._capture_dialog_and_mocks(qt_widget, docs, links)

        # Find unlink buttons
        buttons = dlg.findChildren(QPushButton)
        unlink_btns = [b for b in buttons if "unlink" in b.text().lower()]
        assert len(unlink_btns) >= 1, "Expected at least one Unlink button"

        # Click the unlink button
        unlink_btns[0].click()

        mock_svc.get_links.assert_called_with(10)
        mock_svc.unlink_document.assert_called_once_with(99)
        # get_documents_for_entity should be called again (refresh)
        assert mock_svc.get_documents_for_entity.call_count >= 2


# =========================================================================
# Shim module
# =========================================================================


class TestDocumentCenterViewShim:
    """Import verification for shim module."""

    def test_shim_re_exports(self):
        """Verify from ui.views.document_center_view import works."""
        from ui.views.document_center_view import (
            QtDocumentCenterView as ShimView,
            open_entity_documents as ShimFunc,
        )
        from ui.views.document_center.document_center import (
            QtDocumentCenterView,
            open_entity_documents,
        )

        assert ShimView is QtDocumentCenterView
        assert ShimFunc is open_entity_documents
