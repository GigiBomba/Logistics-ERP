"""Tests for the proforma editor view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def proforma_editor(qt_widget, qtbot):
    db = MagicMock()
    prefs = MagicMock()
    prefs.get_currency.return_value = "EUR"
    editor = __import__("ui.views.proforma_editor", fromlist=["QtProformaEditor"]).QtProformaEditor(
        qt_widget, db=db, prefs=prefs,
    )
    qtbot.addWidget(editor)
    yield editor
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        editor.shutdown()


class TestQtProformaEditor:
    def test_creation(self, proforma_editor):
        assert proforma_editor.db is not None

    def test_form_fields_exist(self, proforma_editor):
        assert hasattr(proforma_editor, "_proforma_number")
        assert hasattr(proforma_editor, "_client_combo")

    def test_line_items_table_exists(self, proforma_editor):
        assert hasattr(proforma_editor, "_items_table")

    def test_shutdown_cleanup(self, proforma_editor):
        proforma_editor._addon_items = [{"id": 1}]
        proforma_editor.shutdown()
        assert proforma_editor._addon_items == [{"id": 1}]

    def test_currency_combo_exists(self, proforma_editor):
        assert hasattr(proforma_editor, "_curr_combo")

    def test_wakeup_does_not_crash(self, proforma_editor):
        proforma_editor.wakeup()
