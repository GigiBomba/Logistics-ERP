"""Tests for utils.chart_export — Choreographer-backed SVG/raster export.

All tests mock the ``_RenderEngine`` singleton to avoid launching real Chrome.
"""

from __future__ import annotations

import asyncio
import os
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_engine():
    """Replace the real engine singleton with a mock after each test.

    We set a MagicMock rather than ``None`` so that async QThreadPool
    render workers that outlive the test boundary (e.g. from
    PlotlyChartWidget renders submitted during test_analytics_layout)
    never see ``_ENGINE is None`` and attempt to start real Chrome.
    """
    import utils.chart_export as ce

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
    import utils.chart_export as ce
    from utils.chart_export import _RenderEngine

    engine = MagicMock(spec=_RenderEngine)
    engine.submit.return_value = b"<svg>mock</svg>"
    with ce._ENGINE_LOCK:
        ce._ENGINE = engine
    yield engine


class TestConfigure:
    """Uses mock_engine fixture so configure_choreographer_export does not
    attempt to launch a real Chrome process during env-var tests."""

    def test_sets_browser_path_env(self, mock_engine):
        from utils.chart_export import configure_choreographer_export

        configure_choreographer_export(chrome_path="/custom/chrome.exe")
        assert os.environ.get("BROWSER_PATH") == "/custom/chrome.exe"

    def test_clears_browser_path_when_none(self, mock_engine):
        from utils.chart_export import configure_choreographer_export

        os.environ["BROWSER_PATH"] = "/old/path"
        configure_choreographer_export()
        assert "BROWSER_PATH" not in os.environ

    def test_accepts_path_object(self, mock_engine):
        from pathlib import Path
        from utils.chart_export import configure_choreographer_export

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
        from utils.chart_export import shutdown_browser_sync

        shutdown_browser_sync()
        mock_engine.shutdown.assert_called_once()

    def test_shutdown_noop_when_no_engine(self):
        from utils.chart_export import shutdown_browser_sync

        shutdown_browser_sync()
        assert True  # no exception


class TestRenderEngine:
    """Integration-adjacent tests that verify engine internals."""

    def test_start_block_waits_for_started(self):
        from utils.chart_export import _RenderEngine

        engine = _RenderEngine()
        with patch.object(engine, "_started") as mock_started:
            mock_started.wait.return_value = True
            engine.start(block=True)
            mock_started.wait.assert_called_once_with(timeout=30)

    def test_raises_if_start_never_completes(self):
        from utils.chart_export import _RenderEngine

        engine = _RenderEngine()
        with patch.object(engine, "_started") as mock_started:
            mock_started.wait.return_value = False
            with pytest.raises(RuntimeError, match="failed to start"):
                engine.submit({"fig": None, "fmt": "svg", "width": 100, "height": 100})

    def test_start_lock_prevents_double_start(self):
        from utils.chart_export import _RenderEngine

        engine = _RenderEngine()
        thread1 = MagicMock()
        thread1.is_alive.return_value = True
        engine._thread = thread1
        engine.start(block=False)
        assert engine._thread is thread1

    def test_permanent_failure_clear_by_default(self):
        from utils.chart_export import _RenderEngine

        engine = _RenderEngine()
        assert not engine._permanent_failure.is_set()

    def test_zombie_counter_starts_at_zero(self):
        from utils.chart_export import _RenderEngine

        engine = _RenderEngine()
        assert engine._zombie_tab_count == 0

    def test_new_engine_has_no_startup_failures(self):
        from utils.chart_export import _RenderEngine

        engine = _RenderEngine()
        assert engine._startup_failures == 0


class TestCloseTabSafely:
    """Tests for the three-layer tab close mechanism."""

    @pytest.mark.asyncio
    async def test_returns_true_on_successful_close(self):
        from utils.chart_export import _RenderEngine

        tab = MagicMock()
        tab.close = AsyncMock(return_value=None)
        engine = _RenderEngine()
        result = await engine._close_tab_safely(tab)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_both_layers_fail(self):
        import asyncio
        from utils.chart_export import _RenderEngine

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
        from utils.chart_export import _RenderEngine

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
        from utils.chart_export import _RenderEngine

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


class TestRenderTimeoutRetry:
    """Exercise the real engine worker loop (no real Chrome) to verify the
    timeout → recycle → single-retry logic added for GPU-less environments.

    Chrome is avoided entirely by monkeypatching the engine instance:
    ``_ensure_browser`` plants a fake browser, ``_recycle_browser`` is a
    counting no-op, and ``_process`` is a controllable stand-in.
    """

    @pytest.fixture(autouse=True)
    def _reset_fallback(self):
        """``_SOFTWARE_RENDER_FALLBACK`` is sticky for the process lifetime
        in production; reset it around every test (setup AND teardown) so
        the flag flipped by the retry tests never leaks into other tests
        (e.g. tests/test_silent_chromium.py asserting the GPU-killing CLI
        flags are present)."""
        import utils.chart_export as ce

        ce._reset_software_render_fallback()
        yield
        ce._reset_software_render_fallback()

    @staticmethod
    def _make_fake_browser():
        """Minimal browser stand-in that answers the CDP health ping and
        closes cleanly."""
        browser = MagicMock()
        browser.send_command = AsyncMock(return_value={"result": {}})
        browser.close = AsyncMock(return_value=None)
        return browser

    def _spawn_engine(self, monkeypatch, process_impl):
        """Fresh ``_RenderEngine`` with Chrome internals monkeypatched away.

        Returns ``(engine, recycle_calls, process_calls)`` where both call
        counters are single-element dicts shared with the engine loop.
        """
        from utils.chart_export import _RenderEngine

        engine = _RenderEngine()
        fake_browser = self._make_fake_browser()
        recycle_calls = {"n": 0}
        process_calls = {"n": 0}

        async def _fake_ensure_browser():
            engine._browser = fake_browser
            engine._started.set()

        async def _fake_recycle_browser():
            recycle_calls["n"] += 1
            engine._needs_recycle.clear()
            engine._render_count = 0

        async def _fake_process(req):
            process_calls["n"] += 1
            return await process_impl(req)

        monkeypatch.setattr(engine, "_ensure_browser", _fake_ensure_browser)
        monkeypatch.setattr(engine, "_recycle_browser", _fake_recycle_browser)
        monkeypatch.setattr(engine, "_process", _fake_process)
        return engine, recycle_calls, process_calls

    @staticmethod
    def _request(timeout: float = 5.0) -> dict:
        # Mirrors the dict generate_svg_bytes_sync() submits.
        return {"fig": None, "fmt": "svg", "width": 100, "height": 100,
                "timeout": timeout}

    def test_first_timeout_recycles_and_retry_succeeds(self, monkeypatch):
        """First _process call times out → engine flips the fallback,
        recycles once, retries → future resolves with the SVG bytes."""
        import utils.chart_export as ce

        impl_state = {"calls": 0}

        async def _process_impl(req):
            impl_state["calls"] += 1
            if impl_state["calls"] == 1:
                raise asyncio.TimeoutError
            return b"<svg>ok</svg>"

        engine, recycle_calls, process_calls = self._spawn_engine(
            monkeypatch, _process_impl,
        )
        try:
            engine.start(block=True)
            result = engine.submit(self._request())
            assert result == b"<svg>ok</svg>"
            assert process_calls["n"] == 2, "initial call + one retry"
            assert recycle_calls["n"] == 1, "recycle exactly once before retry"
            assert ce._SOFTWARE_RENDER_FALLBACK is True
        finally:
            engine.shutdown()

    def test_first_timeout_retry_fails_future_gets_timeout(self, monkeypatch):
        """Retry also times out → future gets TimeoutError; the request is
        recycled once (before the retry) but not a second time."""
        import utils.chart_export as ce

        async def _process_impl(req):
            raise asyncio.TimeoutError

        engine, recycle_calls, process_calls = self._spawn_engine(
            monkeypatch, _process_impl,
        )
        try:
            engine.start(block=True)
            with pytest.raises(TimeoutError):
                engine.submit(self._request())
            assert process_calls["n"] == 2, "initial call + one retry"
            assert recycle_calls["n"] == 1, "no second recycle on retry failure"
            assert ce._SOFTWARE_RENDER_FALLBACK is True
        finally:
            engine.shutdown()

    def test_non_first_timeout_fails_fast_without_retry(self, monkeypatch):
        """When the fallback is already active, a timeout raises immediately:
        no inline recycle and no retry for that request."""
        import utils.chart_export as ce

        ce._SOFTWARE_RENDER_FALLBACK = True

        async def _process_impl(req):
            raise asyncio.TimeoutError

        engine, recycle_calls, process_calls = self._spawn_engine(
            monkeypatch, _process_impl,
        )
        try:
            engine.start(block=True)
            with pytest.raises(TimeoutError):
                engine.submit(self._request())
            assert process_calls["n"] == 1, "no retry on a non-first timeout"
            # The timeout handler schedules a deferred browser recycle via
            # _needs_recycle; the loop performs it on the next iteration
            # (rather than inline-and-retry like the first-timeout path),
            # which is the single recycle recorded here.
            assert recycle_calls["n"] == 1
            assert ce._SOFTWARE_RENDER_FALLBACK is True
        finally:
            engine.shutdown()
