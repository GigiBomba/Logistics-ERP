"""Global QSS stylesheet builder for the Operion ERP PySide6 frontend.

Thin wrapper around ``ui.theme_engine.QtTheme.qss()``. The app-specific widget
styles (stat cards, kanban board, filters, section headers, tab buttons, cards)
now live inside ``QtTheme`` as private ``_*_qss()`` methods, so ``QtTheme.qss()``
returns the *complete* global sheet. ``build_stylesheet()`` is kept as the stable
entry point used by ``main.py`` / ``main_remote.py``.

Usage::

    from ui.stylesheet import build_stylesheet
    app.setStyleSheet(build_stylesheet())
"""

from __future__ import annotations

from ui.theme_engine import QtTheme


def build_stylesheet() -> str:
    """Return the complete global stylesheet for the application."""
    return QtTheme.qss()