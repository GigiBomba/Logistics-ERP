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

    def test_default_discount_type_matches_combo_index_zero(self, proforma_editor):
        # The discount combo defaults to index 0 ("Percentage") without firing
        # its change handler (the signal is connected after addItems), so the
        # backing field must default to "percentage" as well.
        assert proforma_editor._disc_type_combo.currentIndex() == 0
        assert proforma_editor._discount_type == "percentage"

    def test_collect_applies_percentage_discount_without_touching_combo(
        self, proforma_editor,
    ):
        # Regression: a discount typed on a fresh editor (combo untouched, so
        # the field keeps its default) must be applied as a percentage.
        proforma_editor._proforma_number = "PROF-TEST-0001"
        proforma_editor._addon_items = [
            {"description": "Transport", "quantity": 2,
             "unit_price": 50.0, "amount": 100.0},
        ]
        proforma_editor._discount_value = "10"
        data = proforma_editor._collect_proforma_data()
        assert data["subtotal"] == pytest.approx(100.0)
        assert data["discount"] == pytest.approx(0.10 * 100.0)
        assert data["discount_type"] == "Discount %"

    def test_collect_unknown_discount_type_yields_zero_discount(
        self, proforma_editor,
    ):
        # Unknown/empty type must never produce wrong math and must serialize
        # to an empty discount-type display.
        proforma_editor._proforma_number = "PROF-TEST-0002"
        proforma_editor._addon_items = [
            {"description": "Transport", "quantity": 2,
             "unit_price": 50.0, "amount": 100.0},
        ]
        proforma_editor._discount_value = "10"
        proforma_editor._discount_type = ""
        data = proforma_editor._collect_proforma_data()
        assert data["discount"] == 0
        assert data["discount_type"] == ""

    def test_draft_roundtrip_percentage_discount(self, proforma_editor):
        # Regression: a draft saved with a percentage discount must restore to
        # _discount_type == "percentage" and apply the value as a percentage.
        proforma_editor._proforma_number = "PROF-TEST-0003"
        proforma_editor._addon_items = [
            {"description": "Transport", "quantity": 2,
             "unit_price": 50.0, "amount": 100.0},
        ]
        proforma_editor._discount_type = "percentage"
        proforma_editor._discount_value = "10"
        draft = proforma_editor._collect_draft_data()
        # Drafts are internal JSON: store the canonical token, not the display.
        assert draft["discount_type"] == "percentage"
        # Deliberately desync the backing field so the restore must fix it.
        proforma_editor._discount_type = "fixed"
        proforma_editor._restore_from_draft(draft)
        assert proforma_editor._discount_type == "percentage"
        data = proforma_editor._collect_proforma_data()
        assert data["discount"] == pytest.approx(10.0)  # 10% of 100

    def test_draft_roundtrip_fixed_discount(self, proforma_editor):
        # Regression: a draft saved with a fixed discount must restore to
        # _discount_type == "fixed" and apply the value as a fixed amount.
        proforma_editor._proforma_number = "PROF-TEST-0004"
        proforma_editor._addon_items = [
            {"description": "Transport", "quantity": 2,
             "unit_price": 50.0, "amount": 100.0},
        ]
        proforma_editor._discount_type = "fixed"
        proforma_editor._discount_value = "10"
        draft = proforma_editor._collect_draft_data()
        assert draft["discount_type"] == "fixed"
        # Deliberately desync the backing field so the restore must fix it.
        proforma_editor._discount_type = "percentage"
        proforma_editor._restore_from_draft(draft)
        assert proforma_editor._discount_type == "fixed"
        data = proforma_editor._collect_proforma_data()
        assert data["discount"] == pytest.approx(10.0)  # fixed amount

    @pytest.mark.parametrize("legacy_type", ["Discount %", "Percentage"])
    def test_restore_legacy_display_string_discount_type(
        self, proforma_editor, legacy_type,
    ):
        # Legacy drafts stored the display text instead of the canonical token;
        # restore must still fall back to a percentage discount.
        draft = {
            "proforma_number": "PROF-TEST-0005",
            "discount_type": legacy_type,
            "discount_value": 10,
            "addon_items": [
                {"description": "Transport", "quantity": 2,
                 "unit_price": 50.0, "amount": 100.0},
            ],
        }
        proforma_editor._restore_from_draft(draft)
        assert proforma_editor._discount_type == "percentage"
        data = proforma_editor._collect_proforma_data()
        assert data["discount"] == pytest.approx(10.0)  # 10% of 100
