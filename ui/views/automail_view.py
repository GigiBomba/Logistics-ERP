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
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    COLOR_BG_ELEVATED,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_TERTIARY,
)
from ui.components import PageTitle

logger = logging.getLogger(__name__)

# Lazy panel imports — retry on every call so transient import errors
# (e.g. during scaffold phase) don't permanently kill the panel.
def _import_config_panel():
    try:
        from ui.views.automail.config_panel import ConfigPanel
        return ConfigPanel
    except Exception:
        logger.debug("ConfigPanel not available yet, will retry")
        return None


def _import_timeline_panel():
    try:
        from ui.views.automail.timeline_panel import TimelinePanel
        return TimelinePanel
    except Exception:
        logger.debug("TimelinePanel not available yet, will retry")
        return None


def _import_editor_panel():
    try:
        from ui.views.automail.editor_panel import EditorPanel
        return EditorPanel
    except Exception:
        logger.debug("EditorPanel not available yet, will retry")
        return None


class _PlaceholderPanel(QFrame):
    """Temporary placeholder shown when the actual panel is not yet built."""

    def __init__(self, parent: QWidget, label: str) -> None:
        super().__init__(parent)
        self.setProperty("role", "automail-placeholder")
        self.setStyleSheet(
            f"background: {COLOR_BG_OVERLAY}; "
            f"border: 1px solid {COLOR_BORDER_SUBTLE}; "
            f"border-radius: 8px;"
        )
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        lbl = QLabel(label, self)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 12px;")
        layout.addWidget(lbl)


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
        self._wired = False

    # ── Lifecycle ──────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Refresh data when the view becomes active."""
        self._ensure_wired()

    def shutdown(self) -> None:
        """Release resources when the view is hidden."""

    def _ensure_wired(self) -> None:
        """Build real panels one-by-one, replacing placeholders as each loads."""
        if self._wired:
            return

        config_cls = _import_config_panel()
        timeline_cls = _import_timeline_panel()
        editor_cls = _import_editor_panel()

        if config_cls and self._config_panel is None:
            self._config_panel = config_cls(self._splitter, self.db, self.prefs, self.ops)
            if self._config_placeholder:
                idx = self._splitter.indexOf(self._config_placeholder)
                if idx >= 0:
                    self._splitter.insertWidget(idx, self._config_panel)
                self._config_placeholder.deleteLater()
                self._config_placeholder = None

        if timeline_cls and self._timeline_panel is None:
            self._timeline_panel = timeline_cls(self._splitter, self.db, self.prefs, self.ops)
            if self._timeline_placeholder:
                idx = self._splitter.indexOf(self._timeline_placeholder)
                if idx >= 0:
                    self._splitter.insertWidget(idx, self._timeline_panel)
                self._timeline_placeholder.deleteLater()
                self._timeline_placeholder = None

        if editor_cls and self._editor_panel is None:
            self._editor_panel = editor_cls(self._splitter, self.db, self.prefs, self.ops)
            if self._editor_placeholder:
                idx = self._splitter.indexOf(self._editor_placeholder)
                if idx >= 0:
                    self._splitter.insertWidget(idx, self._editor_panel)
                self._editor_placeholder.deleteLater()
                self._editor_placeholder = None

        if (
            self._config_panel is not None
            and self._timeline_panel is not None
            and self._editor_panel is not None
        ):
            self._splitter.setStretchFactor(0, 1)
            self._splitter.setStretchFactor(1, 2)
            self._splitter.setStretchFactor(2, 2)
            self._wired = True
            logger.info("QtAutoMailView: all 3 panels wired")

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

        # Placeholders until real panels are built
        self._config_placeholder = _PlaceholderPanel(
            self._splitter, t("automail.config_placeholder", "Automation Config\n(will appear here)")
        )
        self._timeline_placeholder = _PlaceholderPanel(
            self._splitter, t("automail.timeline_placeholder", "Reminder Timeline\n(will appear here)")
        )
        self._editor_placeholder = _PlaceholderPanel(
            self._splitter, t("automail.editor_placeholder", "Email Editor\n(will appear here)")
        )

        self._splitter.addWidget(self._config_placeholder)
        self._splitter.addWidget(self._timeline_placeholder)
        self._splitter.addWidget(self._editor_placeholder)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 2)
        self._splitter.setStretchFactor(2, 2)

        outer.addWidget(self._splitter, 1)
