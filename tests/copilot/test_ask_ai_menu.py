"""Tests for AskAIMenu — right-click "Ask AI about this" context menu.

Blueprint: §34.12 — Contextual "Ask AI About This" right-click menu.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEvent, QObject, QPoint
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QWidget

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def ask_menu(qapp):
    """Create an AskAIMenu instance with a stable parent object.

    The parent is kept alive via the generator fixture so the C++ object
    is not prematurely destroyed (which would delete the AskAIMenu too).
    """
    from ui.copilot.controllers.ask_ai_menu import AskAIMenu

    parent = QObject()
    yield AskAIMenu(parent)


@pytest.fixture
def registered_widget(qt_widget):
    """QWidget with objectName matching a registered entry in the element registry.

    ``sidebar-item-overview`` reverse-resolves to the symbolic ID ``nav_overview``.
    """
    qt_widget.setObjectName("sidebar-item-overview")
    return qt_widget


# ── Mock helpers ─────────────────────────────────────────────────────────────


def _make_context_menu_event() -> QContextMenuEvent:
    """Build a minimal QContextMenuEvent for testing (Qt 6.11 compatible)."""
    return QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse, QPoint(0, 0), QPoint(0, 0),
    )


def _patch_qmenu(exec_result: object = None):
    """Return a (patcher, mock_action) tuple.

    Patches ``ui.copilot.controllers.ask_ai_menu.QMenu`` (the module-level
    reference) so that instantiating ``QMenu`` returns a fully mocked menu.

    When *exec_result* is the same object as the mock action the code path
    where the user selects the menu item is exercised.  When it is ``None``
    the "user closed the menu" path is exercised.
    """
    mock_menu = MagicMock()
    mock_action = MagicMock()
    mock_menu.addAction.return_value = mock_action
    mock_menu.exec.return_value = exec_result if exec_result is not None else mock_action
    return patch("ui.copilot.controllers.ask_ai_menu.QMenu", return_value=mock_menu), mock_action


# ── Tests: EventFilter ──────────────────────────────────────────────────────


class TestAskAIMenuEventFilter:
    """Right-click interception behaviour."""

    def test_non_contextmenu_event_ignored(self, ask_menu, qt_widget):
        """eventFilter with a non-ContextMenu event type returns False."""
        event = QEvent(QEvent.Type.MouseButtonPress)
        assert ask_menu.eventFilter(qt_widget, event) is False

    def test_non_widget_object_ignored(self, ask_menu):
        """eventFilter with a non-QWidget watched object returns False."""
        obj = QObject()
        event = _make_context_menu_event()
        assert ask_menu.eventFilter(obj, event) is False

    def test_unregistered_widget_no_menu(self, ask_menu, qt_widget):
        """Widget whose objectName is NOT in the registry returns False."""
        qt_widget.setObjectName("completely-unknown-widget")
        event = _make_context_menu_event()
        patcher, _mock_action = _patch_qmenu()
        with patcher:
            result = ask_menu.eventFilter(qt_widget, event)
            assert result is False

    def test_registered_widget_shows_menu(self, ask_menu, registered_widget):
        """Widget whose objectName IS in the registry returns True (handled)."""
        event = _make_context_menu_event()
        patcher, mock_action = _patch_qmenu()
        with patcher:
            result = ask_menu.eventFilter(registered_widget, event)
        assert result is True

    def test_registered_parent_widget_works(self, ask_menu, qt_widget, qtbot):
        """Child widget has no registered objectName, but its parent does.

        The eventFilter should walk up the parent tree and find the
        registered parent.
        """
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.setObjectName("sidebar-item-overview")

        child = QWidget(parent)
        child.setObjectName("")  # no registered name
        # NOTE: child is deliberately NOT registered with qtbot — it will be
        # destroyed automatically when ``parent`` (registered above) is closed.

        event = _make_context_menu_event()
        patcher, mock_action = _patch_qmenu()
        with patcher:
            with qtbot.waitSignal(ask_menu.ask_ai_requested, timeout=500):
                result = ask_menu.eventFilter(child, event)
        assert result is True


# ── Tests: Signal emission ──────────────────────────────────────────────────


class TestAskAIMenuSignal:
    """Signal emission when the menu item is selected or dismissed."""

    def test_signal_emitted_on_menu_select(self, ask_menu, registered_widget, qtbot):
        """Mock QMenu.exec returns the action → ``ask_ai_requested`` fires."""
        event = _make_context_menu_event()
        patcher, mock_action = _patch_qmenu()
        with patcher:
            with qtbot.waitSignal(ask_menu.ask_ai_requested, timeout=500) as blocker:
                ask_menu.eventFilter(registered_widget, event)

        assert blocker.signal_triggered
        question, active_screen = blocker.args
        assert isinstance(question, str)
        assert isinstance(active_screen, str)

    def test_signal_not_emitted_when_user_closes_menu(
        self, ask_menu, registered_widget,
    ):
        """Mock QMenu.exec returns None → signal NOT emitted."""
        event = _make_context_menu_event()

        # Patch QMenu so that addAction returns a mock, but exec returns None
        mock_menu = MagicMock()
        mock_action = MagicMock()
        mock_menu.addAction.return_value = mock_action
        mock_menu.exec.return_value = None  # user closed the menu
        patcher = patch(
            "ui.copilot.controllers.ask_ai_menu.QMenu", return_value=mock_menu,
        )

        with patcher:
            emitted = []
            ask_menu.ask_ai_requested.connect(lambda *a: emitted.append(a))
            result = ask_menu.eventFilter(registered_widget, event)

        assert result is False
        assert len(emitted) == 0


# ── Tests: Active screen getter ─────────────────────────────────────────────


class TestAskAIMenuActiveScreen:
    """The active-screen callable and its effect on the signal payload."""

    def test_active_screen_getter_called(self, ask_menu, registered_widget, qtbot):
        """Getter return value appears in the signal payload."""
        ask_menu.set_active_screen_getter(lambda: "fleet")
        event = _make_context_menu_event()
        patcher, mock_action = _patch_qmenu()
        with patcher:
            with qtbot.waitSignal(ask_menu.ask_ai_requested, timeout=500) as blocker:
                ask_menu.eventFilter(registered_widget, event)

        _question, active_screen = blocker.args
        assert active_screen == "fleet"

    def test_active_screen_getter_none(self, ask_menu, registered_widget, qtbot):
        """No getter set → active_screen is ``\"\"``."""
        event = _make_context_menu_event()
        patcher, mock_action = _patch_qmenu()
        with patcher:
            with qtbot.waitSignal(ask_menu.ask_ai_requested, timeout=500) as blocker:
                ask_menu.eventFilter(registered_widget, event)

        _question, active_screen = blocker.args
        assert active_screen == ""

    def test_active_screen_getter_raises(self, ask_menu, registered_widget, qtbot):
        """Getter raises → active_screen is ``\"\"``, no crash, signal still emits."""
        ask_menu.set_active_screen_getter(_raise_runtime_error)
        event = _make_context_menu_event()
        patcher, mock_action = _patch_qmenu()
        with patcher:
            with qtbot.waitSignal(ask_menu.ask_ai_requested, timeout=500) as blocker:
                ask_menu.eventFilter(registered_widget, event)

        _question, active_screen = blocker.args
        assert active_screen == ""


def _raise_runtime_error() -> str:
    raise RuntimeError("simulated getter failure")


# ── Tests: Edge cases & helper functions ────────────────────────────────────


class TestAskAIMenuEdgeCases:
    """Edge cases for the element label and question builder helpers."""

    @staticmethod
    def _element_label(symbolic_id: str) -> str:
        """Import and call the private ``_element_label``."""
        from ui.copilot.controllers.ask_ai_menu import _element_label

        return _element_label(symbolic_id)

    @staticmethod
    def _build_question(symbolic_id: str, active_screen: str | None) -> str:
        """Import and call the private ``_build_question``."""
        from ui.copilot.controllers.ask_ai_menu import _build_question

        return _build_question(symbolic_id, active_screen)

    # ── Prefix mapping ─────────────────────────────────────────────────

    def test_element_label_prefix_maps(self):
        """Each registered prefix produces the expected human-readable noun."""
        cases = {
            "nav_overview": "navigation item",
            "btn_add_driver": "button",
            "workspace_fleet": "workspace",
            "driver_form_name": "driver form field",
            "invoice_client_field": "invoice field",
            "maintenance_description_field": "maintenance field",
            "dispatch_trip_card": "dispatch element",
            "overview_metrics": "overview element",
            "fleet_health_panel": "fleet element",
        }
        for symbolic_id, expected_noun in cases.items():
            label = self._element_label(symbolic_id)
            assert expected_noun in label, (
                f"Expected noun {expected_noun!r} in label {label!r} "
                f"for symbolic_id {symbolic_id!r}"
            )

    def test_element_label_fallback(self):
        """Unknown prefix is title-cased with underscores replaced."""
        label = self._element_label("custom_element")
        assert label == "Custom Element"

    # ── _build_question ─────────────────────────────────────────────────

    def test_build_question_with_screen(self):
        """Screen-aware question includes the screen name."""
        result = self._build_question("nav_overview", "fleet")
        assert "Overview" in result
        assert "navigation item" in result
        assert "Fleet" in result

    def test_build_question_without_screen(self):
        """Question without a screen omits the screen section clause."""
        result = self._build_question("nav_overview", None)
        assert "Overview" in result
        assert "navigation item" in result
        assert "section" not in result.lower()
