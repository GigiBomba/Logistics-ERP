"""Shared layout utility functions."""
from PySide6.QtWidgets import QLayout

def clear_layout(layout: QLayout) -> None:
    """Remove all widgets from layout and schedule deletion."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
