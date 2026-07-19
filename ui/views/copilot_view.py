"""CoPilotView — view wrapper for the AI Co-Pilot chat panel.

Following the existing view pattern with wakeup()/shutdown() lifecycle hooks
and i18n listener registration.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from services.i18n import register_listener, t, unregister_listener
from ui.copilot.controllers.copilot_controller import CoPilotController
from ui.copilot.widgets.copilot_panel import CoPilotPanel

logger = logging.getLogger(__name__)


class CoPilotView(QWidget):
    """View wrapper for the AI Co-Pilot chat panel.

    Lifecycle:
        wakeup()  — called when the view becomes active
        shutdown() — called when the view is deactivated
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        controller: Optional[CoPilotController] = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._i18n_callback = self._on_language_changed
        self._panel: CoPilotPanel | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._panel = CoPilotPanel(self, controller=self._controller)
        layout.addWidget(self._panel)

    def ask_about_element(self, question: str, active_screen: str | None = None) -> None:
        """Forward an 'Ask AI' question to the Co-Pilot panel (§34.12)."""
        if self._panel is not None:
            self._panel.ask_about_element(question, active_screen)

    def wakeup(self) -> None:
        """Called when the view becomes active."""
        register_listener(self._i18n_callback)
        logger.debug("CoPilotView wakeup")

    def shutdown(self) -> None:
        """Called when the view is deactivated."""
        try:
            unregister_listener(self._i18n_callback)
        except Exception:
            pass
        if self._panel is not None:
            self._panel.shutdown()
        logger.debug("CoPilotView shutdown")

    def _on_language_changed(self, lang: str) -> None:
        """Refresh labels when the language changes."""
        # The panel handles its own i18n refresh
        pass
