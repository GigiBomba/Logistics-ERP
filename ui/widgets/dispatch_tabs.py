"""Tab switching container for the Dispatch Board (PySide6).

Replaces ``ui.widgets.dispatch_tabs.DispatchTabs`` (CTkFrame) with a
QWidget-based implementation that uses QPushButton tabs styled via QSS
property selectors.  Appearance is driven by the global theme in
``ui.qt_theme``; no inline stylesheets are used.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import COLOR_ACCENT_PRIMARY, COLOR_BG_ELEVATED, COLOR_BG_OVERLAY, COLOR_BORDER_STRONG

class QtDispatchTabs(QWidget):
    """Horizontal tab bar that switches between stacked panels.

    Mirrors the API of ``DispatchTabs`` (CTk) so views can be migrated by
    changing the import and swapping ``CTkFrame`` panels for ``QWidget``.
    """

    TAB_BG = COLOR_BG_ELEVATED
    TAB_ACTIVE = COLOR_ACCENT_PRIMARY
    TAB_INACTIVE = COLOR_BG_OVERLAY
    TAB_HOVER = COLOR_BORDER_STRONG

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("qtDispatchTabs")

        self._tabs: dict[str, QWidget] = {}
        self._buttons: dict[str, QPushButton] = {}
        self._active_tab: str | None = None
        self._on_switch_callback: Callable[[str], None] | None = None

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- Tab bar -----------------------------------------------------------
        self._tab_bar = QFrame(self)
        self._tab_bar.setProperty("role", "tab-bar")
        self._tab_bar.setFixedHeight(40)

        self._tab_layout = QHBoxLayout(self._tab_bar)
        self._tab_layout.setContentsMargins(0, 0, 0, 0)
        self._tab_layout.setSpacing(0)
        self._tab_layout.setAlignment(Qt.AlignLeft)

        layout.addWidget(self._tab_bar)

        # -- Separator line ----------------------------------------------------
        separator = QFrame(self)
        separator.setProperty("role", "tab-separator")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # -- Stacked panels ----------------------------------------------------
        self._stack = QStackedWidget(self)
        self._stack.setProperty("role", "tab-stack")
        layout.addWidget(self._stack, 1)

    # ── Public API ───────────────────────────────────────────────────────────

    def add_tab(self, tab_id: str, label: str, panel: QWidget) -> None:
        """Register a new tab with the given *tab_id*, *label*, and *panel*.

        The *panel* widget is reparented into the internal stack.
        """
        self._tabs[tab_id] = panel
        self._stack.addWidget(panel)

        btn = QPushButton(label, self._tab_bar)
        btn.setProperty("tabRole", "tab-button")
        btn.setProperty("tabId", tab_id)
        btn.setFixedHeight(40)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        btn.clicked.connect(lambda checked=False, tid=tab_id: self.switch_to(tid))

        self._tab_layout.addWidget(btn)
        self._buttons[tab_id] = btn

        # If this is the first tab, activate it immediately.
        if self._active_tab is None:
            self.switch_to(tab_id)

    def switch_to(self, tab_id: str) -> None:
        """Switch the active tab to *tab_id*.

        Silently returns if *tab_id* is already active or unknown.
        """
        if tab_id == self._active_tab:
            return

        # Deactivate the previously-active tab button.
        if self._active_tab is not None:
            old_btn = self._buttons.get(self._active_tab)
            if old_btn is not None:
                old_btn.setProperty("tabActive", False)
                old_btn.style().unpolish(old_btn)
                old_btn.style().polish(old_btn)

        # Activate the new tab button.
        btn = self._buttons.get(tab_id)
        if btn is not None:
            btn.setProperty("tabActive", True)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # Switch the stacked panel.
        panel = self._tabs.get(tab_id)
        if panel is not None:
            self._stack.setCurrentWidget(panel)

        self._active_tab = tab_id

        if self._on_switch_callback is not None:
            self._on_switch_callback(tab_id)

    def on_switch(self, callback: Callable[[str], None]) -> None:
        """Register *callback* to be invoked on every tab switch.

        The callback receives the new ``tab_id`` as its only argument.
        """
        self._on_switch_callback = callback

    def refresh_translations(self, labels: dict[str, str]) -> None:
        """Update tab button labels from *labels* dict (tab_id -> new text)."""
        for tab_id, new_label in labels.items():
            btn = self._buttons.get(tab_id)
            if btn is not None:
                btn.setText(new_label)

    def set_tab_panel(self, tab_id: str, panel: QWidget) -> None:
        """Replace the panel widget for an already-registered tab.

        Used to swap a lightweight placeholder for a fully-initialized
        panel on first switch (lazy loading).
        """
        old_panel = self._tabs.get(tab_id)
        if old_panel is None or old_panel is panel:
            return

        idx = self._stack.indexOf(old_panel)
        if idx < 0:
            return

        self._stack.removeWidget(old_panel)
        self._stack.insertWidget(idx, panel)
        self._tabs[tab_id] = panel
        old_panel.deleteLater()

        if self._active_tab == tab_id:
            self._stack.setCurrentWidget(panel)

    def get_active_tab(self) -> str | None:
        """Return the ``tab_id`` of the currently active tab, or ``None``."""
        return self._active_tab

    def _destroy(self) -> None:
        """Clear callbacks and internal dicts, then schedule deletion."""
        self._on_switch_callback = None
        self._tabs.clear()
        self._buttons.clear()
        self._active_tab = None
        super().deleteLater()
