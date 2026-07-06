"""Tests for utils.chart_export — Choreographer-backed SVG/raster export.

All tests mock the ``_RenderEngine`` singleton to avoid launching real Chrome.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

import utils.chart_export as ce

from utils.chart_export import (
    _RenderEngine,
    configure_choreographer_export,
    shutdown_browser_sync,
)


@pytest.fixture(autouse=True)
def _reset_engine():
    """Replace the real engine singleton with a mock after each test."""
    with ce._ENGINE_LOCK:
        saved = ce._ENGINE
        ce._ENGINE = None
    yield
    with ce._ENGINE_LOCK:
        ce._ENGINE = saved


@pytest.fixture
def mock_engine():
    """Create a mock ``_RenderEngine`` and make it the singleton."""
    engine = MagicMock(spec=_RenderEngine)
    engine.submit.return_value = b"<svg>mock</svg>"
    with ce._ENGINE_LOCK:
        ce._ENGINE = engine
    yield engine


class TestConfigure:
    def test_sets_browser_path_env(self):
        configure_choreographer_export(chrome_path="/custom/chrome.exe")
        assert os.environ.get("BROWSER_PATH") == "/custom/chrome.exe"

    def test_clears_browser_path_when_none(self):
        os.environ["BROWSER_PATH"] = "/old/path"
        configure_choreographer_export()
        assert "BROWSER_PATH" not in os.environ

    def test_accepts_path_object(self):
        from pathlib import Path
        configure_choreographer_export(chrome_path=Path("C:/path/to/chrome.exe"))
        val = os.environ["BROWSER_PATH"]
        assert "chrome.exe" in val


class TestGenerateSvgBytesSync:
    def test_delegates_to_engine(self, mock_engine):
        from plotly import graph_objects as go
        from utils.chart_export import generate_svg_bytes_sync
        fig = go.Figure(go.Bar(y=[1]))
        result = generate_svg_bytes_sync(fig, width=400, height=200)
        assert result == b"<svg>mock</svg>"
        mock_engine.submit.assert_called_once()
        args = mock_engine.submit.call_args[0][0]
        assert args["fmt"] == "svg"
        assert args["width"] == 400
        assert args["height"] == 200


class TestExportFigureSync:
    def test_delegates_to_engine(self, mock_engine):
        from plotly import graph_objects as go
        from utils.chart_export import export_figure_sync
        fig = go.Figure(go.Bar(y=[1]))
        mock_engine.submit.return_value = b"png-data"
        result = export_figure_sync(fig, fmt="png", width=800, height=600)
        assert result == b"png-data"
        mock_engine.submit.assert_called_once()
        args = mock_engine.submit.call_args[0][0]
        assert args["fmt"] == "png"
        assert args["quality"] == 92


class TestShutdownBrowser:
    def test_shutdown_delegates_to_engine(self, mock_engine):
        shutdown_browser_sync()
        mock_engine.shutdown.assert_called_once()

    def test_shutdown_noop_when_no_engine(self):
        shutdown_browser_sync()
        assert True  # no exception


class TestRenderEngine:
    """Integration-adjacent tests that verify engine internals."""

    def test_start_block_waits_for_started(self):
        engine = _RenderEngine()
        with patch.object(engine, "_started") as mock_started:
            mock_started.wait.return_value = True
            engine.start(block=True)
            mock_started.wait.assert_called_once_with(timeout=30)

    def test_raises_if_start_never_completes(self):
        engine = _RenderEngine()
        with patch.object(engine, "_started") as mock_started:
            mock_started.wait.return_value = False
            with pytest.raises(RuntimeError, match="failed to start"):
                engine.submit({"fig": None, "fmt": "svg", "width": 100, "height": 100})
