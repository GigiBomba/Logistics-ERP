"""Tests for the CMR form view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def cmr_form(qt_widget, qtbot):
    db = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.cmr_form_view", fromlist=["QtCMRFormView"]).QtCMRFormView(
        qt_widget, db=db, prefs=prefs, ops=ops, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtCMRFormView:
    def test_creation(self, cmr_form):
        assert cmr_form.db is not None

    def test_sender_fields_exist(self, cmr_form):
        assert hasattr(cmr_form, "_sender_name")

    def test_recipient_fields_exist(self, cmr_form):
        assert hasattr(cmr_form, "_recipient_name")

    def test_carrier_fields_exist(self, cmr_form):
        assert hasattr(cmr_form, "_carrier_name")

    def test_goods_fields_exist(self, cmr_form):
        assert hasattr(cmr_form, "_goods_description")

    def test_loading_place_fields(self, cmr_form):
        assert hasattr(cmr_form, "_loading_place")

    def test_unloading_place_fields(self, cmr_form):
        assert hasattr(cmr_form, "_unloading_place")

    def test_document_number_field(self, cmr_form):
        assert hasattr(cmr_form, "_cmr_number")

    def test_pdf_generation_btn(self, cmr_form):
        assert hasattr(cmr_form, "_btn_generate_pdf")

    def test_shutdown_cleanup(self, cmr_form):
        cmr_form.shutdown()
