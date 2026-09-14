"""Fill-only-if-empty widget helpers.

Shared by the receipt editor (``editor_form``) and the generators view
(``generators_view``) so the trip → form autofill rule lives in one place:
existing user input is never clobbered.

A value is considered *absent* only when it is ``None`` or the empty string.
``0`` (and ``False``) are real values and are written through.
"""
from __future__ import annotations

from typing import Any


def widget_is_empty(widget: Any) -> bool:
    """Return ``True`` when a combo or line edit currently has no value."""
    if widget is None:
        return False
    if hasattr(widget, "currentText"):
        return not widget.currentText().strip()
    if hasattr(widget, "text"):
        return not widget.text().strip()
    return False


def fill_entry_if_empty(entry: Any, value: Any) -> bool:
    """Set a line edit's text only when it is currently empty.

    Returns ``True`` when the value was written.  ``None``/``""`` are treated
    as absent; ``0`` is a real value.
    """
    if entry is None or value is None or value == "":
        return False
    if not widget_is_empty(entry) or not hasattr(entry, "setText"):
        return False
    try:
        entry.setText(str(value))
    except Exception:
        return False
    return True


def fill_combo_if_empty(combo: Any, value: Any) -> bool:
    """Select ``value`` in a combo only when it is currently empty.

    Returns ``True`` when the combo selection changed.  Values not present in
    the combo are skipped, never inserted.  ``None``/``""`` are treated as
    absent; ``0`` is a real value.
    """
    if combo is None or value is None or value == "":
        return False
    if not widget_is_empty(combo):
        return False
    if not (hasattr(combo, "findText") and hasattr(combo, "setCurrentIndex")):
        return False
    try:
        idx = combo.findText(str(value))
    except Exception:
        return False
    if idx < 0:
        return False
    combo.setCurrentIndex(idx)
    return True
