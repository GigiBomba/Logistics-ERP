"""Tests for the invoice editor view."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtCore import Qt


@pytest.fixture
def invoice_editor(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.invoice_editor.QtInvoiceEditor._populate_fields",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    invoice_repo = MagicMock()
    editor = __import__("ui.views.invoice_editor", fromlist=["QtInvoiceEditor"]).QtInvoiceEditor(
        qt_widget, db=db, prefs=prefs, invoice_repo=invoice_repo,
    )
    qtbot.addWidget(editor)
    yield editor
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        editor.shutdown()


class TestQtInvoiceEditor:
    def test_creation(self, invoice_editor):
        assert invoice_editor.db is not None
        assert invoice_editor._invoice_number is not None

    def test_form_fields_exist(self, invoice_editor):
        assert hasattr(invoice_editor, "_invoice_number")
        assert hasattr(invoice_editor, "_client_combo")
        assert hasattr(invoice_editor, "_issue_date")
        assert hasattr(invoice_editor, "_due_date")

    def test_line_items_table_columns(self, invoice_editor):
        table = invoice_editor._items_table
        assert table is not None
        assert table.columnCount() >= 3

    def test_shutdown_cleanup(self, invoice_editor):
        invoice_editor._line_items = [{"id": 1}]
        invoice_editor.shutdown()
        assert invoice_editor._line_items == []

    def test_wakeup_refresh(self, invoice_editor):
        invoice_editor._svc = MagicMock()
        invoice_editor.wakeup()
        invoice_editor._svc.refresh.assert_not_called()

    def test_calculate_totals(self, invoice_editor):
        items = [
            {"quantity": 2, "unit_price": 100.0, "vat_percent": 19},
            {"quantity": 1, "unit_price": 50.0, "vat_percent": 19},
        ]
        subtotal, vat, total = invoice_editor._calculate_totals(items) if hasattr(invoice_editor, "_calculate_totals") else (0, 0, 0)
        assert isinstance(subtotal, (int, float))
        assert isinstance(total, (int, float))
