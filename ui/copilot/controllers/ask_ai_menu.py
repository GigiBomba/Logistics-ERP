"""Ask AI context menu — right-click "Ask AI about this" on registered elements.

Blueprint: §34.12 — Contextual "Ask AI About This" right-click menu.

Installs an event filter on the QApplication. When the user right-clicks on
any widget whose objectName is in the Element Registry, a context menu
appears with "Ask AI about this". Selecting it builds a contextual question
and routes it to the Co-Pilot chat panel via the ``ask_ai_requested`` signal.

This is a UX shortcut — it uses the existing ``help.answer_question`` tool
through the normal Co-Pilot utterance pipeline. No new backend capability.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QMenu, QWidget

from services.i18n import t
from ui.copilot.element_registry import resolve_object_name

logger = logging.getLogger(__name__)

# ── Symbolic ID → human-readable label ────────────────────────────────────

_PREFIX_MAP: dict[str, str] = {
    "nav_": "navigation item",
    "btn_": "button",
    "workspace_": "workspace",
    "driver_form_": "driver form field",
    "invoice_": "invoice field",
    "maintenance_": "maintenance field",
    "dispatch_": "dispatch element",
    "overview_": "overview element",
    "fleet_": "fleet element",
}


def _element_label(symbolic_id: str) -> str:
    """Convert a symbolic element ID to a human-readable label."""
    for prefix, noun in _PREFIX_MAP.items():
        if symbolic_id.startswith(prefix):
            remainder = symbolic_id[len(prefix):]
            return f"{remainder.replace('_', ' ').title()} {noun}"
    return symbolic_id.replace("_", " ").title()


def _build_question(symbolic_id: str, active_screen: str | None) -> str:
    """Build a natural language question for the help system.

    The question is phrased to match the planner's ``help.answer_question``
    intent keywords (e.g. "what does", "what is").
    """
    label = _element_label(symbolic_id)
    if active_screen:
        screen_label = active_screen.replace("_", " ").title()
        return t(
            "copilot.help.ask_ai_question_screen",
            default=f"What does the {label} do in the {screen_label} section?",
            label=label,
            screen=screen_label,
        )
    return t(
        "copilot.help.ask_ai_question",
        default=f"What does the {label} do?",
        label=label,
    )


class AskAIMenu(QObject):
    """Event filter that shows 'Ask AI about this' on right-click for registered elements.

    Install on the QApplication to catch context-menu events from any widget::

        app = QApplication.instance()
        menu = AskAIMenu(main_window)
        menu.set_active_screen_getter(lambda: main_window._active_module)
        menu.ask_ai_requested.connect(handler)
        app.installEventFilter(menu)

    Signals:
        ask_ai_requested(str, str): Emitted with (question, active_screen)
            when the user selects "Ask AI about this".
    """

    ask_ai_requested = Signal(str, str)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._active_screen_getter: Optional[Callable[[], str]] = None

    def set_active_screen_getter(self, getter: Callable[[], str]) -> None:
        """Set a callable that returns the current active screen key."""
        self._active_screen_getter = getter

    # ── Event filter ─────────────────────────────────────────────────────

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Intercept context menu events on registered widgets."""
        if event.type() != QEvent.Type.ContextMenu:
            return False

        if not isinstance(obj, QWidget):
            return False

        if not isinstance(event, QContextMenuEvent):
            return False

        # Walk up the parent tree to find a widget with a registered objectName
        target: Optional[QWidget] = obj
        symbolic_id: Optional[str] = None
        while target is not None:
            obj_name = target.objectName()
            if obj_name:
                symbolic_id = resolve_object_name(obj_name)
                if symbolic_id:
                    break
            target = target.parentWidget()

        if symbolic_id is None:
            return False  # Not a registered element — let default handling proceed

        # Build and show the context menu
        menu_text = t("copilot.help.ask_ai_menu", default="Ask AI about this")
        menu = QMenu(obj)
        action = menu.addAction(menu_text)

        result = menu.exec(event.globalPos())
        if result is action:
            active_screen = ""
            if self._active_screen_getter is not None:
                try:
                    active_screen = self._active_screen_getter() or ""
                except Exception:
                    logger.debug("Failed to get active screen", exc_info=True)
                    active_screen = ""

            question = _build_question(symbolic_id, active_screen or None)
            logger.info(
                "Ask AI: element=%s screen=%s question=%s",
                symbolic_id,
                active_screen,
                question,
            )
            self.ask_ai_requested.emit(question, active_screen)
            return True  # Event handled

        return False