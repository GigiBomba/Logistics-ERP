"""Tests for the tachograph import view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def tacho_import(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.tacho_import_view.QtTachoImportView._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.tacho_import_view", fromlist=["QtTachoImportView"]).QtTachoImportView(
        qt_widget, db=db, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


class TestQtTachoImportView:
    def test_creation(self, tacho_import):
        assert tacho_import.db is not None

    def test_import_button_exists(self, tacho_import):
        assert hasattr(tacho_import, "_btn_import")

    def test_file_list_created(self, tacho_import):
        assert hasattr(tacho_import, "_file_list")

    def test_status_table_created(self, tacho_import):
        assert hasattr(tacho_import, "_status_table")

    def test_shutdown_cleanup(self, tacho_import):
        tacho_import.shutdown()

    def test_wakeup_does_not_crash(self, tacho_import):
        tacho_import.wakeup()
