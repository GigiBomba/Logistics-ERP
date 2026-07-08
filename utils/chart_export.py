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

# ── Browser recycling constants ─────────────────────────────────────
# Chrome headless accumulates memory and can degrade over many renders.
# We recycle the browser after this many renders to keep it healthy.
MAX_RENDERS_PER_BROWSER = 50


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
        self._render_count = 0
        self._needs_recycle = threading.Event()
        self._start_lock = threading.Lock()
        self._zombie_tab_count = 0
        self._startup_failures = 0
        self._permanent_failure = threading.Event()

    def start(self, block: bool = False) -> None:
        """Launch the daemon asyncio thread.

        If *block* is ``True``, this call blocks until Chrome has started
        (or a 30-second timeout elapses).

        Protected by ``_start_lock`` to prevent two caller threads from
        creating duplicate Chrome subprocesses (the first becomes orphaned).
        """
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return  # already running
            # Reset state for a fresh engine start
            self._loop = None
            self._browser = None
            self._queue = None
            self._started.clear()
            self._shutdown = False
            self._render_count = 0
            self._zombie_tab_count = 0
            self._startup_failures = 0
            self._permanent_failure.clear()
            self._needs_recycle.clear()
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
        try:
            asyncio.run(self._async_main())
        except BaseException:
            _log.exception("Render engine thread crashed")
        finally:
            # Attempt synchronous browser close to avoid orphaning the
            # Chrome subprocess.  The event loop is already destroyed so
            # we can't await; try the transport-level close instead.
            browser = self._browser
            self._browser = None
            if browser is not None:
                try:
                    if hasattr(browser, "_close_transport"):
                        browser._close_transport()
                except Exception:
                    pass
            self._loop = None
            self._queue = None

    async def _async_main(self) -> None:
        """Permanent asyncio coroutine: create browser then service render requests.

        Automatically recycles the browser every ``MAX_RENDERS_PER_BROWSER``
        renders and immediately after any render timeout or error to prevent
        Chrome headless memory degradation.
        """
        import time as _time
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()

        await self._ensure_browser()

        while not self._shutdown:
            # Check if we need to recycle the browser
            if self._needs_recycle.is_set() or self._render_count >= MAX_RENDERS_PER_BROWSER:
                await self._recycle_browser()

            # If the browser is not available (e.g. failed to start or
            # recycle), try to create it before processing any request.
            if self._browser is None:
                await self._ensure_browser()
                if self._browser is None:
                    # Still no browser — back-off and retry.  Exponential
                    # back-off capped at 30 s and 10 attempts; then signal
                    # permanent failure to any pending request.
                    self._startup_failures += 1
                    delay = min(30.0, 1.0 * (2 ** min(self._startup_failures, 5)))
                    _log.warning(
                        "Browser start failed (attempt %d) — retrying in %.0fs",
                        self._startup_failures, delay,
                    )
                    await asyncio.sleep(delay)
                    if self._startup_failures >= 10:
                        self._permanent_failure.set()
                    continue

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
                # Quick health ping — if the browser is unresponsive even for a
                # simple CDP command, recycle immediately rather than waiting for
                # the full render timeout.
                try:
                    await asyncio.wait_for(
                        self._browser.send_command("Browser.getVersion"),
                        timeout=3.0,
                    )
                except asyncio.TimeoutError:
                    _log.warning("Browser health ping timed out — recycling")
                    self._needs_recycle.set()
                    await self._recycle_browser()
                    if self._browser is None:
                        future.set_exception(RuntimeError("Browser unavailable after recycle"))
                        continue

                request_timeout = request.get("timeout", 30)
                result = await asyncio.wait_for(
                    self._process(request), timeout=request_timeout,
                )
                future.set_result(result)
                self._render_count += 1
                self._zombie_tab_count = 0
            except asyncio.TimeoutError:
                _log.warning(
                    "Render timed out after %.1fs — recycling browser",
                    request.get("timeout", 30),
                )
                self._needs_recycle.set()
                if not future.done():
                    future.set_exception(TimeoutError("Render timed out"))
            except BaseException as exc:
                _log.warning(
                    "Render failed: %s — scheduling browser recycle",
                    exc,
                )
                self._needs_recycle.set()
                if not future.done():
                    future.set_exception(exc)

        # Clean shutdown
        if self._browser is not None:
            try:
                await asyncio.wait_for(self._browser.close(), timeout=10)
            except Exception:
                _log.warning("Error closing shared browser", exc_info=True)
            self._browser = None

    async def _ensure_browser(self) -> None:
        """Create the shared Chrome browser, blocking until ready.

        On failure, sets ``_started`` so callers don't hang, marks the
        browser as ``None``, and logs the error.  The engine loop will
        retry on the next render request.
        """
        import time as _time
        _startup_t0 = _time.perf_counter()

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
            self._browser = None
            self._started.set()
            return

        _startup_elapsed = _time.perf_counter() - _startup_t0
        self._started.set()
        self._startup_failures = 0
        self._permanent_failure.clear()
        _log.info(
            "Render engine ready — shared Chrome browser started in %.2fs",
            _startup_elapsed,
        )

    async def _recycle_browser(self) -> None:
        """Close the current browser and create a fresh one."""
        _log.info(
            "Recycling Chrome browser (render_count=%d)",
            self._render_count,
        )
        old_browser = self._browser
        self._browser = None
        if old_browser is not None:
            try:
                await asyncio.wait_for(old_browser.close(), timeout=10)
            except asyncio.TimeoutError:
                _log.warning("Timeout closing old browser during recycle")
            except Exception:
                _log.warning("Error closing old browser during recycle", exc_info=True)
        self._render_count = 0
        self._zombie_tab_count = 0
        self._startup_failures = 0
        self._permanent_failure.clear()
        self._needs_recycle.clear()
        await self._ensure_browser()

    @staticmethod
    async def _close_tab_safely(tab: Any) -> bool:
        """Close *tab*.  Returns ``True`` on success, ``False`` if it likely
        leaked (zombie tab left in Chrome).

        Three-layer defense:

        1. Normal ``tab.close()`` (5 s timeout).
        2. CDP ``Target.closeTarget`` (3 s timeout) — tries both
           ``target_id`` and ``targetId`` attribute names.
        3. If both fail, logs a warning and returns ``False`` so the
           caller can count the zombie and force-recycle the browser
           when too many accumulate.
        """
        # Layer 1 — normal close
        try:
            await asyncio.wait_for(tab.close(), timeout=5)
            return True
        except asyncio.TimeoutError:
            _log.debug("tab.close() timed out, trying CDP fallback")
        except Exception:
            _log.debug("tab.close() failed, trying CDP fallback", exc_info=True)

        # Layer 2 — CDP-level close
        target_id = getattr(tab, "target_id", None) or getattr(tab, "targetId", None)
        if target_id is not None:
            try:
                await asyncio.wait_for(
                    tab.send_command("Target.closeTarget",
                                     params={"targetId": target_id}),
                    timeout=3,
                )
                return True
            except Exception:
                _log.debug("CDP Target.closeTarget failed", exc_info=True)

        # Layer 3 — try enumerating targets to find and close this one
        try:
            targets_resp = await asyncio.wait_for(
                tab.send_command("Target.getTargets"),
                timeout=3,
            )
            targets = (
                targets_resp.get("result", {})
                .get("result", {})
                .get("targetInfos", [])
            )
            if isinstance(targets, list):
                url_hint = getattr(tab, "_url", "")
                for tinfo in targets:
                    if isinstance(tinfo, dict) and tinfo.get("url") == url_hint:
                        tid = tinfo.get("targetId")
                        if tid and tid != target_id:
                            try:
                                await asyncio.wait_for(
                                    tab.send_command("Target.closeTarget",
                                                     params={"targetId": tid}),
                                    timeout=3,
                                )
                                return True
                            except Exception:
                                pass
        except Exception:
            _log.debug("Target.getTargets fallback failed", exc_info=True)

        _log.warning("Failed to close tab — zombie tab left in Chrome (target_id=%r)", target_id)
        return False

    async def _process(self, req: dict) -> bytes:
        """Process a single render request (runs in the asyncio thread)."""
        import time as _time
        _t0 = _time.perf_counter()

        fig: go.Figure = req["fig"]
        fmt: str = req["fmt"]
        width: int = req["width"]
        height: int = req["height"]
        scale: float = req.get("scale", 1.0)
        quality: int = req.get("quality", 92)
        deadline = asyncio.get_event_loop().time() + req.get("timeout", 30.0)

        def _remaining() -> float:
            return max(1.0, deadline - asyncio.get_event_loop().time())

        # Use embed (inline) plotly.js instead of CDN so that rendering
        # works offline and doesn't hang on slow/unreachable CDN.
        html = fig.to_html(
            include_plotlyjs=True,
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
                    result = await self._extract_svg(tab, width, height, scale, _remaining())
                else:
                    result = await self._capture_image(tab, fmt, quality, _remaining())
                elapsed = _time.perf_counter() - _t0
                _log.debug(
                    "Render %s %dx%d finished in %.2fs (%.1f KB)",
                    fmt, width, height, elapsed, len(result) / 1024,
                )
                return result
            finally:
                if not await self._close_tab_safely(tab):
                    self._zombie_tab_count += 1
                    if self._zombie_tab_count >= 5:
                        _log.warning(
                            "%d zombie tabs — forcing browser recycle",
                            self._zombie_tab_count,
                        )
                        self._needs_recycle.set()
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    async def _extract_svg(
        self, tab: Any, width: int, height: int, scale: float, timeout: float,
    ) -> bytes:
        """Extract the SVG element from the rendered page.

        Polls the DOM for ``.js-plotly-plot svg`` with a maximum of one
        CDP call every 500 ms to avoid congesting the Chrome DevTools
        channel.
        """

        async def _poll_svg() -> str:
            poll_deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = poll_deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
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
                        timeout=min(5.0, remaining),
                    )
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    _log.debug("SVG poll CDP error", exc_info=True)
                    break
                if (
                    "result" in result
                    and "result" in result["result"]
                    and "value" in result["result"]["result"]
                ):
                    svg_markup = result["result"]["result"]["value"] or ""
                    if svg_markup.strip():
                        return svg_markup
                await asyncio.sleep(0.5)
            return ""

        try:
            svg_markup = await asyncio.wait_for(
                _poll_svg(), timeout=timeout + 2,
            )
        except asyncio.TimeoutError:
            svg_markup = ""

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
        import time as _time
        _t0 = _time.perf_counter()
        fmt = request.get("fmt", "svg")
        w = request.get("width", 0)
        h = request.get("height", 0)
        _log.debug("Submit render %s %dx%d", fmt, w, h)
        self.start(block=False)
        if not self._started.wait(timeout=35):
            raise RuntimeError("Render engine failed to start within 35 seconds")
        if self._permanent_failure.is_set():
            raise RuntimeError(
                "Render engine permanently failed — Chrome cannot start. "
                "Check that a Chromium-based browser is installed and "
                "not blocked by antivirus."
            )
        # Browser availability is handled inside the asyncio loop.
        # If the browser is None (e.g. during recycle), the loop will
        # start one before processing the request.
        future: concurrent.futures.Future = concurrent.futures.Future()
        if self._loop is None or self._loop.is_closed():
            raise RuntimeError("Render engine event loop is not running")
        self._loop.call_soon_threadsafe(  # type: ignore[union-attr]
            self._queue.put_nowait, (request, future),
        )
        result = future.result(timeout=request.get("timeout", 30) + 10)
        elapsed = _time.perf_counter() - _t0
        _log.debug("Render %s %dx%d completed in %.2fs (total wait)", fmt, w, h, elapsed)
        return result

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
    """Subclass of Choreographer's Chromium browser with aggressive silent flags.

    Injects comprehensive Chrome CLI flags and subprocess-creation overrides
    to prevent ANY transient windows or auxiliary processes (Crashpad, GPU
    compositor, background network services) on Windows during headless
    chart rendering.
    """

    def __init__(self, channel, path=None, **kwargs):
        import choreographer.browsers.chromium as _chromium_mod
        self._wrapped = _chromium_mod.Chromium(channel, path, **kwargs)

    def pre_open(self):
        return self._wrapped.pre_open()

    def is_isolated(self):
        return self._wrapped.is_isolated()

    def get_popen_args(self):
        """Return subprocess args, adding ``CREATE_NO_WINDOW`` on Windows
        and setting ``STARTUPINFO.wShowWindow = SW_HIDE`` so the Chrome
        child process never draws a visible window at startup.
        """
        args = dict(self._wrapped.get_popen_args())
        if platform.system() == "Windows":
            import subprocess as _subprocess
            existing = args.get("creationflags", 0)
            args["creationflags"] = existing | _subprocess.CREATE_NO_WINDOW
            # Set the startup info to hide the window from the first frame.
            si = _subprocess.STARTUPINFO()
            si.dwFlags = _subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = _subprocess.SW_HIDE
            args["startupinfo"] = si
        return args

    def get_cli(self):
        cli = list(self._wrapped.get_cli())
        # Strip flags from the base Chromium class that either conflict
        # with our replacements or are known to cause issues:
        #   --headless           → replaced by --headless=new below
        #   --disable-gpu        → conflicts with --headless=new (new headless
        #                          mode  needs GPU  acceleration  to work; with
        #                          GPU off Chrome creates a visible software-
        #                          rendered window as fallback on Windows).
        #                          We keep the more targeted
        #                          --disable-gpu-compositing instead.
        #   --user-data-dir=...  → replaced by our persistent dir below
        cli = [
            a for a in cli
            if a != "--headless"
            and a != "--disable-gpu"
            and not a.startswith("--user-data-dir=")
        ]

        # Comprehensive set of flags to suppress EVERY source of
        # transient windows / auxiliary processes on Windows:
        #   - Crashpad crash-reporter (creates crashpad_handler.exe)
        #   - GPU compositor / software-rasterizer (GPU driver windows)
        #   - Translate UI, What's New, background networking
        #   - Window position pushed far off-screen so the DWM frame
        #     lands outside any physical monitor boundary
        flags_to_add = [
            "--headless=new",
            "--window-position=-10000,-10000",
            "--window-size=10,10",
            "--disable-software-rasterizer",
            "--disable-crashpad-for-testing",
            "--disable-gpu-compositing",
            "--disable-features=TranslateUI,Crashpad,ChromeWhatsNewUI",
            "--disable-background-networking",
            "--disable-component-extensions-with-background-pages",
            "--disable-extensions",
            "--no-default-browser-check",
            "--no-first-run",
            f"--user-data-dir={_ensure_profile_dir()}",
        ]
        for flag in flags_to_add:
            if flag not in cli:
                cli.append(flag)
        _log.info("Chrome CLI flags: %s", " ".join(cli))
        return cli

    def get_env(self):
        return self._wrapped.get_env()

    def clean(self):
        return self._wrapped.clean()

    def __getattr__(self, name):
        return getattr(self._wrapped, name)

    logger_parser = None  # set below if the wrapped class has one


_PERSISTENT_PROFILE_DIR: str = os.path.join(
    tempfile.gettempdir(), "operion_chrome_profile"
)
"""Persistent Chromium user-data directory.

Using a fixed (non-temporary) profile means Chrome skips the first-time
setup / telemetry / what's-new UI checks that execute when it detects a
brand new profile.  The first-ever boot still runs that initialisation,
but subsequent app launches reuse the cached profile and avoid the
transient windows those checks create.
"""


def _ensure_profile_dir() -> str:
    os.makedirs(_PERSISTENT_PROFILE_DIR, exist_ok=True)
    return _PERSISTENT_PROFILE_DIR


def _browser_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = dict(
        browser_cls=_SilentChromium,
        enable_gpu=False,
        enable_sandbox=False,
        tmp_dir=_ensure_profile_dir(),
    )
    if _CHROME_PATH:
        kwargs["path"] = _CHROME_PATH
    _log.debug("Browser kwargs: tmp_dir=%s, path=%s, gpu=%s, sandbox=%s",
               _PERSISTENT_PROFILE_DIR,
               _CHROME_PATH,
               False, False)
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
