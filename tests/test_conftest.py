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


# ── Visual regression testing fixtures ────────────────────────────────────

import os
import platform
import sys
from pathlib import Path

import pytest
import numpy as np
from PIL import Image, ImageChops
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage

_BASELINES_ROOT = Path(__file__).parent / "baselines"
_PIXEL_THRESHOLD = 0.1


def _get_os_name() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows-latest"
    elif system == "darwin":
        return "macos-latest"
    else:
        return "ubuntu-latest"


def _qpixmap_to_pil(pixmap) -> Image.Image:
    qimage = pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
    width = qimage.width()
    height = qimage.height()
    ptr = qimage.constBits()
    assert qimage.bytesPerLine() == qimage.width() * 4, \
        f"Expected bytesPerLine={qimage.width() * 4}, got {qimage.bytesPerLine()}"
    arr = bytes(ptr)
    return Image.frombytes("RGBA", (width, height), arr)


@pytest.fixture
def assert_snapshot(tmp_path, qapp, request):
    """Capture a widget's appearance and compare against a per-OS baseline.

    Usage:
        assert_snapshot(widget, "test_name", delay_ms=50, resize=(400,300))
        assert_snapshot(widget, delay_ms=100)
    """
    update_mode = os.environ.get("OPERION_UPDATE_BASELINES", "") == "1"

    def _assert_snapshot(
        widget,
        test_name=None,
        delay_ms=50,
        resize=None,
    ):
        if test_name is None:
            test_name = request.node.name.replace("test_", "", 1)

        if resize is not None:
            widget.resize(*resize)

        QTest.qWait(delay_ms)

        pixmap = widget.grab()
        image = _qpixmap_to_pil(pixmap)

        os_name = _get_os_name()
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        baseline_path = _BASELINES_ROOT / os_name / py_version / f"{test_name}.png"

        if update_mode:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(baseline_path), "PNG")
            pytest.skip(f"Baseline updated: {baseline_path}")
            return

        baseline_path.parent.mkdir(parents=True, exist_ok=True)

        if not baseline_path.exists():
            # No committed baseline (Qt widget screenshots can't be generated
            # reliably headless on CI).  Skip — never fail the suite.
            current_path = tmp_path / f"{test_name}__current.png"
            image.save(str(current_path), "PNG")
            pytest.skip(
                f"No baseline found for '{test_name}'. Current saved to: {current_path}"
            )

        baseline = Image.open(str(baseline_path))

        if image.size != baseline.size:
            pytest.fail(
                f"Size mismatch for '{test_name}':\n"
                f"  Current:  {image.width}x{image.height}\n"
                f"  Baseline: {baseline.width}x{baseline.height}"
            )

        diff = ImageChops.difference(image.convert("RGB"), baseline.convert("RGB"))
        diff_arr = np.array(diff)
        diff_pixels = int(np.sum(np.any(diff_arr > 0, axis=2)))
        total_pixels = image.width * image.height
        diff_percent = (diff_pixels / total_pixels) * 100

        if diff_percent > _PIXEL_THRESHOLD:
            diff_path = tmp_path / f"{test_name}__diff.png"
            current_path = tmp_path / f"{test_name}__current.png"
            diff.save(str(diff_path))
            image.save(str(current_path))
            pytest.fail(
                f"Visual regression for '{test_name}':\n"
                f"  {diff_percent:.3f}% pixels differ (threshold: {_PIXEL_THRESHOLD}%)\n"
                f"  Diff: {diff_path}\n"
                f"  Current: {current_path}"
            )

    return _assert_snapshot
