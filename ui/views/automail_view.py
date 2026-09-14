"""AutoMail tab — three-panel automation center for payment reminders.

Layout (20:45:35):
    - Left:   ConfigPanel   — master toggle, schedule editor, delivery rules
    - Center: TimelinePanel — invoice timeline, search, manual controls
    - Right:  EditorPanel   — HTML email editor, variable picker, preview

Referenced from :class:`ui.views.document_center_view.QtDocumentCenterView`
as the fourth tab (index 3).
"""

from __future__ import annotations

import contextlib
import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from ui.design_tokens import COLOR_BORDER_SUBTLE
from ui.views.automail.config_panel import ConfigPanel
from ui.views.automail.timeline_panel import TimelinePanel
from ui.views.automail.editor_panel import EditorPanel

logger = logging.getLogger(__name__)


class QtAutoMailView(QWidget):
    """Top-level AutoMail tab with three-panel layout."""

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs=None,
        ops=None,
        api_client=None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self.ops = ops
        self._api_client = api_client

        self._config_panel: Optional[QWidget] = None
        self._timeline_panel: Optional[QWidget] = None
        self._editor_panel: Optional[QWidget] = None

        self._build_ui()

    # ── Lifecycle ──────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Refresh data when the view becomes active."""
        if self._config_panel is not None and hasattr(self._config_panel, "wakeup"):
            self._config_panel.wakeup()
        if self._timeline_panel is not None and hasattr(self._timeline_panel, "wakeup"):
            self._timeline_panel.wakeup()
        if self._editor_panel is not None and hasattr(self._editor_panel, "wakeup"):
            self._editor_panel.wakeup()

    def shutdown(self) -> None:
        """Release resources when the view is hidden."""
        # Panels do not expose dedicated shutdown methods;
        # stop any owned QTimers to prevent callbacks after teardown.
        if self._timeline_panel is not None:
            with contextlib.suppress(Exception):
                self._timeline_panel._search_timer.stop()
        if self._editor_panel is not None:
            with contextlib.suppress(Exception):
                self._editor_panel._preview_timer.stop()

    # ── UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._splitter = QSplitter(Qt.Horizontal, self)
        self._splitter.setHandleWidth(4)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {COLOR_BORDER_SUBTLE}; }}"
        )

        self._config_panel = ConfigPanel(self._splitter, self.db, self.prefs, self.ops)
        self._timeline_panel = TimelinePanel(self._splitter, self.db, self.prefs, self.ops)
        self._editor_panel = EditorPanel(self._splitter, self.db, self.prefs, self.ops)

        self._splitter.addWidget(self._config_panel)
        self._splitter.addWidget(self._timeline_panel)
        self._splitter.addWidget(self._editor_panel)
        self._splitter.setStretchFactor(0, 4)   # Config  20%
        self._splitter.setStretchFactor(1, 11)  # Timeline 55%
        self._splitter.setStretchFactor(2, 5)   # Editor  25%

        outer.addWidget(self._splitter, 1)
