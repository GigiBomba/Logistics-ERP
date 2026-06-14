"""pytest-qt fixtures for the Operion ERP PySide6 test suite.

These fixtures are registered automatically via ``tests/conftest.py``.
"""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from ui.theme_engine import QtTheme


def _ensure_webengine_software_rendering() -> None:
    """Set environment flags so QWebEngineView uses CPU rendering in headless CI.

    Without these, Chromium crashes with an access violation when no GPU is
    available.  The flags must be set *before* ``QApplication`` is instantiated.
    """
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if "--disable-gpu" not in flags:
        flags += " --disable-gpu"
    if "--no-sandbox" not in flags and os.name == "nt":
        flags += " --no-sandbox"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = flags.strip()
    os.environ.setdefault("QT_WEBENGINE_DISABLE_SANDBOX", "1")

    # Set flag to indicate WebEngine should work with software rendering.
    os.environ["_QT_TEST_WEBENGINE_READY"] = "1"


_ensure_webengine_software_rendering()


@pytest.fixture(scope="session")
def qapp():
    """Return the singleton QApplication with the global theme applied.

    pytest-qt also provides a ``qapp`` fixture, but ours is session-scoped and
    ensures the Operion dark theme is loaded before any widget is created.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    QtTheme.apply(app)
    yield app


@pytest.fixture
def qt_main_window(qapp, qtbot):
    """Provide a bare QMainWindow for widget tests."""
    window = QMainWindow()
    window.setWindowTitle("Operion Test Window")
    window.resize(800, 600)
    qtbot.addWidget(window)
    yield window
    window.close()


@pytest.fixture
def qt_widget(qapp, qtbot):
    """Provide a bare QWidget parent for widget tests."""
    w = QWidget()
    w.resize(400, 300)
    qtbot.addWidget(w)
    yield w
    w.close()


@pytest.fixture
def webengine_available() -> bool:
    """Check whether QWebEngineView can be instantiated in this environment."""
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView
        v = QWebEngineView()
        v.deleteLater()
        return True
    except Exception:
        return False
