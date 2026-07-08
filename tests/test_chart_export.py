"""Tests for utils.chart_export — Choreographer-backed SVG/raster export.

All tests mock the ``_RenderEngine`` singleton to avoid launching real Chrome.
"""

from __future__ import annotations

import os
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import utils.chart_export as ce

from utils.chart_export import (
    _RenderEngine,
    configure_choreographer_export,
    shutdown_browser_sync,
)


@pytest.fixture(autouse=True)
def _reset_engine():
    """Replace the real engine singleton with a mock after each test.

    We set a MagicMock rather than ``None`` so that async QThreadPool
    render workers that outlive the test boundary (e.g. from
    PlotlyChartWidget renders submitted during test_analytics_layout)
    never see ``_ENGINE is None`` and attempt to start real Chrome.
    """
    mock = MagicMock(spec=ce._RenderEngine)
    mock.submit.return_value = b"<svg>mock</svg>"
    with ce._ENGINE_LOCK:
        saved = ce._ENGINE
        ce._ENGINE = mock
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
    """Uses mock_engine fixture so configure_choreographer_export does not
    attempt to launch a real Chrome process during env-var tests."""

    def test_sets_browser_path_env(self, mock_engine):
        configure_choreographer_export(chrome_path="/custom/chrome.exe")
        assert os.environ.get("BROWSER_PATH") == "/custom/chrome.exe"

    def test_clears_browser_path_when_none(self, mock_engine):
        os.environ["BROWSER_PATH"] = "/old/path"
        configure_choreographer_export()
        assert "BROWSER_PATH" not in os.environ

    def test_accepts_path_object(self, mock_engine):
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

    def test_start_lock_prevents_double_start(self):
        engine = _RenderEngine()
        thread1 = MagicMock()
        thread1.is_alive.return_value = True
        engine._thread = thread1
        engine.start(block=False)
        assert engine._thread is thread1

    def test_permanent_failure_clear_by_default(self):
        engine = _RenderEngine()
        assert not engine._permanent_failure.is_set()

    def test_zombie_counter_starts_at_zero(self):
        engine = _RenderEngine()
        assert engine._zombie_tab_count == 0

    def test_new_engine_has_no_startup_failures(self):
        engine = _RenderEngine()
        assert engine._startup_failures == 0


class TestCloseTabSafely:
    """Tests for the three-layer tab close mechanism."""

    @pytest.mark.asyncio
    async def test_returns_true_on_successful_close(self):
        tab = MagicMock()
        tab.close = AsyncMock(return_value=None)
        engine = _RenderEngine()
        result = await engine._close_tab_safely(tab)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_both_layers_fail(self):
        import asyncio

        tab = MagicMock()
        tab.close = AsyncMock(side_effect=asyncio.TimeoutError)
        del tab.target_id
        del tab.targetId
        tab.send_command = AsyncMock(side_effect=asyncio.TimeoutError)

        engine = _RenderEngine()
        result = await engine._close_tab_safely(tab)
        assert result is False

    @pytest.mark.asyncio
    async def test_cdp_fallback_succeeds_when_close_fails(self):
        import asyncio

        tab = MagicMock()
        tab.close = AsyncMock(side_effect=asyncio.TimeoutError)
        tab.target_id = "tab-123"
        tab.send_command = AsyncMock(return_value={"result": "ok"})

        engine = _RenderEngine()
        result = await engine._close_tab_safely(tab)
        assert result is True
        tab.send_command.assert_called()


class TestPollSvg:
    """Tests for the SVG polling resilience."""

    def test_breaks_on_non_retryable_error(self):
        import asyncio

        engine = _RenderEngine()
        tab = MagicMock()
        # simulate a connection error (not TimeoutError)
        tab.send_command = MagicMock(side_effect=RuntimeError("websocket closed"))

        with pytest.raises(RuntimeError):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    engine._extract_svg(tab, 100, 100, 1.0, 5.0)
                )
            finally:
                loop.close()
