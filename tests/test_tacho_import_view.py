"""Tests for the tachograph import view (PySide6)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_tacho_service():
    """Patch the TachoService constructor so no real DB is needed."""
    with patch("ui.views.tacho_import_view.TachoService", autospec=True) as svc:
        inst = svc.return_value
        inst.get_import_history.return_value = []
        inst.import_ddd_file.return_value = {
            "success": True,
            "summary": "Import successful",
            "records_imported": 10,
            "file_name": "test.ddd",
        }
        yield inst


@pytest.fixture
def view_with_db(qt_widget, qtbot, mock_tacho_service):
    """Create a ``QtTachoImportView`` with a fake DB (local TachoService)."""
    from ui.views.tacho_import_view import QtTachoImportView

    db = MagicMock()
    v = QtTachoImportView(parent=qt_widget, db=db, api_client=None)
    qt_widget.show()
    v.show()
    qtbot.addWidget(v)
    qtbot.wait(10)  # let Qt process show events
    yield v
    with pytest.importorskip("contextlib").suppress(Exception):
        v.shutdown()


@pytest.fixture
def view_with_api(qt_widget, qtbot):
    """Create a ``QtTachoImportView`` with a fake API client."""
    with patch(
        "client.remote_tacho.RemoteTachoService",
        autospec=True,
    ) as remote_svc:
        inst = remote_svc.return_value
        inst.get_import_history.return_value = []
        inst.import_ddd_file.return_value = {
            "success": True,
            "summary": "Import successful",
        }
        from ui.views.tacho_import_view import QtTachoImportView

        v = QtTachoImportView(
            parent=qt_widget, db=None, api_client=MagicMock(),
        )
        qt_widget.show()
        v.show()
        qtbot.addWidget(v)
        qtbot.wait(10)
        yield v
        with pytest.importorskip("contextlib").suppress(Exception):
            v.shutdown()


@pytest.fixture
def view_no_service(qt_widget, qtbot):
    """Create a ``QtTachoImportView`` with neither db nor api_client."""
    from ui.views.tacho_import_view import QtTachoImportView

    v = QtTachoImportView(parent=qt_widget, db=None, api_client=None)
    qt_widget.show()
    v.show()
    qtbot.addWidget(v)
    qtbot.wait(10)
    yield v
    with pytest.importorskip("contextlib").suppress(Exception):
        v.shutdown()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestQtTachoImportView:
    def test_creation_with_db(self, view_with_db):
        assert view_with_db is not None
        assert view_with_db.db is not None
        assert view_with_db.tacho_service is not None

    def test_creation_with_api(self, view_with_api):
        assert view_with_api is not None
        assert view_with_api._api_client is not None
        assert view_with_api.tacho_service is not None

    def test_creation_without_service(self, view_no_service):
        assert view_no_service is not None
        assert view_no_service.tacho_service is None

    # ── UI elements ────────────────────────────────────────────────────

    def test_drop_zone_created(self, view_with_db):
        assert hasattr(view_with_db, "_drop_zone")
        assert view_with_db._drop_zone is not None

    def test_import_driver_button_created(self, view_with_db):
        assert hasattr(view_with_db, "_btn_driver")
        assert view_with_db._btn_driver is not None

    def test_import_vehicle_button_created(self, view_with_db):
        assert hasattr(view_with_db, "_btn_vehicle")
        assert view_with_db._btn_vehicle is not None

    def test_progress_label_created(self, view_with_db):
        assert hasattr(view_with_db, "_progress_lbl")
        assert view_with_db._progress_lbl is not None

    def test_result_card_created(self, view_with_db):
        assert hasattr(view_with_db, "_result_card")
        assert view_with_db._result_card is not None
        # Should be hidden initially
        assert not view_with_db._result_card.isVisible()

    def test_result_icon_created(self, view_with_db):
        assert hasattr(view_with_db, "_result_icon")

    def test_result_msg_created(self, view_with_db):
        assert hasattr(view_with_db, "_result_msg")

    def test_result_detail_created(self, view_with_db):
        assert hasattr(view_with_db, "_result_detail")

    def test_result_violations_created(self, view_with_db):
        assert hasattr(view_with_db, "_result_violations")

    def test_history_table_created(self, view_with_db):
        assert hasattr(view_with_db, "_history_table")
        assert view_with_db._history_table is not None

    def test_history_card_created(self, view_with_db):
        assert hasattr(view_with_db, "_history_card")

    def test_history_table_container_created(self, view_with_db):
        assert hasattr(view_with_db, "_history_table_container")

    def test_history_empty_state_created(self, view_with_db):
        assert hasattr(view_with_db, "_history_empty")

    # ── Signal ─────────────────────────────────────────────────────────

    def test_import_completed_signal(self, view_with_db):
        assert hasattr(view_with_db, "import_completed")

    # ── Lifecycle ──────────────────────────────────────────────────────

    def test_wakeup_refreshes_history(self, view_with_db):
        with patch.object(view_with_db, "_refresh_history") as mock_refresh:
            view_with_db.wakeup()
            mock_refresh.assert_called_once()

    def test_shutdown_does_not_crash(self, view_with_db):
        view_with_db.shutdown()  # no crash

    def test_shutdown_idempotent(self, view_with_db):
        view_with_db.shutdown()
        view_with_db.shutdown()  # second call must not raise

    # ── Progress / result display ──────────────────────────────────────

    def test_show_progress(self, view_with_db):
        view_with_db.show()  # ensure parent chain is visible
        view_with_db._show_progress("Importing...")
        assert view_with_db._progress_lbl.text() == "Importing..."
        assert view_with_db._progress_lbl.isVisible()

    def test_hide_progress(self, view_with_db):
        view_with_db.show()
        view_with_db._show_progress("Importing...")
        view_with_db._hide_progress()
        assert view_with_db._progress_lbl.text() == ""
        assert not view_with_db._progress_lbl.isVisible()

    def test_show_result_success(self, view_with_db):
        view_with_db.show()
        result = {
            "success": True,
            "summary": "Import OK",
            "driver_name": "John Doe",
            "plate": "B-123-TST",
            "days_imported": 28,
            "odometer_km": 50000.0,
            "violations_found": 2,
        }
        view_with_db._show_result_success(result)
        assert view_with_db._result_card.isVisible()
        assert "\u2713" in view_with_db._result_icon.text()
        assert "Import OK" in view_with_db._result_msg.text()
        assert view_with_db._result_detail.isVisible()
        assert view_with_db._result_violations.isVisible()

    def test_show_result_success_no_detail(self, view_with_db):
        view_with_db.show()
        result = {"success": True, "summary": "OK"}
        view_with_db._show_result_success(result)
        assert view_with_db._result_detail.isVisible() is False

    def test_show_result_error(self, view_with_db):
        view_with_db.show()
        view_with_db._show_result_error("Something went wrong")
        assert view_with_db._result_card.isVisible()
        assert "\u2717" in view_with_db._result_icon.text()
        assert "Something went wrong" in view_with_db._result_msg.text()
        assert not view_with_db._result_detail.isVisible()
        assert not view_with_db._result_violations.isVisible()

    def test_on_import_complete_success(self, view_with_db):
        result = {"success": True, "summary": "OK"}
        with (
            patch.object(view_with_db, "_show_result_success") as mock_ok,
            patch.object(view_with_db, "_refresh_history") as mock_hist,
        ):
            view_with_db._on_import_complete(result)
            mock_ok.assert_called_once_with(result)
            mock_hist.assert_called_once()

    def test_on_import_complete_error(self, view_with_db):
        result = {"success": False, "error": "Failed"}
        with (
            patch.object(view_with_db, "_show_result_error") as mock_err,
            patch.object(view_with_db, "_refresh_history") as mock_hist,
        ):
            view_with_db._on_import_complete(result)
            mock_err.assert_called_once_with("Failed")
            mock_hist.assert_called_once()

    # ── Drop zone drag/drop events ─────────────────────────────────────

    def test_drag_enter_accepts_urls(self, view_with_db):
        mime = MagicMock()
        mime.hasUrls.return_value = True
        event = MagicMock()
        event.mimeData.return_value = mime
        view_with_db.dragEnterEvent(event)
        event.acceptProposedAction.assert_called_once()

    def test_drag_enter_rejects_non_urls(self, view_with_db):
        mime = MagicMock()
        mime.hasUrls.return_value = False
        event = MagicMock()
        event.mimeData.return_value = mime
        view_with_db.dragEnterEvent(event)
        event.acceptProposedAction.assert_not_called()

    def test_drop_event(self, view_with_db):
        """Drop event with a file URL triggers _run_import."""
        url = MagicMock()
        url.toLocalFile.return_value = "/tmp/test.ddd"
        mime = MagicMock()
        mime.urls.return_value = [url]  # QMimeData.urls() is a method
        event = MagicMock()
        event.mimeData.return_value = mime
        with patch.object(view_with_db, "_run_import") as mock_import:
            view_with_db.dropEvent(event)
            mock_import.assert_called_once_with("/tmp/test.ddd")

    # ── i18n ───────────────────────────────────────────────────────────

    def test_language_callback_registered(self, view_with_db):
        assert hasattr(view_with_db, "_language_callback")
        assert view_with_db._language_callback is not None

    def test_on_language_changed_triggers_rebuild(self, view_with_db, qtbot):
        with patch.object(view_with_db, "_rebuild_ui") as mock_rebuild:
            view_with_db._on_language_changed("ro")
            # QTimer.singleShot(0) — process events to let it fire
            qtbot.wait(10)
            mock_rebuild.assert_called_once()

    # ── History formatting ─────────────────────────────────────────────

    def test_format_history_row(self, view_with_db):
        raw = {
            "imported_at": "2025-06-15T10:30:00",
            "file_type": "driver_card",
            "file_name": "card.ddd",
            "records_imported": 42,
            "parse_status": "ok",
        }
        row = view_with_db._format_history_row(raw)
        assert row["imported_at"] == "2025-06-15"
        assert row["file_type"] != "driver_card"  # translated
        assert row["file_type_raw"] == "driver_card"
        assert row["records_imported"] == "42"
        assert row["parse_status_raw"] == "ok"

    def test_format_history_row_vehicle_type(self, view_with_db):
        raw = {
            "file_type": "vehicle_unit",
            "parse_status": "partial",
        }
        row = view_with_db._format_history_row(raw)
        assert row["file_type_raw"] == "vehicle_unit"
        assert row["parse_status_raw"] == "partial"

    def test_format_history_row_error_status(self, view_with_db):
        raw = {
            "file_type": "driver_card",
            "parse_status": "error",
        }
        row = view_with_db._format_history_row(raw)
        assert row["parse_status_raw"] == "error"

    # ── Run import (no service) ────────────────────────────────────────

    def test_run_import_no_service(self, view_no_service):
        with patch.object(view_no_service, "_show_result_error") as mock_err:
            view_no_service._run_import("/tmp/test.ddd")
            mock_err.assert_called_once()
