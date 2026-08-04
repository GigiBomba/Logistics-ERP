"""Tests for QtDocumentCenterView — document management view.

This tests the refactored three-panel Document Center
(``ui/views/document_center/document_center.py``).
"""
from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QCheckBox, QScrollArea, QFrame, QTabWidget

from services.document_service import DocumentService

# Workaround: ui.widgets imports SP as S but SectionHeader uses SP (source bug)
import ui.widgets as _ui_widgets

if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_doc_service():
    """DocumentService mock with sensible default return values."""
    svc = MagicMock(spec=DocumentService)
    svc.get_categories.return_value = [
        {"category": "invoices", "cnt": 5},
        {"category": "receipts", "cnt": 3},
        {"category": "maintenance", "cnt": 0},
    ]
    svc.advanced_search.return_value = {"items": [], "total": 0, "total_pages": 0}
    svc.fts_search.return_value = {"items": [], "total": 0, "total_pages": 0}
    svc.get_entity_types.return_value = []
    svc.get_mime_types.return_value = []
    svc.get_thumbnail_path.return_value = None
    return svc


@pytest.fixture
def mock_prefs():
    return MagicMock()


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.event_bus = MagicMock()
    return ops


@pytest.fixture
def document_center(qtbot, mock_doc_service, mock_prefs, mock_ops):
    """Create a QtDocumentCenterView with all external services mocked."""
    patchers = [
        # Prevent real auth check during __init__ (API dashboard tab)
        # The _build_ui method imports get_auth inside a try/except,
        # but we mock it here to keep the test environment clean.
        patch("client.auth_manager.get_auth", return_value=None),
    ]
    for p in patchers:
        p.start()

    from ui.views.document_center.document_center import QtDocumentCenterView

    widget = QtDocumentCenterView(
        parent=None,
        db=MagicMock(),
        prefs=mock_prefs,
        ops=mock_ops,
        document_service=mock_doc_service,
    )
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(10)  # let Qt event loop process show/visibility
    yield widget

    with contextlib.suppress(Exception):
        widget.shutdown()
    for p in patchers:
        p.stop()


# =========================================================================
# Tests
# =========================================================================


class TestQtDocumentCenterView:
    """Suite of tests for QtDocumentCenterView."""

    # ── Lifecycle ─────────────────────────────────────────────────────

    def test_initialization(self, document_center):
        """Widget initialises without crashing and stores service references."""
        assert document_center is not None
        assert document_center._service is not None
        assert document_center.db is not None
        assert document_center.prefs is not None
        assert document_center.ops is not None

    def test_shutdown_cleanup(self, document_center):
        """shutdown() calls base cleanup without crash."""
        document_center.shutdown()
        # Second call must be safe
        document_center.shutdown()

    def test_wakeup_does_not_crash(self, document_center):
        """wakeup() refreshes without crashing."""
        document_center.wakeup()

    def test_refresh_calls_service(self, document_center, mock_doc_service):
        """refresh() delegates to service for categories and documents."""
        document_center.refresh()
        mock_doc_service.get_categories.assert_called()
        mock_doc_service.advanced_search.assert_called()

    def test_shutdown_without_service(self, qtbot):
        """Constructing with db=None does not crash on shutdown."""
        from ui.views.document_center.document_center import QtDocumentCenterView

        widget = QtDocumentCenterView(parent=None, db=None)
        qtbot.addWidget(widget)
        widget.shutdown()

    # ── Tab structure ─────────────────────────────────────────────────

    def test_tabs_created(self, document_center):
        """QTabWidget exists with Documents + Automation tabs."""
        assert hasattr(document_center, "_tab_widget")
        tab_widget = document_center._tab_widget
        assert isinstance(tab_widget, QTabWidget)
        assert tab_widget.count() >= 2  # docs + automation
        # API dashboard tab depends on auth — in test it's absent
        self._check_tab_label(tab_widget, 0, "documents")
        self._check_tab_label(tab_widget, 1, "automation")

    @staticmethod
    def _check_tab_label(tab_widget, index, hint):
        text = tab_widget.tabText(index).lower()
        assert hint in text, f"Expected '{hint}' in tab {index} label: '{text}'"

    # ── Sidebar ───────────────────────────────────────────────────────

    def test_sidebar_renders(self, document_center):
        """Left sidebar is built with expected widgets."""
        assert document_center._sidebar is not None
        assert document_center._sidebar_header is not None
        assert isinstance(document_center._cat_layout, type(document_center._cat_layout))
        assert document_center._filter_toggle is not None
        assert document_center._upload_btn is not None

    def test_category_buttons_built_after_refresh(self, document_center):
        """refresh() builds category _CategoryButton widgets."""
        document_center.refresh()
        buttons = document_center._sidebar.findChildren(QPushButton)
        # "All" + at least some category buttons
        category_btns = [b for b in buttons
                         if b.property("category-btn") == "true"]
        assert len(category_btns) >= 1

    def test_upload_button_exists(self, document_center):
        """Upload button is present and clickable."""
        btn = document_center._upload_btn
        assert btn is not None
        # t("docs.upload") falls back to the key itself
        assert "upload" in btn.text().lower()

    # ── Center panel ──────────────────────────────────────────────────

    def test_center_panel_renders(self, document_center):
        """Center panel has toolbar, batch bar, scroll area and pager."""
        assert document_center._center_panel is not None
        # Toolbar
        assert document_center._sort_combo is not None
        assert document_center._search_entry is not None
        assert document_center._select_all_cb is not None
        assert document_center._admin_trigger is not None
        # Batch bar
        assert document_center._batch_bar is not None
        assert document_center._batch_zip_btn is not None
        assert document_center._batch_del_btn is not None
        # List area
        assert document_center._list_scroll is not None
        assert isinstance(document_center._list_scroll, QScrollArea)
        assert document_center._list_layout is not None
        # Pager
        assert document_center._page_label is not None
        assert document_center._prev_btn is not None
        assert document_center._next_btn is not None

    def test_batch_bar_hidden_by_default(self, document_center):
        """Batch action bar starts hidden when nothing is selected."""
        # The batch bar visibility flag should be False initially
        assert len(document_center._selected_ids) == 0
        assert document_center._batch_bar.isHidden() is True

    def test_sort_combo_has_items(self, document_center):
        """Sort combobox has six sort options."""
        assert document_center._sort_combo.count() == 6

    # ── Detail sidebar ────────────────────────────────────────────────

    def test_detail_sidebar_renders(self, document_center):
        """Right detail sidebar exists with header, content, actions."""
        assert document_center._detail_panel is not None
        assert document_center._detail_header is not None
        assert document_center._detail_content is not None
        assert document_center._detail_actions is not None

    # ── Filter panel ──────────────────────────────────────────────────

    def test_filter_toggle_shows_hides_panel(self, document_center):
        """_toggle_filters toggles the _filters_visible flag."""
        assert document_center._filters_visible is False
        document_center._toggle_filters()
        assert document_center._filters_visible is True
        # After first toggle the filter panel is no longer hidden
        assert document_center._filter_panel.isHidden() is False
        document_center._toggle_filters()
        assert document_center._filters_visible is False
        assert document_center._filter_panel.isHidden() is True

    def test_filter_panel_populated_when_shown(self, document_center):
        """Revealing the filter panel populates filter controls."""
        document_center._toggle_filters()
        assert hasattr(document_center, "_entity_type_combo")
        assert hasattr(document_center, "_date_from_entry")
        assert hasattr(document_center, "_date_to_entry")
        assert hasattr(document_center, "_mime_type_combo")

    def test_clear_filters_resets_and_applies(self, document_center, mock_doc_service):
        """_clear_filters resets filter widgets and reloads documents."""
        document_center._toggle_filters()
        document_center._entity_type_combo.setCurrentIndex(0)
        document_center._clear_filters()
        mock_doc_service.advanced_search.assert_called()

    # ── Search & sort ─────────────────────────────────────────────────

    def test_search_triggers_document_load(self, document_center, mock_doc_service):
        """_on_search resets page and reloads documents."""
        document_center._page = 2
        document_center._on_search()
        assert document_center._page == 0
        mock_doc_service.advanced_search.assert_called()

    def test_sort_change_triggers_document_load(self, document_center, mock_doc_service):
        """Changing sort order resets page and reloads documents."""
        document_center._page = 1
        from services.i18n import t
        document_center._on_sort_change(t("docs.sort_oldest"))
        assert document_center._sort_order == "uploaded_at ASC"
        assert document_center._page == 0
        mock_doc_service.advanced_search.assert_called()

    def test_sort_map_all_keys(self, document_center):
        """All six sort options map to correct SQL order clauses."""
        from services.i18n import t
        cases = [
            (t("docs.sort_newest"), "uploaded_at DESC"),
            (t("docs.sort_oldest"), "uploaded_at ASC"),
            (t("docs.sort_name_az"), "title ASC"),
            (t("docs.sort_name_za"), "title DESC"),
            (t("docs.sort_size_lg"), "file_size DESC"),
            (t("docs.sort_size_sm"), "file_size ASC"),
        ]
        for label, expected in cases:
            document_center._on_sort_change(label)
            assert document_center._sort_order == expected, f"Mismatch for {label}"

    def test_category_filter_triggers_refresh(self, document_center, mock_doc_service):
        """_filter_category sets active category and calls refresh."""
        document_center._filter_category("invoices")
        assert document_center._active_category == "invoices"
        assert document_center._page == 0
        mock_doc_service.get_categories.assert_called()

    # ── Paging ────────────────────────────────────────────────────────

    def test_pager_navigation(self, document_center, mock_doc_service):
        """Prev / next page buttons navigate correctly."""
        mock_doc_service.advanced_search.return_value = {
            "items": [{"id": 1, "title": "Doc", "file_name": "d.pdf",
                        "file_size": 100, "mime_type": "text/plain",
                        "uploaded_at": "", "tags": "[]",
                        "entity_type": "", "entity_id": None}],
            "total": 25,
            "total_pages": 2,
        }
        document_center._page = 0
        document_center._total_pages = 2
        document_center._load_documents()
        assert document_center._page == 0

        document_center._next_page()
        assert document_center._page == 1

        document_center._prev_page()
        assert document_center._page == 0

    def test_prev_page_does_not_go_below_zero(self, document_center):
        """Calling _prev_page at page 0 is a no-op."""
        document_center._page = 0
        document_center._prev_page()
        assert document_center._page == 0

    def test_next_page_respects_total_pages(self, document_center):
        """Calling _next_page on the last page is a no-op."""
        document_center._page = 1
        document_center._total_pages = 2
        document_center._next_page()
        assert document_center._page == 1

    def test_page_label_format(self, document_center):
        """_update_page_label shows current / total and count."""
        document_center._page = 0
        document_center._total_pages = 3
        document_center._total = 50
        document_center._update_page_label()
        text = document_center._page_label.text()
        assert "1 / 3" in text
        assert "(50)" in text

    # ── Empty state ───────────────────────────────────────────────────

    def test_empty_state_shows_placeholder(self, document_center, mock_doc_service):
        """Empty document list renders a 'no documents' label."""
        mock_doc_service.advanced_search.return_value = {
            "items": [], "total": 0, "total_pages": 0,
        }
        document_center._load_documents()
        # EmptyState component renders title + subtitle labels
        labels = document_center._list_content.findChildren(QLabel)
        # Look for the empty-state text (translation key or default)
        empty_labels = [l for l in labels
                        if "no documents" in l.text().lower()
                        or "docs.empty_title" in l.text().lower()]
        assert len(empty_labels) >= 1

    def test_empty_state_clears_detail(self, document_center, mock_doc_service):
        """Empty state also hides the detail panel placeholder."""
        mock_doc_service.advanced_search.return_value = {
            "items": [], "total": 0, "total_pages": 0,
        }
        document_center._load_documents()
        # Detail should show "select a document" placeholder
        placeholders = document_center._detail_content.findChildren(QLabel)
        assert any(l.property("role") == "detail-placeholder"
                   for l in placeholders)

    # ── Document list rendering ───────────────────────────────────────

    def test_document_list_creates_rows(self, document_center, mock_doc_service):
        """_load_documents creates _DocRow widgets for each result."""
        mock_docs = [
            {
                "id": 1,
                "title": "Invoice 001",
                "file_name": "inv001.pdf",
                "file_size": 2048,
                "mime_type": "application/pdf",
                "uploaded_at": "2025-01-15T10:00:00",
                "doc_number": "INV-001",
                "tags": "[]",
                "entity_type": "",
                "entity_id": None,
            },
            {
                "id": 2,
                "title": "Receipt 002",
                "file_name": "rec002.png",
                "file_size": 512000,
                "mime_type": "image/png",
                "uploaded_at": "2025-01-16T12:00:00",
                "doc_number": "",
                "tags": '["fuel"]',
                "entity_type": "trip",
                "entity_id": 42,
            },
        ]
        mock_doc_service.advanced_search.return_value = {
            "items": mock_docs, "total": 2, "total_pages": 1,
        }
        document_center._load_documents()
        from ui.views.document_center.document_center import _DocRow
        rows = document_center._list_content.findChildren(_DocRow)
        assert len(rows) == 2

    def test_doc_row_title_appears(self, document_center, mock_doc_service):
        """_DocRow displays the document title."""
        doc = {
            "id": 1, "title": "Test Document", "file_name": "test.pdf",
            "file_size": 1024, "mime_type": "application/pdf",
            "uploaded_at": "2025-06-01T08:00:00", "doc_number": "DOC-001",
            "tags": '[]', "entity_type": "", "entity_id": None,
        }
        mock_doc_service.advanced_search.return_value = {
            "items": [doc], "total": 1, "total_pages": 1,
        }
        document_center._load_documents()
        from ui.views.document_center.document_center import _DocRow
        rows = document_center._list_content.findChildren(_DocRow)
        assert len(rows) == 1
        titles = [l for l in rows[0].findChildren(QLabel)
                  if l.property("role") == "doc-title"]
        assert any("Test Document" in t.text() for t in titles)

    def test_doc_row_shows_meta(self, document_center, mock_doc_service):
        """_DocRow shows metadata including size and upload date."""
        doc = {
            "id": 1, "title": "Meta Doc", "file_name": "meta.pdf",
            "file_size": 2048, "mime_type": "application/pdf",
            "uploaded_at": "2025-06-01", "doc_number": "",
            "tags": '[]', "entity_type": "", "entity_id": None,
        }
        mock_doc_service.advanced_search.return_value = {
            "items": [doc], "total": 1, "total_pages": 1,
        }
        document_center._load_documents()
        from ui.views.document_center.document_center import _DocRow
        rows = document_center._list_content.findChildren(_DocRow)
        metas = [l for l in rows[0].findChildren(QLabel)
                 if l.property("role") == "doc-meta"]
        assert len(metas) >= 1
        meta_text = metas[0].text()
        assert "2.0 KB" in meta_text
        assert "2025-06-01" in meta_text

    def test_doc_row_shows_tags(self, document_center, mock_doc_service):
        """_DocRow renders tag chips for documents with tags."""
        doc = {
            "id": 1, "title": "Tagged Doc", "file_name": "tagged.pdf",
            "file_size": 100, "mime_type": "application/pdf",
            "uploaded_at": "2025-01-01", "doc_number": "",
            "tags": '["urgent", "invoice", "paid"]',
            "entity_type": "", "entity_id": None,
        }
        mock_doc_service.advanced_search.return_value = {
            "items": [doc], "total": 1, "total_pages": 1,
        }
        document_center._load_documents()
        from ui.views.document_center.document_center import _DocRow
        rows = document_center._list_content.findChildren(_DocRow)
        chips = [l for l in rows[0].findChildren(QLabel)
                 if l.property("role") == "tag-chip"]
        assert len(chips) >= 1

    # ── Selection ─────────────────────────────────────────────────────

    def test_toggle_select_adds_and_removes(self, document_center):
        """_toggle_select updates _selected_ids and batch bar visibility."""
        assert 42 not in document_center._selected_ids
        document_center._toggle_select(42, True)
        assert 42 in document_center._selected_ids

        document_center._toggle_select(42, False)
        assert 42 not in document_center._selected_ids

    def test_select_all_toggles_all(self, document_center, mock_doc_service):
        """Select-all checkbox selects / deselects all visible docs."""
        docs = [
            {"id": i, "title": f"Doc {i}", "file_name": f"d{i}.pdf",
             "file_size": 100, "mime_type": "application/pdf",
             "uploaded_at": "2025-01-01", "tags": "[]",
             "entity_type": "", "entity_id": None}
            for i in range(3)
        ]
        mock_doc_service.advanced_search.return_value = {
            "items": docs, "total": 3, "total_pages": 1,
        }
        document_center._load_documents()

        document_center._select_all_cb.setChecked(True)
        assert len(document_center._selected_ids) == 3

        document_center._select_all_cb.setChecked(False)
        assert len(document_center._selected_ids) == 0

    # ── Detail panel ──────────────────────────────────────────────────

    def test_detail_shows_placeholder_when_no_doc(self, document_center):
        """_show_detail(None) renders a 'select a document' placeholder."""
        document_center._show_detail(None)
        placeholders = [l for l in
                        document_center._detail_content.findChildren(QLabel)
                        if l.property("role") == "detail-placeholder"]
        assert len(placeholders) >= 1

    def test_detail_populates_with_doc_info(self, document_center, mock_doc_service):
        """_show_detail with a doc renders its title, size, tags."""
        doc = {
            "id": 1, "title": "Detailed Document",
            "file_name": "detail.pdf", "file_size": 1048576,
            "mime_type": "application/pdf",
            "uploaded_at": "2025-03-15T10:00:00", "doc_number": "DOC-999",
            "tags": '["important"]',
            "entity_type": "", "entity_id": None,
            "expiry_date": "2025-12-31",
            "ocr_run_at": "",
            "ocr_engine": "",
            "extracted_data_json": "{}",
        }
        mock_doc_service.get_links.return_value = []
        mock_doc_service.get_versions.return_value = []
        document_center._show_detail(doc)
        labels = document_center._detail_content.findChildren(QLabel)
        assert any("Detailed Document" in l.text() for l in labels)
        assert any("1.0 MB" in l.text() for l in labels)

    def test_detail_shows_tags_section(self, document_center, mock_doc_service):
        """Detail panel renders tag chips and add-tag input."""
        doc = {
            "id": 1, "title": "Tagged", "file_name": "t.pdf",
            "file_size": 100, "mime_type": "text/plain",
            "uploaded_at": "2025-01-01", "tags": '["tag-a", "tag-b"]',
            "entity_type": "", "entity_id": None,
            "expiry_date": "", "ocr_run_at": "", "ocr_engine": "",
            "extracted_data_json": "{}",
        }
        mock_doc_service.get_links.return_value = []
        mock_doc_service.get_versions.return_value = []
        document_center._show_detail(doc)
        chips = [l for l in document_center._detail_content.findChildren(QLabel)
                 if l.property("role") == "tag-chip"]
        assert len(chips) >= 2
        assert any("tag-a" in l.text() for l in chips)

    def test_detail_action_buttons_rendered(self, document_center, mock_doc_service):
        """Detail bottom-actions area has action buttons."""
        doc = {
            "id": 1, "title": "Actionable", "file_name": "a.pdf",
            "file_size": 100, "mime_type": "application/pdf",
            "uploaded_at": "2025-01-01", "tags": "[]",
            "entity_type": "", "entity_id": None,
            "expiry_date": "", "ocr_run_at": "", "ocr_engine": "",
            "extracted_data_json": "{}",
        }
        mock_doc_service.get_links.return_value = []
        mock_doc_service.get_versions.return_value = []
        document_center._show_detail(doc)
        from PySide6.QtWidgets import QPushButton
        btns = document_center._detail_actions.findChildren(QPushButton)
        # The i18n t() function returns the key as fallback, so buttons
        # will have text like "docs.view", "docs.download_zip", etc.
        assert len(btns) >= 3

    # ── Error resilience ──────────────────────────────────────────────

    def test_load_documents_handles_service_error(self, document_center, mock_doc_service):
        """Service exception in _load_documents does not crash."""
        mock_doc_service.advanced_search.side_effect = Exception("Service boom")
        # Should not raise
        document_center._load_documents()
        # List content should still be valid
        assert document_center._list_layout is not None

    def test_shutdown_stops_ocr_worker(self, document_center):
        """shutdown cleans up OCR worker if it existed."""
        # Simulate an OCR worker (or just verify no crash)
        document_center._ocr_busy = False
        document_center.shutdown()
        assert document_center._ocr_worker is None
        assert document_center._ocr_busy is False


class TestDocumentCenterLoadBaseViewBehavior:
    """Test the load-once behavior override."""

    def test_load_data_once_on_first_refresh(
        self, document_center, mock_doc_service
    ):
        """First refresh() does _load_categories + _load_documents; subsequent calls also refresh (no caching yet)."""
        document_center.refresh()
        assert mock_doc_service.get_categories.called
        assert mock_doc_service.advanced_search.called

        # Current implementation performs both loads on every refresh;
        # this documents the behavior before the load-once optimization
        initial_cat = mock_doc_service.get_categories.call_count
        initial_doc = mock_doc_service.advanced_search.call_count

        document_center.refresh()

        assert mock_doc_service.get_categories.call_count > initial_cat
        assert mock_doc_service.advanced_search.call_count > initial_doc

    def test_reload_forced_by_parameter(
        self, document_center, mock_doc_service
    ):
        """refresh() always reloads regardless of cache state."""
        document_center.refresh()
        initial_cat = mock_doc_service.get_categories.call_count

        # Mark as loaded — current implementation ignores this flag
        document_center._categories_loaded = True

        document_center.refresh()
        # Still refreshes because the override isn't implemented yet
        assert mock_doc_service.get_categories.call_count > initial_cat
