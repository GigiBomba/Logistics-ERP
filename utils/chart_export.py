"""Plotly static image export via Choreographer-backed headless Chrome.

Architecture
------------
A single daemon background thread runs a permanent ``asyncio`` event loop.
The choreographer ``Browser`` is created once on that thread and lives for
the entire process lifetime.  All render requests (SVG, PNG, JPEG) are
submitted to the thread via ``loop.call_soon_threadsafe`` and block the
caller on a ``concurrent.futures.Future``.

This design fixes the fatal cross-thread ``asyncio.Lock`` bug that arose
when ``asyncio.run()`` was called inside multiple ``QThreadPool`` workers:
each call created a new event loop, the ``asyncio.Lock`` was not shared
across them, and multiple Chrome subprocesses launched simultaneously,
resulting in orphaned windows and ``CancelledError`` crashes.

Usage
-----
    from utils.chart_export import configure_choreographer_export
    configure_choreographer_export()          # call once at app startup

    svg = generate_svg_bytes_sync(fig)        # blocks, returns SVG bytes
    png = export_figure_sync(fig, fmt="png")  # blocks, returns PNG bytes

    # On app shutdown (daemon thread joins automatically):
    # shutdown_browser_sync()  # optional clean-up
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import logging
import os
import platform
import tempfile
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio

# ── Silence any Plotly browser-opening attempts ──────────────────────
# Register a dummy webbrowser that does nothing on open() calls so that
# stray show() calls or Plotly's internal renderer hooks never spawn a
# browser window in the Windows desktop environment.
class _DummyBrowser:
    def open(self, url, new=0, autoraise=True):
        pass
    def open_new(self, url):
        pass
    def open_new_tab(self, url):
        pass
webbrowser.register("dummy", None, _DummyBrowser(), preferred=True)
# Force Plotly to serialise figures as raw JSON instead of trying to
# open them in a browser through the default renderer.
pio.renderers.default = "json"

_log = logging.getLogger(__name__)

_CHROME_PATH: str | None = None


def configure_choreographer_export(
    chrome_path: str | Path | None = None,
) -> None:
    """Configure Choreographer for headless static image export.

    Must be called **once** at application startup, before any figure
    export.  Eagerly starts the persistent asyncio thread and launches
    the shared headless Chrome instance.

    Parameters
    ----------
    chrome_path : str, Path, or None
        Absolute path to the Chrome/Chromium/Edge executable.
        When ``None``, Choreographer searches ``PATH`` and common
        install locations for a compatible browser.
    """
    global _CHROME_PATH
    if chrome_path:
        chrome_path_str = str(chrome_path)
        os.environ["BROWSER_PATH"] = chrome_path_str
        _CHROME_PATH = chrome_path_str
    else:
        os.environ.pop("BROWSER_PATH", None)
        _CHROME_PATH = None

    _log.info("Choreographer export configured")
    _get_engine().start(block=True)


# ── Render engine (persistent asyncio thread) ──────────────────────────

_ENGINE: _RenderEngine | None = None
_ENGINE_LOCK = threading.Lock()


def _get_engine() -> _RenderEngine:
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is not None:
            return _ENGINE
        _ENGINE = _RenderEngine()
    return _ENGINE


class _RenderEngine:
    """Singleton that owns a persistent asyncio event loop and Chrome browser."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._browser: Any = None
        self._queue: asyncio.Queue | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._shutdown = False

    def start(self, block: bool = False) -> None:
        """Launch the daemon asyncio thread.

        If *block* is ``True``, this call blocks until Chrome has started
        (or a 30-second timeout elapses).
        """
        if self._thread is not None and self._thread.is_alive():
            return  # already running
        self._thread = threading.Thread(
            target=self._run_loop,
            name="choreographer-engine",
            daemon=True,
        )
        self._thread.start()
        if block:
            self._started.wait(timeout=30)

    def _run_loop(self) -> None:
        """Entry point for the daemon thread — runs ``asyncio.run()`` forever."""
        asyncio.run(self._async_main())

    async def _async_main(self) -> None:
        """Permanent asyncio coroutine: create browser then service render requests."""
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()

        import choreographer as choreo  # type: ignore[import-untyped]

        try:
            self._browser = await asyncio.wait_for(
                choreo.Browser(**_browser_kwargs()),
                timeout=30,
            )
        except ImportError:
            raise
        except Exception as exc:
            _log.warning("Choreographer browser failed to start: %s", exc)
            self._started.set()
            return  # engine thread exits gracefully; renders will fall back to error SVG

        self._started.set()
        _log.info("Render engine ready — shared Chrome browser started")

        while not self._shutdown:
            try:
                request, future = await asyncio.wait_for(
                    self._queue.get(), timeout=5.0,
                )
            except asyncio.TimeoutError:
                continue
            if request is None:
                future.set_result(None)
                break
            try:
                result = await self._process(request)
                future.set_result(result)
            except BaseException as exc:
                if not future.done():
                    future.set_exception(exc)

        # Clean shutdown
        try:
            await asyncio.wait_for(self._browser.close(), timeout=10)
        except Exception:
            _log.warning("Error closing shared browser", exc_info=True)

    async def _process(self, req: dict) -> bytes:
        """Process a single render request (runs in the asyncio thread)."""
        fig: go.Figure = req["fig"]
        fmt: str = req["fmt"]
        width: int = req["width"]
        height: int = req["height"]
        scale: float = req.get("scale", 1.0)
        quality: int = req.get("quality", 92)
        deadline = asyncio.get_event_loop().time() + req.get("timeout", 30.0)

        def _remaining() -> float:
            return max(1.0, deadline - asyncio.get_event_loop().time())

        html = fig.to_html(
            include_plotlyjs="cdn",
            full_html=True,
            default_width=f"{width}px",
            default_height=f"{height}px",
        )

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", encoding="utf-8", delete=False,
        )
        try:
            tmp.write(html)
            tmp.close()
            file_url = Path(tmp.name).resolve().as_uri()

            tab = await asyncio.wait_for(
                self._browser.create_tab(url=file_url),
                timeout=_remaining(),
            )
            try:
                # Set viewport
                await asyncio.wait_for(
                    tab.send_command(
                        "Emulation.setDeviceMetricsOverride",
                        params={
                            "width": width,
                            "height": height,
                            "deviceScaleFactor": 1,
                            "mobile": False,
                        },
                    ),
                    timeout=_remaining(),
                )
                # Wait for page to fully load (subscribe to the event)
                await asyncio.wait_for(
                    tab.subscribe_once("Page.loadEventFired"),
                    timeout=_remaining(),
                )

                if fmt == "svg":
                    return await self._extract_svg(tab, width, height, scale, _remaining())
                else:
                    return await self._capture_image(tab, fmt, quality, _remaining())
            finally:
                try:
                    await asyncio.wait_for(tab.close(), timeout=5)
                except Exception:
                    pass
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    async def _extract_svg(
        self, tab: Any, width: int, height: int, scale: float, timeout: float,
    ) -> bytes:
        """Poll for the SVG element and return its markup."""
        svg_markup = ""
        poll_deadline = asyncio.get_event_loop().time() + timeout
        while not svg_markup.strip():
            if asyncio.get_event_loop().time() > poll_deadline:
                break
            result = await asyncio.wait_for(
                tab.send_command(
                    "Runtime.evaluate",
                    params={
                        "expression": """
                            (function() {
                                var plots = document.querySelectorAll('.js-plotly-plot');
                                if (!plots || !plots.length) return '';
                                var svg = plots[0].querySelector('svg');
                                return svg ? svg.outerHTML : '';
                            })()
                        """,
                        "returnByValue": True,
                    },
                ),
                timeout=min(10.0, timeout),
            )
            if (
                "result" in result
                and "result" in result["result"]
                and "value" in result["result"]["result"]
            ):
                svg_markup = result["result"]["result"]["value"] or ""
            if not svg_markup.strip():
                await asyncio.sleep(0.2)

        if not svg_markup.strip():
            raise RuntimeError("No SVG element found in rendered page")

        svg_markup = svg_markup.replace(
            "<svg ",
            f'<svg width="{int(width * scale)}" height="{int(height * scale)}" ',
            1,
        )
        return svg_markup.encode("utf-8")

    async def _capture_image(
        self, tab: Any, fmt: str, quality: int, timeout: float,
    ) -> bytes:
        """Capture a screenshot of the rendered page."""
        params: dict[str, Any] = {"format": fmt}
        if fmt == "jpeg":
            params["quality"] = quality
        result = await asyncio.wait_for(
            tab.send_command("Page.captureScreenshot", params=params),
            timeout=timeout,
        )
        raw: bytes | None = None
        if "result" in result and "data" in result["result"]:
            raw = base64.b64decode(result["result"]["data"])
        if not raw:
            raise RuntimeError(f"Screenshot returned no data: {result}")
        return raw

    def submit(self, request: dict) -> Any:
        """Submit a render request and block for the result.

        *request* must contain at minimum ``fig``, ``fmt``, ``width``,
        ``height``.  Accepts optional ``scale``, ``quality``, ``timeout``.
        """
        self.start(block=False)
        if not self._started.wait(timeout=35):
            raise RuntimeError("Render engine failed to start within 35 seconds")
        if self._browser is None:
            raise RuntimeError("Choreographer browser is not available")
        future: concurrent.futures.Future = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(  # type: ignore[union-attr]
            self._queue.put_nowait, (request, future),
        )
        return future.result(timeout=request.get("timeout", 30) + 10)

    def shutdown(self) -> None:
        """Signal the engine thread to stop and close the browser."""
        if self._loop is None or self._loop.is_closed():
            return
        if self._queue is None:
            return
        self._shutdown = True
        done_future: concurrent.futures.Future = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(
            self._queue.put_nowait, (None, done_future),
        )
        try:
            done_future.result(timeout=15)
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)


class _SilentChromium:
    """Subclass of Choreographer's Chromium browser with extra silent flags.

    Injects ``--disable-software-rasterizer`` and ``--headless=new`` into
    the Chrome CLI to prevent GPU layers and software fallback from
    creating hidden windows on Windows during headless chart rendering.
    """

    def __init__(self, channel, path=None, **kwargs):
        import choreographer.browsers.chromium as _chromium_mod
        self._wrapped = _chromium_mod.Chromium(channel, path, **kwargs)

    def pre_open(self):
        return self._wrapped.pre_open()

    def is_isolated(self):
        return self._wrapped.is_isolated()

    def get_popen_args(self):
        return self._wrapped.get_popen_args()

    def get_cli(self):
        cli = self._wrapped.get_cli()
        # Force GPU layers and software rasterizer OFF to prevent
        # any hidden window artifact on Windows.
        flags_to_add = [
            "--disable-software-rasterizer",
            "--headless=new",
        ]
        for flag in flags_to_add:
            if flag not in cli:
                cli.append(flag)
        return cli

    def get_env(self):
        return self._wrapped.get_env()

    def clean(self):
        return self._wrapped.clean()

    def __getattr__(self, name):
        return getattr(self._wrapped, name)

    logger_parser = None  # set below if the wrapped class has one


def _browser_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = dict(
        browser_cls=_SilentChromium,
        enable_gpu=False,
        enable_sandbox=False,
    )
    if _CHROME_PATH:
        kwargs["path"] = _CHROME_PATH
    return kwargs


# ── Public synchronous API ─────────────────────────────────────────────


def generate_svg_bytes_sync(
    fig: go.Figure,
    width: int = 700,
    height: int = 300,
    scale: float = 1.0,
    timeout: float = 30.0,
) -> bytes:
    """Render a Plotly figure to SVG bytes.

    Blocks the calling thread while the persistent asyncio engine renders
    the figure via headless Chrome and extracts the SVG from the DOM.
    """
    return _get_engine().submit(dict(
        fig=fig, fmt="svg",
        width=width, height=height, scale=scale, timeout=timeout,
    ))


def export_figure_sync(
    fig: go.Figure,
    fmt: str = "png",
    width: int = 1200,
    height: int = 800,
    scale: float = 2.0,
    quality: int = 92,
    timeout: float = 30.0,
) -> bytes:
    """Render a Plotly figure to a raster image (PNG/JPEG).

    Blocks the calling thread while the persistent asyncio engine renders
    the figure via headless Chrome and captures a screenshot.
    """
    return _get_engine().submit(dict(
        fig=fig, fmt=fmt,
        width=width, height=height, scale=scale,
        quality=quality, timeout=timeout,
    ))


def shutdown_browser_sync(timeout: float = 10.0) -> None:
    """Close the shared browser and stop the render engine thread.

    Safe to call multiple times; no-op once the engine has already shut
    down.  The engine thread is a daemon and will exit automatically on
    process exit, so this call is optional.
    """
    engine = _get_engine()
    engine.shutdown()
