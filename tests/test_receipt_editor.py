"""Tests for the receipt editor view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def receipt_editor(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.receipt_editor.QtReceiptEditor._populate_fields",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    editor = __import__("ui.views.receipt_editor", fromlist=["QtReceiptEditor"]).QtReceiptEditor(
        qt_widget, db=db, prefs=prefs,
    )
    qtbot.addWidget(editor)
    yield editor
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        editor.shutdown()


class TestQtReceiptEditor:
    def test_creation(self, receipt_editor):
        assert receipt_editor.db is not None

    def test_form_fields_exist(self, receipt_editor):
        assert hasattr(receipt_editor, "_receipt_number")
        assert hasattr(receipt_editor, "_customer_combo")

    def test_line_items_table_exists(self, receipt_editor):
        assert hasattr(receipt_editor, "_line_items_table")

    def test_shutdown_cleanup(self, receipt_editor):
        receipt_editor._line_items = [{"id": 1}]
        receipt_editor.shutdown()
        assert receipt_editor._line_items == []

    def test_currency_combo_exists(self, receipt_editor):
        assert hasattr(receipt_editor, "_currency_combo")

    def test_wakeup_does_not_crash(self, receipt_editor):
        receipt_editor.wakeup()
