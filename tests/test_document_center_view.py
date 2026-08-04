"""Tests for the document center view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def document_center(qt_widget, qtbot):
    db = MagicMock()
    # Mock conn.execute to return sensible values for document queries
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = None
    mock_cursor.description = ()
    db.conn.execute.return_value = mock_cursor
    # Prevent errors from rows_to_dicts on MagicMock results
    db.rows_to_dicts = MagicMock(return_value=[])
    db.row_to_dict = MagicMock(return_value={})
    prefs = MagicMock()
    ops = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.document_center_view", fromlist=["QtDocumentCenterView"]).QtDocumentCenterView(
        qt_widget, db=db, prefs=prefs, ops=ops, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


class TestQtDocumentCenterView:
    def test_creation(self, document_center):
        assert document_center.db is not None

    def test_document_table_created(self, document_center):
        # The document center uses a widget-based list, not a QTableWidget
        assert hasattr(document_center, "_list_content") or hasattr(document_center, "_list_layout")

    def test_search_bar_created(self, document_center):
        assert hasattr(document_center, "_search_entry")

    def test_filter_controls_exist(self, document_center):
        assert hasattr(document_center, "_filter_panel") or hasattr(document_center, "_entity_type_combo")

    def test_bulk_action_buttons(self, document_center):
        assert hasattr(document_center, "_batch_del_btn") or hasattr(document_center, "_batch_zip_btn")

    def test_shutdown_cleanup(self, document_center):
        document_center.shutdown()
