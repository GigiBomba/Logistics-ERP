"""Tests for the document center view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def document_center(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.document_center_view.QtDocumentCenterView._initial_load",
        lambda self: None,
    )
    db = MagicMock()
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
        assert hasattr(document_center, "_doc_table")
        assert document_center._doc_table is not None

    def test_search_bar_created(self, document_center):
        assert hasattr(document_center, "_search_bar")

    def test_filter_controls_exist(self, document_center):
        assert hasattr(document_center, "_status_filter")

    def test_bulk_action_buttons(self, document_center):
        assert hasattr(document_center, "_btn_delete_selected")

    def test_shutdown_cleanup(self, document_center):
        document_center.shutdown()
