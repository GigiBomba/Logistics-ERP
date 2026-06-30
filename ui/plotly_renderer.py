"""Plotly-to-Qt rendering bridge for Operion ERP.

Replaces matplotlib's ``FigureCanvasQTAgg`` embedding with a lightweight
kaleido → SVG → QPixmap pipeline.  Key components:

* ``figure_to_svg_bytes()`` — render a Plotly figure to raw SVG bytes.
* ``figure_to_qpixmap()`` — convert SVG bytes to a QPixmap for ``QLabel``.
* ``empty_figure()`` — return a placeholder figure for no-data states.
* ``sparkline_figure()`` — minimal sparkline figure (no axes / chrome).
* ``RenderManager`` — singleton background render queue.  Kaleido SVG
  rendering takes ~1 second per chart on the main thread, freezing the
  UI.  ``RenderManager`` runs renders in a ``QThreadPool`` and emits the
  resulting ``QPixmap`` back to the main thread via a queued signal.
* ``PlotlyChartWidget`` — reusable QFrame that accepts a ``go.Figure``
  and displays it, with debounced resize re-rendering and async
  off-thread rendering via ``RenderManager``.

Usage::

    from ui.plotly_renderer import PlotlyChartWidget
    widget = PlotlyChartWidget()
    widget.set_figure(fig)        # returns immediately; pixmap arrives later
    parent_layout.addWidget(widget)
"""

from __future__ import annotations

import itertools
import logging

import plotly.graph_objects as go
from PySide6.QtCore import (
    QByteArray,
    QObject,
    QRectF,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from services.i18n import t as _t
from ui.design_tokens import (
    BG_SURFACE,
    FONT_FAMILY,
    TEXT_MUTED,
)
from ui.plotly_theme import (
    PLOTLY_ACCENT,
    apply_sparkline_theme,
)

_log = logging.getLogger(__name__)

# ── Rendering helpers ──────────────────────────────────────────────


def figure_to_svg_bytes(
    fig: go.Figure,
    width: int = 700,
    height: int = 300,
    scale: float = 1.0,
) -> bytes:
    """Render *fig* to SVG bytes via the kaleido engine.

    Parameters
    ----------
    fig : go.Figure
        The Plotly figure to render.  Its template should already be set
        (call ``apply_operion_theme(fig)`` beforehand).
    width, height : int
        Desired output dimensions in CSS pixels.
    scale : float
        Scale factor for HiDPI displays (2.0 for Retina).

    Returns
    -------
    bytes
        Raw SVG markup.
    """
    try:
        img_bytes: bytes = fig.to_image(
            format="svg",
            width=width,
            height=height,
            scale=scale,
        )
        return img_bytes
    except Exception:
        _log.exception("Kaleido SVG render failed")
        return _fallback_svg(width, height, "Render error")


def figure_to_qpixmap(
    fig: go.Figure,
    width: int = 700,
    height: int = 300,
    scale: float = 1.0,
) -> QPixmap:
    """Convert *fig* to a QPixmap suitable for display in a QLabel.

    Uses QSvgRenderer for robust SVG→pixmap rasterization.
    """
    svg_bytes = figure_to_svg_bytes(fig, width, height, scale)
    return _svg_bytes_to_pixmap(svg_bytes, width, height, scale)


def _svg_bytes_to_pixmap(
    svg_bytes: bytes,
    width: int,
    height: int,
    scale: float = 1.0,
) -> QPixmap:
    """Rasterize SVG bytes into a QPixmap via QSvgRenderer."""
    pw = max(1, int(width * scale))
    ph = max(1, int(height * scale))
    pixmap = QPixmap(pw, ph)
    pixmap.fill(Qt.transparent)

    renderer = QSvgRenderer(QByteArray(svg_bytes))
    if not renderer.isValid():
        _log.warning("Invalid SVG produced by kaleido")
        return _error_pixmap(width, height, scale)

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        renderer.render(painter, QRectF(0, 0, pw, ph))
    finally:
        painter.end()

    pixmap.setDevicePixelRatio(scale)
    return pixmap


def _error_pixmap(width: int, height: int, scale: float = 1.0) -> QPixmap:
    """Return a small placeholder pixmap for error states."""
    pw = max(1, int(width * scale))
    ph = max(1, int(height * scale))
    pixmap = QPixmap(pw, ph)
    pixmap.fill(Qt.transparent)
    return pixmap


def _fallback_svg(width: int, height: int, message: str) -> bytes:
    """Return a minimal SVG showing an error message."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}">'
        f'<rect width="100%" height="100%" fill="{BG_SURFACE}"/>'
        f'<text x="50%" y="50%" text-anchor="middle" '
        f'dominant-baseline="central" '
        f'fill="{TEXT_MUTED}" font-family="{FONT_FAMILY}" '
        f'font-size="13">{message}</text>'
        f"</svg>"
    ).encode()


# ── Empty / error figure factories ─────────────────────────────────


def empty_figure(message: str = "") -> go.Figure:
    """Return a placeholder Plotly figure for no-data or empty states.

    The figure displays *message* centered on a dark background with
    hidden axes — visually identical to the old matplotlib empty state.
    """
    if not message:
        message = _t("common.no_data")

    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": TEXT_MUTED, "size": 13, "family": FONT_FAMILY},
    )
    fig.update_layout(
        template="operion_dark",
        xaxis={"visible": False, "fixedrange": True},
        yaxis={"visible": False, "fixedrange": True},
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        paper_bgcolor=BG_SURFACE,
        plot_bgcolor=BG_SURFACE,
    )
    return fig


# ── Sparkline figure ───────────────────────────────────────────────


def sparkline_figure(
    values: list,
    color: str = "",
    show_area: bool = True,
    width: int = 260,
    height: int = 45,
) -> go.Figure:
    """Build a minimal sparkline figure with no chrome.

    Parameters
    ----------
    values : list[float]
        The data points to plot.
    color : str
        Hex colour for the line.  Defaults to accent if empty.
    show_area : bool
        Whether to fill the area below the line.
    width, height : int
        Output dimensions in CSS pixels (used only for SVG export,
        not for the Plotly layout itself).

    Returns
    -------
    go.Figure
        A figure with transparent background, hidden axes, and no
        margins — ready to be rendered to SVG via kaleido.
    """
    if not color:
        color = PLOTLY_ACCENT

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            y=list(values),
            mode="lines",
            line={"color": color, "width": 1.5},
            fill="tozeroy" if show_area else None,
            fillcolor=("rgba(99,102,241,0.15)"
                        if show_area else None),
            hoverinfo="none",
        )
    )
    apply_sparkline_theme(fig)
    fig.update_layout(
        width=width,
        height=height,
    )
    return fig


# ── Background render manager ──────────────────────────────────────


class _RenderSignals(QObject):
    """QObject that carries the ``QPixmap`` result of an async render.

    Defined at module level so the type can be used by both the
    ``RenderManager`` (emitter) and ``PlotlyChartWidget`` (consumer)
    without circular dependencies.
    """

    delivered = Signal(object, object)  # (tag, QPixmap)


class _RenderJob(QRunnable):
    """A single kaleido SVG render that runs in a worker thread.

    The job is submitted to ``QThreadPool``.  When the render finishes
    (or fails) the result is delivered back to the main thread via the
    ``RenderManager._signals.delivered`` queued signal.  Callbacks are
    identified by a unique ``tag`` token so multiple consumers (e.g.
    several ``PlotlyChartWidget`` instances) can each receive their
    own pixmap.

    Lifecycle: ``setAutoDelete(True)`` lets Qt reclaim the C++ object
    after ``run()`` returns.  We deliberately keep a *Python* reference
    to ``signals`` so the QObject that emits ``delivered`` is not
    garbage-collected while a worker is still running.  ``RenderManager``
    also pins every live job in ``self._live_jobs`` until completion
    (see ``_on_delivered``), preventing premature C++ deletion from
    outliving the worker thread.
    """

    def __init__(
        self,
        tag: object,
        fig: go.Figure,
        width: int,
        height: int,
        scale: float,
        signals: _RenderSignals,
    ):
        super().__init__()
        self.tag = tag
        self.fig = fig
        self.width = int(width)
        self.height = int(height)
        self.scale = float(scale)
        self.signals = signals
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Render the figure to a ``QPixmap`` and emit it to the main thread."""
        try:
            svg_bytes = figure_to_svg_bytes(
                self.fig, self.width, self.height, self.scale
            )
            pixmap = _svg_bytes_to_pixmap(
                svg_bytes, self.width, self.height, self.scale
            )
        except Exception:
            _log.exception("Async kaleido render failed")
            pixmap = _error_pixmap(self.width, self.height, self.scale)
        # The signals object is a process-wide singleton owned by
        # ``RenderManager``.  Guard against the case where the manager
        # has already been torn down (e.g. during interpreter exit).
        try:
            self.signals.delivered.emit(self.tag, pixmap)
        except RuntimeError:
            _log.debug("Render delivered after manager teardown; dropping pixmap")


class RenderManager(QObject):
    """Process-wide queue that off-loads kaleido SVG renders to a thread pool.

    Kaleido v1 takes roughly one second per chart to render a Plotly
    figure to SVG, and the operation is CPU-bound (Chromium subprocess).
    Doing this on the GUI thread freezes the application for several
    seconds on a typical analytics page (10+ charts).

    ``RenderManager`` solves this by:

    * dispatching each render to ``QThreadPool`` (concurrent, up to
      ``MAX_CONCURRENT`` workers);
    * delivering the resulting ``QPixmap`` back to the main thread via
      a queued ``Signal`` (thread-safe);
    * supporting request cancellation — when ``cancel(tag)`` is called,
      the late-arriving result is ignored by the consumer (it must check
      the tag itself).

    The manager is a singleton — ``get_render_manager()`` returns the
    same instance for the lifetime of the process.
    """

    @classmethod
    def _max_concurrent(cls) -> int:
        """Resolve the kaleido concurrency for the current machine.

        Uses the formula ``max(1, min(2, cpu // 2))`` which produces:

        ===========  ==============  =================
        CPU cores    Max concurrent  Notes
        ===========  ==============  =================
        2            1               small / low-end
        4            2               typical workstation
        6            2               modern desktop
        8+           2               capped to limit Chromium spawn
        ===========  ==============  =================

        Kaleido is **Chromium-bound**, not CPU-bound: each concurrent
        render spawns a headless Chrome process.  Empirically,
        multiple kaleido workers contend for the same Chrome profile
        directory and the resulting overhead is much worse than
        running 1–2 renders in parallel — the cap of 2 keeps the
        profile contention in check while still allowing some
        parallelism on a 4+ core machine.  The lower bound of 1
        ensures single-CPU laptops are not deadlocked.
        """
        try:
            import os
            cpu = os.cpu_count() or 4
        except Exception:
            cpu = 4
        return max(1, min(2, cpu // 2))

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        # Cap concurrent kaleido renders to a CPU-aware value.  See
        # ``_max_concurrent`` for the formula.  Resolved at
        # construction time so the user can see the value in
        # ``stats()``.
        self._max_threads = self._max_concurrent()
        self._pool.setMaxThreadCount(self._max_threads)
        # Signal carrier — created in the calling thread (the GUI
        # thread for the singleton) so it already lives there.  The
        # QRunnable emits ``delivered`` from a worker thread, but Qt
        # auto-detects the cross-thread case and uses a queued
        # connection to deliver back to the main thread.
        self._signals = _RenderSignals()
        self._signals.delivered.connect(self._on_delivered, Qt.QueuedConnection)
        self._id_counter = itertools.count(1)
        self._active_tags: set = set()
        # Keep strong Python references to live jobs so the C++
        # QRunnable is not auto-deleted mid-render, which would race
        # with the signal emission at the end of ``run()``.
        self._live_jobs: set = set()
        self._stats_total = 0
        self._stats_async = 0

    def submit(
        self,
        fig: go.Figure,
        width: int,
        height: int,
        scale: float = 1.0,
    ) -> object:
        """Submit a render request; returns a unique ``tag`` token.

        Connect to ``delivered`` (on ``RenderManager.signals()``) to
        receive the ``QPixmap``.  The signal carries ``(tag, pixmap)``,
        so consumers must compare the received tag against their own
        to detect stale requests.
        """
        tag = next(self._id_counter)
        self._active_tags.add(tag)
        self._stats_total += 1
        self._stats_async += 1
        job = _RenderJob(tag, fig, int(width), int(height), float(scale), self._signals)
        # Pin the job to a set keyed by tag so it is not auto-collected
        # while the worker thread is still rendering.  The set is pruned
        # by ``_on_delivered`` once the pixmap is emitted.
        self._live_jobs.add((tag, job))
        self._pool.start(job)
        return tag

    @property
    def signals(self) -> _RenderSignals:
        """The signal carrier used to deliver completed pixmaps."""
        return self._signals

    def cancel(self, tag: object) -> None:
        """Mark a tag as no longer relevant.

        Note: the underlying render still runs to completion in the
        worker thread (kaleido cannot be interrupted mid-render), but
        the result will be dropped by the consumer.
        """
        self._active_tags.discard(tag)

    def is_active(self, tag: object) -> bool:
        """Whether the render tagged *tag* is still in flight."""
        return tag in self._active_tags

    def stats(self) -> dict[str, int]:
        """Return diagnostic counters for tests / debugging.

        Includes ``effective_concurrency`` — the actual thread-pool
        limit resolved at construction time from the host's CPU
        count.  Useful for tests that want to assert the formula
        behaviour without hard-coding the value.
        """
        return {
            "total_requests": self._stats_total,
            "async_requests": self._stats_async,
            "active": len(self._active_tags),
            "effective_concurrency": self._max_threads,
        }

    def wait_for_done(self, msec: int = -1) -> bool:
        """Block until all queued renders complete (test helper)."""
        return self._pool.waitForDone(msec)

    @Slot(object, object)
    def _on_delivered(self, tag: object, _pixmap: QPixmap) -> None:
        """Internal slot: remove *tag* from the active set once delivered."""
        self._active_tags.discard(tag)
        # Drop the strong job reference so the QRunnable (and the
        # captured ``signals`` QObject) can be collected now that the
        # worker has finished and emitted its pixmap.
        self._live_jobs = {
            (t, j) for (t, j) in self._live_jobs if t != tag
        }


_render_manager: RenderManager | None = None


def get_render_manager() -> RenderManager:
    """Return the process-wide ``RenderManager`` (lazy singleton)."""
    global _render_manager
    if _render_manager is None:
        _render_manager = RenderManager()
    return _render_manager


# ── Reusable chart widget ──────────────────────────────────────────


class PlotlyChartWidget(QFrame):
    """A QFrame that displays a Plotly figure rendered to SVG via kaleido.

    Drop-in replacement for ``FigureCanvasQTAgg``.  Call
    ``set_figure(fig)`` to display a chart.

    Rendering is **asynchronous**: ``set_figure`` returns immediately
    and the resulting ``QPixmap`` is delivered later via
    ``RenderManager``.  This keeps the GUI thread responsive while
    kaleido spins up Chromium for the SVG export.

    The widget handles resize events with a 150 ms debounce to avoid
    re-rendering on every pixel change during window resize.  Stale
    renders (queued before a resize) are detected by tag and dropped.
    """

    # Minimum dimensions enforced on the inner pixmap label
    MIN_WIDTH = 100
    MIN_HEIGHT = 60

    _DEBOUNCE_MS = 150

    # Only re-render the kaleido SVG when the size change exceeds this
    # threshold.  Below it, the existing pixmap is just re-stretched
    # by Qt (free).  16 px is enough to absorb window-drag jitter and
    # DPI rounding without spurious kaleido calls.
    RESIZE_THRESHOLD_PX = 16

    def __init__(
        self,
        parent: QFrame | None = None,
        min_height: int = 0,
    ):
        super().__init__(parent)
        self._fig: go.Figure | None = None
        self._fig_id: int = 0  # last ``id()`` of the figure we rendered
        self._width: int = 420
        self._height: int = 170
        self._min_height: int = min_height
        self._scale: float = 1.0
        self._resize_timer: QTimer | None = None
        # The owning tab (or any owner) that should be notified when a
        # render completes.  Used by the analytics view's loading
        # overlay to count how many renders have completed per tab.
        # ``None`` for chart widgets that are not owned by a tab
        # (e.g. the overview view's profit chart).  See
        # ``BaseTab._install_overlay`` and ``set_owner`` below.
        self._owner = None
        # Tag of the currently in-flight render; ``None`` when idle.
        # Used to drop stale results delivered after a resize.
        self._pending_tag: object | None = None
        # ``True`` once ``showEvent`` has issued the first render.
        # Used to deduplicate the show-time render and the first
        # ``resizeEvent``-triggered render (both fire on the first
        # show and would otherwise double-render the chart).
        self._first_render_queued: bool = False
        # Latest tag whose pixmap we accepted; used to dedupe
        # ``delivered`` signals when the worker pool coalesces runs.
        self._accepted_tag: object | None = None
        # Per-instance LRU pixmap cache.  Bounded FIFO keyed by
        # ``(id(fig), w, h)`` so a re-render of the same figure at the
        # same size is a free hit.  Common case: re-entering a view
        # that already rendered the chart — the cached pixmap is
        # applied directly without a kaleido call.
        self._pixmap_cache: dict[tuple[int, int, int], QPixmap] = {}

        self.setObjectName("plotly-chart-card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        if min_height > 0:
            self.setMinimumHeight(min_height)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._label.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        if min_height > 0:
            self._label.setMinimumHeight(min_height)
        self._label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._label)

        # Wire the singleton render manager's ``delivered`` signal once
        # per widget.  All renders flow through this single slot; the
        # ``_pending_tag`` guard ensures only the most recent render
        # actually paints the label.
        manager = get_render_manager()
        manager.signals.delivered.connect(self._on_render_delivered, Qt.QueuedConnection)

    # ── public API ─────────────────────────────────────────────

    def set_figure(self, fig: go.Figure) -> None:
        """Store the figure and queue a render.

        Returns immediately; the pixmap is delivered later via the
        background render manager.

        The per-instance LRU cache is consulted first: if the same
        figure was rendered at the current target size, the cached
        pixmap is applied directly without a kaleido call.  This is
        the common case after a view-switch — re-entering a view that
        already rendered the chart is instant.

        Deferral rules (preserved verbatim — these are what the rest
        of the file relies on):

        * ``self.width() <= 0 or self.height() <= 0`` — the widget
          itself has not been sized yet (rare; usually means it has
          been orphaned from the layout).
        * ``self._label.width() <= 0`` — the inner QLabel has not
          been laid out yet.  This is the common case for widgets
          constructed inside a tab/grid that has not been shown.
          Without this guard we would submit a render at the
          ``MIN_WIDTH × MIN_HEIGHT`` default size, which is then
          immediately superseded by ``showEvent`` when the real
          layout completes — wasting a kaleido call per chart.

        When any of these conditions hold, the figure is stored and
        ``showEvent`` is the single first-render entry point.  On
        re-renders (data change, resize) the widget is already laid
        out so the cache-or-render path runs immediately.
        """
        self._fig = fig
        new_fig_id = id(fig)

        # Defer to ``showEvent`` if the widget has not been shown yet.
        # The ``_label.width()`` heuristic is unreliable because the
        # label's ``setMinimumSize(100, 60)`` makes its reported
        # width be 100 even before layout.  ``isVisible()`` is the
        # only correct signal: it returns True only after the widget
        # has been added to a visible parent hierarchy.
        #
        # We also defer if the widget is hidden (``isHidden()``) — this
        # handles the re-render after a tab-switch-back case where
        # the user has switched to a different tab and the current
        # widget is temporarily hidden.
        if not self.isVisible():
            return
        w = max(self.MIN_WIDTH, self._label.width())
        h = max(self.MIN_HEIGHT, self._label.height())
        if self._min_height > 0:
            h = max(h, self._min_height)

        # LRU cache hit — apply directly.  This is the fast path for
        # re-entering a view whose chart was already rendered.
        cached = self._pixmap_cache.get((new_fig_id, w, h))
        if cached is not None and not cached.isNull():
            self._width = w
            self._height = h
            self._fig_id = new_fig_id
            self._pending_tag = None
            self._label.setPixmap(cached)
            # Notify the owner on cache hits too — otherwise the
            # loading overlay would never count cached charts and
            # would hit its 30 s safety timeout with received=0.
            self._notify_owner()
            return

        # No cache hit — submit a fresh render.
        self._queue_render(w=w, h=h, fig_id=new_fig_id)

    def figure(self) -> go.Figure | None:
        """Return the currently stored figure, if any."""
        return self._fig

    def set_min_height(self, px: int) -> None:
        """Set a minimum height in pixels for the inner label."""
        self._min_height = max(0, px)
        if px > 0:
            self._label.setMinimumHeight(px)

    def set_owner(self, owner) -> None:
        """Set the owning object that should be notified on render completion.

        ``owner`` is expected to expose a ``_on_chart_rendered(widget)``
        method.  The widget calls it from its render-delivery slot so
        the analytics view's loading overlay can count completions per
        tab.

        Pass ``None`` to detach the owner.
        """
        self._owner = owner

    def _notify_owner(self) -> None:
        """Call ``self._owner._on_chart_rendered(self)`` if an owner is set.

        Extracted from ``_on_render_delivered`` so the cache-hit
        short-circuit in ``set_figure`` and ``showEvent`` can notify
        the owner as well.  Without this, a tab whose every chart
        hits the LRU cache would never reach the ``received ==
        expected`` threshold and the loading overlay would time out.
        """
        if self._owner is None:
            return
        if not hasattr(self._owner, "_on_chart_rendered"):
            return
        try:
            self._owner._on_chart_rendered(self)
        except Exception:
            _log.exception("Owner render notification failed")

    def owner(self):
        """Return the current owner (``None`` when not set)."""
        return self._owner

    # ── internal rendering ─────────────────────────────────────

    def _queue_render(self, w: int | None = None, h: int | None = None, fig_id: int | None = None) -> None:
        """Submit the current figure to the render manager.

        If the figure is ``None`` we show the empty placeholder
        immediately (no need to round-trip through the worker).

        ``w`` / ``h`` / ``fig_id`` are pre-computed by the caller
        (typically ``set_figure``) when the size and figure identity
        are already known — avoids recomputing the LRU cache key.
        """
        if self._fig is None:
            self._pending_tag = None
            self._render_empty()
            return

        if w is None:
            w = max(self.MIN_WIDTH, self._label.width())
        if h is None:
            h = max(self.MIN_HEIGHT, self._label.height())
            if self._min_height > 0:
                h = max(h, self._min_height)
        if fig_id is None:
            fig_id = id(self._fig)

        # Remember the target size so we can scale the pixmap correctly
        # when it arrives.  This must happen *before* the async render
        # is submitted, otherwise a subsequent resize could shrink the
        # label between submission and delivery and the wrong scale
        # would be applied.
        self._width = w
        self._height = h
        self._fig_id = fig_id

        manager = get_render_manager()
        # Cancel any previous in-flight render; its pixmap is now stale
        # and must not be applied to the label.
        if self._pending_tag is not None:
            manager.cancel(self._pending_tag)
        self._pending_tag = manager.submit(
            self._fig, w, h, self._scale
        )

    # Maximum number of pixmaps cached per widget.  Bound chosen so
    # the worst-case memory is ~4 × 1000×500×4 bytes ≈ 8 MB per chart
    # widget — well under typical memory ceilings while still
    # amortising kaleido cost across typical UI navigation patterns.
    CACHE_MAX_ENTRIES = 4

    def _cache_pixmap(self, fig_id: int, w: int, h: int, pixmap: QPixmap) -> None:
        """Store a delivered pixmap in the per-widget LRU cache.

        Uses a simple bounded FIFO (the latest entry wins; the
        oldest is evicted on overflow).  A real LRU could be done
        with ``OrderedDict.move_to_end`` but the win is marginal at
        this size and FIFO is far simpler.
        """
        if pixmap is None or pixmap.isNull():
            return
        if w <= 0 or h <= 0:
            return
        # Drop the oldest entry if the cache is full.  We track
        # insertion order via a parallel list; for our small size
        # this is cheap and keeps the implementation local.
        if len(self._pixmap_cache) >= self.CACHE_MAX_ENTRIES:
            # Find any key whose fig_id is not the most recent one.
            # (Picking the lexicographically smallest ``id`` is good
            # enough — id() values monotonically increase within a
            # process for live objects.)
            evict_key = min(
                self._pixmap_cache.keys(),
                key=lambda k: k[0],
            )
            self._pixmap_cache.pop(evict_key, None)
        self._pixmap_cache[(fig_id, w, h)] = pixmap

    @Slot(object, object)
    def _on_render_delivered(self, tag: object, pixmap: QPixmap) -> None:
        """Apply the delivered pixmap to the label, ignoring stale tags.

        Also stores the pixmap in the per-widget LRU cache so the
        same figure at the same size is a free hit on the next
        ``set_figure`` call (typical after a view-switch).
        """
        if tag != self._pending_tag:
            # Stale render — a newer request has already been queued.
            return
        self._accepted_tag = tag
        self._pending_tag = None
        if pixmap is None or pixmap.isNull():
            self._render_empty()
            return
        # Populate the cache BEFORE applying, so even if the label
        # reflows, the next ``set_figure`` for the same figure+size
        # is a hit.
        self._cache_pixmap(self._fig_id, self._width, self._height, pixmap)
        self._label.setPixmap(pixmap)
        # Notify the owning tab so its loading overlay can count
        # completions.  Only fires for the active tab — pre-warmed
        # tabs do not have an active overlay.
        self._notify_owner()

    def _render_empty(self) -> None:
        """Show a subtle placeholder when no figure is set."""
        w = max(self.MIN_WIDTH, self._label.width())
        h = max(self.MIN_HEIGHT, self._label.height())
        svg_bytes = _fallback_svg(w, h, "")
        pixmap = _svg_bytes_to_pixmap(svg_bytes, w, h, self._scale)
        if pixmap is not None and not pixmap.isNull():
            self._label.setPixmap(pixmap)

    # ── Qt overrides ───────────────────────────────────────────

    def resizeEvent(self, event) -> None:
        """Debounce resize: only re-render after the user stops dragging."""
        super().resizeEvent(event)
        if self._resize_timer is None:
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._on_resize_finished)
        self._resize_timer.start(self._DEBOUNCE_MS)

    def _on_resize_finished(self) -> None:
        """Called after the resize debounce timer fires.

        Three-step strategy, in order of cost:

        1. If the size has not actually changed, do nothing.
        2. If a render is already in flight (e.g. ``showEvent`` just
           queued one), do nothing — the in-flight render will
           populate the pixmap and ``showEvent``'s render is
           sufficient.  Without this guard the first show + first
           resize would submit two renders per chart.
        3. If the size change is below the threshold
           (``RESIZE_THRESHOLD_PX``), let Qt re-stretch the existing
           pixmap (free).
        4. If the cache has a pixmap for the new size, apply it
           directly (free).
        5. Otherwise, submit a fresh kaleido render.
        """
        new_w = self._label.width()
        new_h = self._label.height()
        if self._fig is None:
            return
        # If a render is already in flight (typically from the
        # ``showEvent`` that fires on the first show), do nothing.
        # The in-flight render will use the new size — and the
        # cache lookup in ``_on_render_delivered`` will store the
        # pixmap under the correct key.
        if self._pending_tag is not None:
            return
        w_delta = abs(new_w - self._width)
        h_delta = abs(new_h - self._height)
        if w_delta <= self.RESIZE_THRESHOLD_PX and h_delta <= self.RESIZE_THRESHOLD_PX:
            return  # tiny change; Qt re-stretch is enough
        cached = self._pixmap_cache.get((self._fig_id, new_w, new_h))
        if cached is not None and not cached.isNull():
            self._width = new_w
            self._height = new_h
            self._pending_tag = None
            self._label.setPixmap(cached)
            return
        self._queue_render()

    def showEvent(self, event) -> None:
        """Re-render when the widget becomes visible.

        Only fires a render if the widget has a real (non-minimum)
        size and the pixmap is missing.  At construction time the
        widget size is 0×0; ``set_figure`` defers the first render to
        this event.  Subsequent re-renders (e.g. after a tab switch)
        skip when the pixmap is still present — so a view-switch
        does not trigger a kaleido call when the cached pixmap is
        reusable.

        ``showEvent`` may fire multiple times during the first
        show (e.g. when the parent layout is re-laid out, or when
        the widget transitions between hidden and visible).  The
        ``_pending_tag`` guard prevents duplicate render
        submissions: if a render is already in flight, do nothing —
        the in-flight render will populate the pixmap.
        """
        super().showEvent(event)
        if self._fig is None:
            return
        # If a render is already in flight, the showEvent is a
        # re-fire (e.g. parent layout re-laid out) — do nothing.
        # The in-flight render will populate the pixmap.
        if self._pending_tag is not None:
            return
        if self.width() < self.MIN_WIDTH or self.height() < self.MIN_HEIGHT:
            return
        w = max(self.MIN_WIDTH, self._label.width())
        h = max(self.MIN_HEIGHT, self._label.height())
        if self._min_height > 0:
            h = max(h, self._min_height)
        cached = self._pixmap_cache.get((id(self._fig), w, h))
        if cached is not None and not cached.isNull():
            self._width = w
            self._height = h
            self._fig_id = id(self._fig)
            self._label.setPixmap(cached)
            # Cache hit at show-time must also notify the owner so
            # the loading overlay counts it.
            self._notify_owner()
            return
        if not self._label.pixmap():
            self._queue_render()

    def minimumSizeHint(self) -> QSize:
        return QSize(self.MIN_WIDTH, max(self.MIN_HEIGHT, self._min_height))

    def sizeHint(self) -> QSize:
        return QSize(self._width, max(self._height, self._min_height))
