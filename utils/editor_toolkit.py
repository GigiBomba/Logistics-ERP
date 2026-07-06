"""Shared utilities for editor views (Receipt, Invoice, CMR, Proforma).

Provides reusable helpers for keyboard shortcuts, field validation,
JSON export, and debounced callbacks — reducing code duplication
across the four generator editors.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Sequence

from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

logger = logging.getLogger(__name__)


# ── Debounced Task ──────────────────────────────────────────────────────


class DebouncedTask:
    """Wraps a callback in a single-shot QTimer for debounced execution.

    Usage::

        self._refresh_task = DebouncedTask(self._refresh_preview)
        ...
        self._refresh_task.schedule()   # resets the 300 ms timer

    Supports ``cancel()`` to abort a pending execution.
    """

    def __init__(self, callback: Callable[[], Any], interval_ms: int = 300):
        self._callback = callback
        self._interval = interval_ms
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._callback)

    def schedule(self) -> None:
        """Start (or restart) the debounce timer."""
        self._timer.start(self._interval)

    def cancel(self) -> None:
        """Cancel a pending execution, if any."""
        self._timer.stop()

    @property
    def is_active(self) -> bool:
        return self._timer.isActive()


# ── Keyboard Shortcuts ─────────────────────────────────────────────────


SHORTCUT_KEYS: dict[str, str] = {
    "generate": "Ctrl+G",
    "save_draft": "Ctrl+Shift+S",
    "load_draft": "Ctrl+O",
    "duplicate": "Ctrl+D",
    "export_json": "Ctrl+E",
    "print": "Ctrl+Shift+P",
}


def register_shortcuts(
    parent: QWidget,
    actions: dict[str, Callable[[], Any]],
) -> list[QShortcut]:
    """Create ``QShortcut`` bindings for *parent* from an *actions* dict.

    Allowed keys (with their default key sequences):

    * ``"generate"`` → ``Ctrl+G``
    * ``"save_draft"`` → ``Ctrl+Shift+S``
    * ``"load_draft"`` → ``Ctrl+O``
    * ``"duplicate"`` → ``Ctrl+D``
    * ``"export_json"`` → ``Ctrl+E``
    * ``"print"`` → ``Ctrl+Shift+P``

    Returns the created ``QShortcut`` list so callers can keep a reference
    for cleanup if needed.
    """
    shortcuts: list[QShortcut] = []
    for action_key, callback in actions.items():
        key_seq = SHORTCUT_KEYS.get(action_key)
        if key_seq is None:
            logger.warning("register_shortcuts: unknown action key %r", action_key)
            continue
        sc = QShortcut(QKeySequence(key_seq), parent, callback)
        shortcuts.append(sc)
    return shortcuts


# ── Inline Field Validation ────────────────────────────────────────────


def highlight_invalid_fields(widgets: Sequence[QWidget]) -> None:
    """Remove the ``"invalid"`` property from every widget in *widgets*.

    Call this *before* running validation checks to reset highlights
    from a previous pass.
    """
    for w in widgets:
        w.setProperty("invalid", "false")
        w.style().unpolish(w)
        w.style().polish(w)


def mark_field_invalid(widget: QWidget) -> None:
    """Set the ``"invalid"`` property on *widget* so the QSS selector
    ``[invalid=\"true\"]`` can style it (e.g. red border).
    """
    widget.setProperty("invalid", "true")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def validate_and_highlight(
    widgets: Sequence[QWidget],
    invalid_widgets: list[QWidget],
) -> None:
    """Convenience: clear highlights, then apply to *invalid_widgets*."""
    highlight_invalid_fields(widgets)
    for w in invalid_widgets:
        mark_field_invalid(w)


# ── JSON Export ────────────────────────────────────────────────────────


def export_editor_data(
    parent: QWidget,
    data: dict[str, Any],
    dialog_title: str,
    default_filename: str,
) -> None:
    """Open a save-file dialog and write *data* as pretty-printed JSON.

    Shows a success ``QMessageBox`` on completion or an error dialog
    if the write fails.
    """
    path, _ = QFileDialog.getSaveFileName(
        parent,
        dialog_title,
        default_filename,
        "JSON (*.json)",
    )
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        QMessageBox.information(
            parent,
            dialog_title,
            f"Data exported to:\n{path}",
        )
    except Exception as exc:
        logger.exception("JSON export failed")
        QMessageBox.critical(
            parent,
            dialog_title,
            f"Export failed:\n{exc}",
        )
