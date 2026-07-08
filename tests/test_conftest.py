"""pytest-qt fixtures for the Operion ERP PySide6 test suite.

These fixtures are registered automatically via ``tests/conftest.py``.
"""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from ui.theme_engine import QtTheme


# Apply the same ghost-window-suppressing Chromium flags that main.py uses
# for QWebEngine's child process.  Must execute before any PySide6 import
# that transitively loads ``QWebEngineWidgets``.
from utils.webengine_flags import apply_webengine_flags
apply_webengine_flags()
# Additional sandbox-disabling for CI/test environments.
os.environ.setdefault("QT_WEBENGINE_DISABLE_SANDBOX", "1")
os.environ["_QT_TEST_WEBENGINE_READY"] = "1"


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
