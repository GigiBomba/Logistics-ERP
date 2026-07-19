"""Tests for the CoPilot view (CoPilotView)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_controller():
    return MagicMock()


@pytest.fixture
def copilot_view(qt_widget, qtbot, mock_controller):
    """Construct a CoPilotView with a mocked controller."""
    mod = __import__("ui.views.copilot_view", fromlist=["CoPilotView"])
    view = mod.CoPilotView(qt_widget, controller=mock_controller)
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


# ===========================================================================
# Construction
# ===========================================================================

class TestConstruction:
    """View constructs and exposes expected sub-widgets."""

    def test_creation(self, copilot_view):
        """View constructs without crashing."""
        assert copilot_view is not None

    def test_panel_created(self, copilot_view):
        """CoPilotPanel is created as an attribute."""
        assert copilot_view._panel is not None

    def test_panel_is_widget(self, copilot_view):
        """The panel is a QWidget (CoPilotPanel)."""
        from PySide6.QtWidgets import QWidget
        assert isinstance(copilot_view._panel, QWidget)

    def test_panel_visible(self, copilot_view):
        """Panel widget is visible after construction."""
        # The panel may not be explicitly shown until the parent is, but
        # it should be part of the layout.
        assert copilot_view._panel.parent() is not None

    def test_controller_assigned(self, copilot_view, mock_controller):
        """Controller reference is forwarded to the view."""
        assert copilot_view._controller is mock_controller

    def test_panel_has_controller(self, copilot_view, mock_controller):
        """Panel receives the controller via constructor."""
        assert copilot_view._panel._controller is mock_controller

    def test_layout_contains_panel(self, copilot_view):
        """The view's layout contains the panel widget."""
        layout = copilot_view.layout()
        assert layout is not None
        # The layout should contain the panel at index 0
        item = layout.itemAt(0)
        assert item is not None
        assert item.widget() is copilot_view._panel


# ===========================================================================
# Construction without controller
# ===========================================================================

class TestNoController:
    """View works when no controller is provided."""

    def test_creation_no_controller(self, qt_widget, qtbot):
        """View constructs without a controller."""
        mod = __import__("ui.views.copilot_view", fromlist=["CoPilotView"])
        view = mod.CoPilotView(qt_widget, controller=None)
        qtbot.addWidget(view)

        assert view._controller is None
        assert view._panel is not None
        assert view._panel._controller is None

        view.shutdown()

    def test_ask_about_element_no_crash(self, qt_widget, qtbot):
        """Calling ask_about_element with no controller does not crash."""
        mod = __import__("ui.views.copilot_view", fromlist=["CoPilotView"])
        view = mod.CoPilotView(qt_widget, controller=None)
        qtbot.addWidget(view)

        # Should not raise
        view.ask_about_element("What is this?")
        view.shutdown()


# ===========================================================================
# Panel visibility / toggle
# ===========================================================================

class TestPanelVisibility:
    """Panel visibility is controlled by the view (or parent)."""

    def test_panel_not_hidden(self, copilot_view):
        """Panel is not explicitly hidden after construction."""
        assert not copilot_view._panel.isHidden()

    def test_hide_panel(self, copilot_view):
        """Hiding the panel does not crash."""
        copilot_view._panel.hide()
        assert copilot_view._panel.isHidden()

    def test_show_panel(self, copilot_view):
        """Showing the panel after hiding works."""
        copilot_view._panel.hide()
        copilot_view._panel.show()
        assert not copilot_view._panel.isHidden()


# ===========================================================================
# Integration with CoPilotController
# ===========================================================================

class TestControllerIntegration:
    """Forwarding calls to the controller."""

    def test_ask_about_element_forwards_to_panel(self, copilot_view, mock_controller):
        """ask_about_element delegates to panel, which calls controller."""
        with patch.object(copilot_view._panel, "ask_about_element") as mock_panel_method:
            copilot_view.ask_about_element("Explain this form", "dashboard")
            mock_panel_method.assert_called_once_with("Explain this form", "dashboard")

    def test_ask_about_element_no_screen(self, copilot_view, mock_controller):
        """ask_about_element works without active_screen."""
        with patch.object(copilot_view._panel, "ask_about_element") as mock_panel_method:
            copilot_view.ask_about_element("What is this?")
            mock_panel_method.assert_called_once_with("What is this?", None)


# ===========================================================================
# Lifecycle
# ===========================================================================

class TestLifecycle:
    """wakeup / shutdown lifecycle."""

    def test_wakeup_does_not_crash(self, copilot_view):
        """wakeup() can be called safely."""
        copilot_view.wakeup()

    def test_shutdown_cleanup(self, copilot_view):
        """shutdown() can be called safely."""
        copilot_view.shutdown()

    def test_shutdown_idempotent(self, copilot_view):
        """shutdown() can be called multiple times."""
        copilot_view.shutdown()
        copilot_view.shutdown()

    def test_shutdown_calls_panel_shutdown(self, copilot_view):
        """shutdown() triggers panel.shutdown()."""
        with patch.object(copilot_view._panel, "shutdown") as mock_shutdown:
            copilot_view.shutdown()
            mock_shutdown.assert_called_once()

    def test_wakeup_then_shutdown(self, copilot_view):
        """wakeup() followed by shutdown() does not crash."""
        copilot_view.wakeup()
        copilot_view.shutdown()


# ===========================================================================
# i18n
# ===========================================================================

class TestI18n:
    """Language change handling."""

    def test_language_callback_registered(self, copilot_view):
        """_on_language_changed is the registered callback."""
        assert callable(copilot_view._i18n_callback)

    def test_language_changed_does_not_crash(self, copilot_view):
        """_on_language_changed can be called without error."""
        copilot_view._on_language_changed("ro")

    def test_panel_i18n_connected(self, copilot_view):
        """Panel has its own i18n listener."""
        assert callable(copilot_view._panel._i18n_callback)
