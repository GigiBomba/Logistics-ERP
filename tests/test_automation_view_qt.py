"""pytest-qt tests for QtAutomationView — UI, lifecycle, pipeline listing.

Expands on the legacy tests in ``test_automation_view.py`` (which covered an
older API) with modern pytest-qt fixtures, mock-based dependencies, and
coverage for the current widget tree.

Tests
-----
- Initialization and injected dependency storage
- Key UI elements: DropZone, detail panel, mode radio buttons, refresh button
- Mode switching (simple <-> advanced)
- Empty state placeholder (visible / hidden)
- Card creation from pipeline_repo data
- Run selection and highlight
- Shutdown / wakeup lifecycle (idempotent)
- Selected-trip public API
- Refreshing with DB errors (no crash)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton

from ui.views.automation_view.automation_view import (
    QtAutomationView,
    DropZone,
    _RunCard,
    _RunDetailPanel,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_prefs():
    prefs = MagicMock()
    prefs.get_setting.return_value = None
    return prefs


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.event_bus = MagicMock()
    return ops


@pytest.fixture
def mock_api_client():
    return MagicMock()


@pytest.fixture
def mock_pipeline_repo():
    repo = MagicMock()
    repo.list_runs.return_value = []
    repo.recover_stuck_runs.return_value = 0
    return repo


@pytest.fixture
def automation_view(
    qtbot,
    mock_db,
    mock_prefs,
    mock_ops,
    mock_api_client,
    mock_pipeline_repo,
):
    """Create a QtAutomationView with all heavyweight dependencies mocked."""
    with (
        patch("services.email_importer.EmailImporter"),
        patch("services.folder_watcher.FolderWatcher"),
        patch("services.document_service.DocumentService"),
    ):
        view = QtAutomationView(
            parent=None,
            db=mock_db,
            prefs=mock_prefs,
            ops=mock_ops,
            api_client=mock_api_client,
            pipeline_repo=mock_pipeline_repo,
        )
        qtbot.addWidget(view)
        yield view

        with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
            view.shutdown()


# =========================================================================
# Initialization & injected dependencies
# =========================================================================


class TestQtAutomationViewInit:
    """Widget initializes without crashing and stores injected refs."""

    def test_creation(self, automation_view):
        assert automation_view is not None

    def test_stores_db(self, automation_view):
        assert automation_view.db is not None

    def test_stores_prefs(self, automation_view):
        assert automation_view.prefs is not None

    def test_stores_ops(self, automation_view):
        assert automation_view.ops is not None


# =========================================================================
# Key UI elements
# =========================================================================


class TestQtAutomationViewUI:
    """Key UI elements exist and have expected defaults."""

    def test_drop_zone_exists(self, automation_view):
        dz = automation_view._drop_zone
        assert dz is not None
        assert isinstance(dz, DropZone)
        assert dz.acceptDrops() is True
        assert dz.objectName() == "automationDropZone"

    def test_detail_panel_exists(self, automation_view):
        detail = automation_view._detail
        assert detail is not None
        assert isinstance(detail, _RunDetailPanel)

    def test_mode_radio_buttons_exist(self, automation_view):
        assert automation_view._radio_simple is not None
        assert automation_view._radio_advanced is not None
        # Advanced is checked by default
        assert automation_view._radio_advanced.isChecked() is True
        assert automation_view._radio_simple.isChecked() is False
        assert automation_view._mode == "advanced"

    def test_mode_switch_to_simple(self, automation_view, qtbot):
        qtbot.mouseClick(automation_view._radio_simple, Qt.LeftButton)
        assert automation_view._radio_simple.isChecked() is True
        assert automation_view._radio_advanced.isChecked() is False
        assert automation_view._mode == "simple"

    def test_mode_switch_back_to_advanced(self, automation_view, qtbot):
        qtbot.mouseClick(automation_view._radio_simple, Qt.LeftButton)
        assert automation_view._mode == "simple"
        qtbot.mouseClick(automation_view._radio_advanced, Qt.LeftButton)
        assert automation_view._mode == "advanced"

    def test_header_title_renders(self, automation_view):
        """PageTitle label appears in the header."""
        labels = automation_view.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert any("Document Automation" in t for t in texts)

    def test_refresh_button_exists(self, automation_view):
        """At least one QPushButton child exists (the Refresh button)."""
        buttons = automation_view.findChildren(QPushButton)
        assert len(buttons) >= 1

    def test_concurrent_workers_default(self, automation_view):
        assert 1 <= automation_view.MAX_CONCURRENT_WORKERS <= 8
        assert automation_view.MAX_CONCURRENT_WORKERS == QtAutomationView.DEFAULT_MAX_CONCURRENT_WORKERS

    def test_max_concurrent_workers_from_prefs(self, mock_prefs):
        """Setting a value in prefs is reflected in MAX_CONCURRENT_WORKERS."""
        mock_prefs.get_setting.return_value = "5"
        # Recreate with the custom prefs
        with (
            patch("services.email_importer.EmailImporter"),
            patch("services.folder_watcher.FolderWatcher"),
            patch("services.document_service.DocumentService"),
        ):
            view = QtAutomationView(
                parent=None, db=MagicMock(), prefs=mock_prefs, ops=MagicMock(),
            )
            assert view.MAX_CONCURRENT_WORKERS == 5

    def test_max_concurrent_workers_clamped(self, mock_prefs):
        """Values outside [1, HARD_MAX] are clamped."""
        mock_prefs.get_setting.return_value = "999"
        with (
            patch("services.email_importer.EmailImporter"),
            patch("services.folder_watcher.FolderWatcher"),
            patch("services.document_service.DocumentService"),
        ):
            view = QtAutomationView(
                parent=None, db=MagicMock(), prefs=mock_prefs, ops=MagicMock(),
            )
            assert view.MAX_CONCURRENT_WORKERS == QtAutomationView.HARD_MAX_CONCURRENT_WORKERS

    def test_max_concurrent_workers_minimum(self, mock_prefs):
        """Minimum value is 1."""
        mock_prefs.get_setting.return_value = "0"
        with (
            patch("services.email_importer.EmailImporter"),
            patch("services.folder_watcher.FolderWatcher"),
            patch("services.document_service.DocumentService"),
        ):
            view = QtAutomationView(
                parent=None, db=MagicMock(), prefs=mock_prefs, ops=MagicMock(),
            )
            assert view.MAX_CONCURRENT_WORKERS == 1


# =========================================================================
# Empty state
# =========================================================================


class TestQtAutomationViewEmptyState:
    """Placeholder behaviour when the runs list is empty."""

    def test_empty_state_shows_placeholder(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.list_runs.return_value = []
        automation_view._refresh_from_db()
        assert automation_view._placeholder_label is not None
        assert isinstance(automation_view._placeholder_label, QLabel)
        assert len(automation_view._placeholder_label.text()) > 0

    def test_placeholder_disappears_with_runs(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.list_runs.return_value = [
            {"id": 1, "source_file_name": "test.pdf",
             "source_mime_type": "application/pdf", "source_file_size": 1024,
             "status": "imported", "stage": "import"},
        ]
        automation_view._refresh_from_db()
        assert 1 in automation_view._cards
        assert automation_view._placeholder_label is None

    def test_placeholder_reappears_when_runs_cleared(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.list_runs.return_value = [
            {"id": 1, "source_file_name": "a.pdf",
             "source_mime_type": "application/pdf", "source_file_size": 123,
             "status": "imported", "stage": "import"},
        ]
        automation_view._refresh_from_db()
        assert automation_view._placeholder_label is None
        # Now simulate deletion
        mock_pipeline_repo.list_runs.return_value = []
        automation_view._refresh_from_db()
        assert automation_view._placeholder_label is not None

    def test_placeholder_not_duplicated_on_repeated_refresh(self, automation_view, mock_pipeline_repo):
        """Repeated refreshes on empty DB don't stack placeholders."""
        mock_pipeline_repo.list_runs.return_value = []
        for _ in range(5):
            automation_view._refresh_from_db()
        # Only one placeholder in the layout
        count = 0
        for i in range(automation_view._run_list_layout.count()):
            item = automation_view._run_list_layout.itemAt(i)
            w = item.widget() if item else None
            if isinstance(w, QLabel):
                count += 1
        assert count == 1

    def test_refresh_handles_db_error(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.list_runs.side_effect = Exception("DB error")
        automation_view._refresh_from_db()  # must not crash
        # Falls back to empty, showing placeholder
        assert automation_view._placeholder_label is not None


# =========================================================================
# Cards — creation, selection, update
# =========================================================================


class TestQtAutomationViewCards:
    """Pipeline run cards are created, updated, and selectable."""

    def test_cards_created_from_runs(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.list_runs.return_value = [
            {"id": i, "source_file_name": f"doc{i}.pdf",
             "source_mime_type": "application/pdf", "source_file_size": 1024,
             "status": "imported", "stage": "import"}
            for i in range(1, 4)
        ]
        automation_view._refresh_from_db()
        assert len(automation_view._cards) == 3
        for i in range(1, 4):
            assert i in automation_view._cards
            assert isinstance(automation_view._cards[i], _RunCard)

    def test_card_has_run_id(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.list_runs.return_value = [
            {"id": 99, "source_file_name": "x.pdf",
             "source_mime_type": "image/jpeg", "source_file_size": 512,
             "status": "imported", "stage": "import"},
        ]
        automation_view._refresh_from_db()
        assert automation_view._cards[99].run_id == 99

    def test_select_run_sets_selected_id(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.list_runs.return_value = [
            {"id": 1, "source_file_name": "a.pdf",
             "source_mime_type": "image/jpeg", "source_file_size": 512,
             "status": "imported", "stage": "import"},
        ]
        mock_pipeline_repo.get_run_by_id.return_value = {
            "id": 1, "source_file_name": "a.pdf",
            "source_mime_type": "image/jpeg", "source_file_size": 512,
            "status": "imported", "stage": "import",
        }
        automation_view._refresh_from_db()
        automation_view._select_run(1)
        assert automation_view._selected_run_id == 1

    def test_update_selected_run_populates_detail(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.list_runs.return_value = [
            {"id": 1, "source_file_name": "a.pdf",
             "source_mime_type": "image/jpeg", "source_file_size": 512,
             "status": "imported", "stage": "import"},
        ]
        mock_pipeline_repo.get_run_by_id.return_value = {
            "id": 1, "source_file_name": "a.pdf",
            "source_mime_type": "image/jpeg", "source_file_size": 512,
            "status": "imported", "stage": "import",
            "extracted_data_json": "{}",
        }
        automation_view._refresh_from_db()
        automation_view._select_run(1)
        assert automation_view._detail._current_run_id == 1


# =========================================================================
# Lifecycle — shutdown / wakeup
# =========================================================================


class TestQtAutomationViewLifecycle:
    """shutdown() and wakeup() are safe and idempotent."""

    def test_shutdown_does_not_crash(self, automation_view):
        automation_view.shutdown()

    def test_shutdown_is_idempotent(self, automation_view):
        automation_view.shutdown()
        automation_view.shutdown()

    def test_wakeup_does_not_crash(self, automation_view):
        automation_view.wakeup()


# =========================================================================
# Public API — selected_trip_id, package_requested, send_requested
# =========================================================================


class TestQtAutomationViewPublicAPI:
    """Public convenience methods behave correctly."""

    def test_selected_trip_id_none_when_no_selection(self, automation_view):
        assert automation_view.selected_trip_id() is None

    def test_selected_trip_id_none_when_run_not_found(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.get_run_by_id.return_value = None
        automation_view._selected_run_id = 1
        assert automation_view.selected_trip_id() is None

    def test_selected_trip_id_returns_value(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.get_run_by_id.return_value = {
            "id": 1, "matched_trip_id": 42,
        }
        automation_view._selected_run_id = 1
        assert automation_view.selected_trip_id() == 42

    def test_prepare_package_emits_signal(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.get_run_by_id.return_value = {
            "id": 1, "matched_trip_id": 42,
        }
        automation_view._selected_run_id = 1
        received = []
        automation_view.package_requested.connect(received.append)
        result = automation_view.prepare_package_for_selected_trip()
        assert result == 42
        assert received == [42]

    def test_prepare_package_returns_none_when_no_trip(self, automation_view):
        result = automation_view.prepare_package_for_selected_trip()
        assert result is None

    def test_send_documents_emits_signal(self, automation_view, mock_pipeline_repo):
        mock_pipeline_repo.get_run_by_id.return_value = {
            "id": 1, "matched_trip_id": 99,
        }
        automation_view._selected_run_id = 1
        received = []
        automation_view.send_requested.connect(received.append)
        result = automation_view.send_documents_for_selected_trip()
        assert result == 99
        assert received == [99]

    def test_send_documents_returns_none_when_no_trip(self, automation_view):
        result = automation_view.send_documents_for_selected_trip()
        assert result is None


# =========================================================================
# DropZone  (standalone widget tests)
# =========================================================================


class TestDropZone:
    """DropZone widget works correctly in isolation."""

    def test_creation(self, qtbot):
        dz = DropZone()
        qtbot.addWidget(dz)
        assert dz.acceptDrops() is True
        assert dz.minimumHeight() >= 120
        assert dz.objectName() == "automationDropZone"

    def test_has_labels(self, qtbot):
        dz = DropZone()
        qtbot.addWidget(dz)
        labels = dz.findChildren(QLabel)
        assert len(labels) >= 2

    def test_drag_enter_does_not_crash(self, qtbot):
        """Calling dragEnterEvent with empty mime data does not crash."""
        dz = DropZone()
        qtbot.addWidget(dz)
        from PySide6.QtCore import QMimeData, QPoint
        from PySide6.QtGui import QDragEnterEvent
        mime = QMimeData()
        mime.setUrls([])
        event = QDragEnterEvent(QPoint(0, 0), Qt.DropAction.CopyAction, mime,
                                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        dz.dragEnterEvent(event)

    def test_drag_leave_does_not_crash(self, qtbot):
        """Calling dragLeaveEvent does not crash."""
        dz = DropZone()
        qtbot.addWidget(dz)
        dz.dragLeaveEvent(None)  # must not crash


# =========================================================================
# _RunDetailPanel  (standalone widget tests)
# =========================================================================


class TestRunDetailPanel:
    """_RunDetailPanel widget works correctly in isolation."""

    def test_creation(self, qtbot):
        panel = _RunDetailPanel()
        qtbot.addWidget(panel)
        assert panel.objectName() == "automationDetailPanel"

    def test_clear_resets_state(self, qtbot):
        panel = _RunDetailPanel()
        qtbot.addWidget(panel)
        panel.clear()
        assert panel._current_run_id is None
        assert panel._current_trip_id is None
        assert panel._prepare_btn.isEnabled() is False
        assert panel._send_btn.isEnabled() is False

    def test_initial_title(self, qtbot):
        panel = _RunDetailPanel()
        qtbot.addWidget(panel)
        assert panel._title is not None
        assert "Select a run" in panel._title.text()

    def test_signals_exist(self, qtbot):
        panel = _RunDetailPanel()
        qtbot.addWidget(panel)
        assert hasattr(panel, "prepare_clicked")
        assert hasattr(panel, "send_clicked")
        assert hasattr(panel, "link_requested")
        assert hasattr(panel, "skip_and_package_clicked")
        assert hasattr(panel, "delete_requested")

    def test_prepare_btn_emits_signal(self, qtbot):
        panel = _RunDetailPanel()
        qtbot.addWidget(panel)
        received = []
        panel.prepare_clicked.connect(received.append)
        panel._on_prepare_clicked()
        # No current_trip_id set, so nothing emitted
        assert received == []
        panel._current_trip_id = 7
        panel._on_prepare_clicked()
        assert received == [7]

    def test_send_btn_emits_signal(self, qtbot):
        panel = _RunDetailPanel()
        qtbot.addWidget(panel)
        received = []
        panel.send_clicked.connect(received.append)
        panel._on_send_clicked()
        assert received == []
        panel._current_trip_id = 3
        panel._on_send_clicked()
        assert received == [3]

    def test_skip_btn_emits_signal(self, qtbot):
        panel = _RunDetailPanel()
        qtbot.addWidget(panel)
        received = []
        panel.skip_and_package_clicked.connect(received.append)
        panel._on_skip_clicked()
        assert received == []
        panel._current_run_id = 10
        panel._on_skip_clicked()
        assert received == [10]


# =========================================================================
# _RunCard  (standalone widget tests)
# =========================================================================


class TestRunCard:
    """_RunCard widget works correctly in isolation."""

    def test_creation(self, qtbot):
        run = {"id": 1, "source_file_name": "test.pdf",
               "status": "imported", "stage": "import"}
        card = _RunCard(run)
        qtbot.addWidget(card)
        assert card.run_id == 1
        assert "test.pdf" in card._title.text()

    def test_click_emits_run_id(self, qtbot):
        run = {"id": 42, "source_file_name": "doc.pdf",
               "status": "imported", "stage": "import"}
        card = _RunCard(run)
        qtbot.addWidget(card)
        received = []
        card.clicked.connect(received.append)
        qtbot.mouseClick(card, Qt.LeftButton)
        assert received == [42]

    def test_update_changes_title(self, qtbot):
        run = {"id": 1, "source_file_name": "old.pdf",
               "status": "imported", "stage": "import"}
        card = _RunCard(run)
        qtbot.addWidget(card)
        card.update({"id": 1, "source_file_name": "new.pdf",
                     "status": "processing", "stage": "processing"})
        assert "new.pdf" in card._title.text()

    def test_update_changes_stage(self, qtbot):
        run = {"id": 1, "source_file_name": "a.pdf",
               "status": "imported", "stage": "import"}
        card = _RunCard(run)
        qtbot.addWidget(card)
        original_stage = card._stage_lbl.text()
        card.update({"id": 1, "source_file_name": "a.pdf",
                     "status": "complete", "stage": "complete"})
        updated_stage = card._stage_lbl.text()
        assert updated_stage != original_stage or original_stage == "complete"

    def test_progress_bar_created(self, qtbot):
        run = {"id": 1, "source_file_name": "a.pdf",
               "status": "imported", "stage": "import"}
        card = _RunCard(run)
        qtbot.addWidget(card)
        assert card._progress is not None
        assert card._progress.minimum() == 0
        assert card._progress.maximum() == 100
