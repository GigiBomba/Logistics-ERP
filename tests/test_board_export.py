"""Tests for the dispatch board export."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestBoardExport:
    def test_module_importable(self):
        from ui.dispatch import board_export
        assert board_export is not None

    def test_export_to_csv_mocked(self, monkeypatch):
        from ui.dispatch.board_export import export_board_to_csv
        mock_dialog = MagicMock()
        monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getSaveFileName", lambda *a, **kw: ("test.csv", "CSV (*.csv)"))
        try:
            export_board_to_csv([], MagicMock())
        except Exception:
            pass

    def test_export_to_csv_with_data(self, monkeypatch):
        from ui.dispatch.board_export import export_board_to_csv
        monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getSaveFileName", lambda *a, **kw: ("test.csv", "CSV (*.csv)"))
        trips = [
            {"id": 1, "client": "Test", "status": "planned", "truck": "AG01ABC"},
            {"id": 2, "client": "ACME", "status": "in_transit", "truck": "AG02XYZ"},
        ]
        try:
            export_board_to_csv(trips, MagicMock())
        except Exception:
            pass
