"""Tests for QtAutoMailView — three-panel automation center."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QWidget

from ui.views.automail.config_panel import ConfigPanel
from ui.views.automail.timeline_panel import TimelinePanel
from ui.views.automail.editor_panel import EditorPanel
from ui.views.automail_view import QtAutoMailView


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def automail_view(qt_widget, qtbot):
    """Create QtAutoMailView with real panels wired directly."""
    view = QtAutoMailView(
        parent=qt_widget,
        db=MagicMock(),
        prefs=MagicMock(),
        ops=MagicMock(),
        api_client=MagicMock(),
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


# =========================================================================
# Tests
# =========================================================================


class TestQtAutoMailViewInit:
    """Construction and basic attributes."""

    def test_creation(self, automail_view):
        assert automail_view is not None
        assert automail_view.db is not None
        assert automail_view.prefs is not None
        assert automail_view.ops is not None
        assert automail_view._api_client is not None

    def test_panels_are_real_widgets(self, automail_view):
        """Real panels are constructed immediately in _build_ui."""
        assert isinstance(automail_view._config_panel, ConfigPanel)
        assert isinstance(automail_view._timeline_panel, TimelinePanel)
        assert isinstance(automail_view._editor_panel, EditorPanel)


class TestQtAutoMailViewUiElements:
    """Verify UI structure."""

    def test_splitter_exists(self, automail_view):
        assert hasattr(automail_view, "_splitter")
        assert isinstance(automail_view._splitter, QSplitter)

    def test_splitter_has_three_real_panels(self, automail_view):
        assert automail_view._splitter.count() == 3
        widgets = [
            automail_view._splitter.widget(i)
            for i in range(automail_view._splitter.count())
        ]
        assert any(isinstance(w, ConfigPanel) for w in widgets)
        assert any(isinstance(w, TimelinePanel) for w in widgets)
        assert any(isinstance(w, EditorPanel) for w in widgets)

    def test_splitter_orientation(self, automail_view):
        assert automail_view._splitter.orientation() == Qt.Horizontal

    def test_splitter_handle_width(self, automail_view):
        assert automail_view._splitter.handleWidth() == 4


class TestQtAutoMailViewLifecycle:
    """Lifecycle methods."""

    def test_wakeup_does_not_crash(self, automail_view):
        automail_view.wakeup()

    def test_shutdown_does_not_crash(self, automail_view):
        automail_view.shutdown()

    def test_wakeup_reentrant(self, automail_view):
        """Multiple wakeup calls are safe."""
        automail_view.wakeup()
        automail_view.wakeup()
        automail_view.wakeup()

    def test_shutdown_stops_timers(self, automail_view):
        """shutdown stops panel-owned QTimers."""
        # Timers may not be running, but stop() must not raise.
        automail_view.shutdown()
        assert automail_view._timeline_panel._search_timer.isActive() is False
        assert automail_view._editor_panel._preview_timer.isActive() is False


class TestQtAutoMailViewDirectWiring:
    """Integration: real panels are wired directly without lazy swap."""

    def test_construct_without_wakeup(self, qt_widget, qtbot):
        """View constructs with real panels immediately; wakeup is optional."""
        view = QtAutoMailView(
            parent=qt_widget,
            db=MagicMock(),
            prefs=MagicMock(),
            ops=MagicMock(),
            api_client=MagicMock(),
        )
        qtbot.addWidget(view)

        assert isinstance(view._config_panel, ConfigPanel)
        assert isinstance(view._timeline_panel, TimelinePanel)
        assert isinstance(view._editor_panel, EditorPanel)

        # All three must already be in the splitter
        assert view._splitter.count() == 3
        widgets = [view._splitter.widget(i) for i in range(view._splitter.count())]
        assert view._config_panel in widgets
        assert view._timeline_panel in widgets
        assert view._editor_panel in widgets

        view.shutdown()
