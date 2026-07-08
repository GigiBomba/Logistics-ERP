"""Tests for the automail view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtAutomailView:
    def test_creation(self, qt_widget, qtbot, monkeypatch):
        monkeypatch.setattr(
            "ui.views.automail_view.QtAutomailView._initial_load",
            lambda self: None,
        )
        db = MagicMock()
        prefs = MagicMock()
        api_client = MagicMock()
        view = __import__("ui.views.automail_view", fromlist=["QtAutomailView"]).QtAutomailView(
            qt_widget, db=db, prefs=prefs, api_client=api_client,
        )
        qtbot.addWidget(view)
        with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
            view.shutdown()

    def test_has_config_panel(self, qt_widget, qtbot, monkeypatch):
        monkeypatch.setattr(
            "ui.views.automail_view.QtAutomailView._initial_load",
            lambda self: None,
        )
        view = __import__("ui.views.automail_view", fromlist=["QtAutomailView"]).QtAutomailView(
            qt_widget, db=MagicMock(), prefs=MagicMock(), api_client=MagicMock(),
        )
        qtbot.addWidget(view)

    def test_wakeup_does_not_crash(self, qt_widget, qtbot, monkeypatch):
        monkeypatch.setattr(
            "ui.views.automail_view.QtAutomailView._initial_load",
            lambda self: None,
        )
        view = __import__("ui.views.automail_view", fromlist=["QtAutomailView"]).QtAutomailView(
            qt_widget, db=MagicMock(), prefs=MagicMock(), api_client=MagicMock(),
        )
        qtbot.addWidget(view)
        view.wakeup()
