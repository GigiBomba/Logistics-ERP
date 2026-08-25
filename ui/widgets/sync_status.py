"""Sync status indicator widget (Phase 4b).

A small clickable label showing the offline-first sync state in the top bar.
Clicking it opens the sync conflict journal (wired by ``MainWindow``).

Statuses (from ``SyncEngine.sync_status_changed`` / ``sync_finished``):

* ``"offline"``   → "Sync: offline"
* ``"syncing"``   → "Sync: syncing…"
* ``"idle"``      → "Sync: up to date"
* ``"conflicts"`` → "Sync: N conflicts"
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel

from services.i18n import t
from ui.design_tokens import (
    COLOR_INFO_TEXT,
    DANGER_TEXT,
    FONT_SIZE_SM,
    SUCCESS_TEXT,
    TEXT_MUTED,
)


def sync_status_text(status: str, conflicts: int = 0) -> str:
    """Human-readable label for a sync status (pure helper, testable)."""
    if status == "syncing":
        return "Sync: syncing…"
    if status == "offline":
        return "Sync: offline"
    if status == "conflicts":
        return f"Sync: {conflicts} conflicts"
    if status == "error":
        return "Sync: error"
    return "Sync: up to date"


def sync_status_color(status: str) -> str:
    """Accent color for a sync status (pure helper, testable)."""
    if status == "syncing":
        return COLOR_INFO_TEXT
    if status == "offline":
        return TEXT_MUTED
    if status == "conflicts":
        return DANGER_TEXT
    if status == "error":
        return DANGER_TEXT
    return SUCCESS_TEXT


def resolve_status(status: str, conflicts: int = 0) -> str:
    """Resolve a raw sync status + conflict count to a display status.

    Conflicts take priority over ``"idle"`` so the label keeps showing the
    pending conflict count even after a cycle that ended idle.  A failed
    cycle (``"error"``) takes priority over conflicts — an error is more
    severe and must not be masked by a stale conflict count.
    """
    if status == "offline":
        return "offline"
    if status == "error":
        return "error"
    if conflicts > 0:
        return "conflicts"
    return status


class SyncStatusLabel(QLabel):
    """Clickable sync-state label matching the top bar's muted-label style."""

    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._conflict_count = 0
        self.setAccessibleName("Sync status")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(
            t("sync.status_tooltip", default="Sync status — click to view conflicts")
        )
        self.update_status("idle")

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)

    def update_status(self, status: str, conflicts: int | None = None) -> None:
        """Refresh the label from a sync status (and optional conflict count)."""
        if conflicts is not None:
            self._conflict_count = conflicts
        self.setText(sync_status_text(status, self._conflict_count))
        self.setStyleSheet(
            f"color: {sync_status_color(status)}; "
            f"font-size: {FONT_SIZE_SM}px; background: transparent;"
        )