"""View Lifecycle Probe — instrument every BaseView lifecycle phase.

Monkey-patches ``ui.base_view.BaseView`` to record timing for:

- Construction (``__init__``)
- UI building (``_build_ui``)
- Activation (``wakeup``)
- Shutdown (``shutdown``)
- Qt events (``closeEvent``, ``resizeEvent``)
- Data loading (``_load_data_async``, ``_load_data``)

Detection events
----------------
- ``view.{class}.resize_storm`` — > 5 resizeEvents within 100 ms
- ``view.{class}.orphaned`` — view created but ``shutdown()`` never called
- ``view.{class}.slow_wakeup`` — wakeup > 500 ms
- ``view.{class}.slow_build`` — ``_build_ui`` > 200 ms
- ``view.{class}.lifetime`` — emitted on shutdown with total lifetime
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from typing import Any

from diagnostics.models import DiagnosticCategory, Event
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.view_lifecycle")

# ── Thresholds ──────────────────────────────────────────────────────────
RESIZE_STORM_THRESHOLD = 5       # number of resizes
RESIZE_STORM_WINDOW_MS = 100     # time window in ms
SLOW_WAKEUP_MS = 500             # ms
SLOW_BUILD_MS = 200              # ms
ORPHAN_TIMEOUT_S = 300           # seconds


class ViewLifecycleProbe:
    """Instruments every BaseView lifecycle phase.

    Must be installed **before** any BaseView instances are created.
    """

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._originals: dict[str, Any] = {}
        self._installed = False
        self._lock = threading.Lock()

        # Active view tracking:  id(view) -> info dict
        self._active_views: dict[int, dict] = {}
        self._view_init_counts: dict[str, int] = {}

    # ── Install / Uninstall ──────────────────────────────────────────

    def install(self) -> None:
        """Monkey-patch all BaseView lifecycle methods."""
        if self._installed:
            return

        from ui.base_view import BaseView

        self._originals.clear()
        probe = self           # captured in closures below
        store = self.store

        # ═══════════════════════════════════════════════════════════════
        #  __init__
        # ═══════════════════════════════════════════════════════════════
        _orig_init = BaseView.__init__

        @functools.wraps(_orig_init)
        def _wrapped_init(self, *args: Any, **kwargs: Any) -> Any:
            view_id = id(self)
            cls_name = type(self).__name__
            now = time.perf_counter()

            # Track active view
            with probe._lock:
                probe._active_views[view_id] = {
                    "class": cls_name,
                    "created_at": now,
                    "shutdown_at": None,
                }
                probe._view_init_counts[cls_name] = (
                    probe._view_init_counts.get(cls_name, 0) + 1
                )

            # Guard — skip instrumentation when disabled
            if getattr(self, "_diagnostics_disabled", False):
                return _orig_init(self, *args, **kwargs)

            # Time the constructor
            span = store.begin_span(
                f"view.{cls_name}.__init__",
                category=DiagnosticCategory.VIEW,
                metadata={"class": cls_name},
            )
            try:
                result = _orig_init(self, *args, **kwargs)
                self._diag_init_span = span.span_id  # type: ignore[attr-defined]
                return result
            finally:
                store.end_span(span)

        self._originals["__init__"] = _orig_init
        BaseView.__init__ = _wrapped_init

        # ═══════════════════════════════════════════════════════════════
        #  _build_ui
        # ═══════════════════════════════════════════════════════════════
        _orig_build_ui = BaseView._build_ui

        @functools.wraps(_orig_build_ui)
        def _wrapped_build_ui(self, *args: Any, **kwargs: Any) -> Any:
            if getattr(self, "_diagnostics_disabled", False):
                return _orig_build_ui(self, *args, **kwargs)
            cls_name = type(self).__name__
            span = store.begin_span(
                f"view.{cls_name}._build_ui",
                category=DiagnosticCategory.VIEW,
                metadata={"class": cls_name},
            )
            try:
                return _orig_build_ui(self, *args, **kwargs)
            finally:
                elapsed = span.elapsed_ms
                store.end_span(span)
                if elapsed > SLOW_BUILD_MS:
                    store.record_event(Event(
                        name=f"view.{cls_name}.slow_build",
                        category=DiagnosticCategory.VIEW,
                        metadata={
                            "class": cls_name,
                            "elapsed_ms": round(elapsed, 1),
                            "threshold_ms": SLOW_BUILD_MS,
                        },
                    ))

        self._originals["_build_ui"] = _orig_build_ui
        BaseView._build_ui = _wrapped_build_ui

        # ═══════════════════════════════════════════════════════════════
        #  wakeup
        # ═══════════════════════════════════════════════════════════════
        _orig_wakeup = BaseView.wakeup

        @functools.wraps(_orig_wakeup)
        def _wrapped_wakeup(self, *args: Any, **kwargs: Any) -> Any:
            if getattr(self, "_diagnostics_disabled", False):
                return _orig_wakeup(self, *args, **kwargs)
            cls_name = type(self).__name__
            span = store.begin_span(
                f"view.{cls_name}.wakeup",
                category=DiagnosticCategory.VIEW,
                metadata={"class": cls_name},
            )
            try:
                return _orig_wakeup(self, *args, **kwargs)
            finally:
                elapsed = span.elapsed_ms
                store.end_span(span)
                if elapsed > SLOW_WAKEUP_MS:
                    store.record_event(Event(
                        name=f"view.{cls_name}.slow_wakeup",
                        category=DiagnosticCategory.VIEW,
                        metadata={
                            "class": cls_name,
                            "elapsed_ms": round(elapsed, 1),
                            "threshold_ms": SLOW_WAKEUP_MS,
                        },
                    ))

        self._originals["wakeup"] = _orig_wakeup
        BaseView.wakeup = _wrapped_wakeup

        # ═══════════════════════════════════════════════════════════════
        #  shutdown
        # ═══════════════════════════════════════════════════════════════
        _orig_shutdown = BaseView.shutdown

        @functools.wraps(_orig_shutdown)
        def _wrapped_shutdown(self, *args: Any, **kwargs: Any) -> Any:
            if getattr(self, "_diagnostics_disabled", False):
                return _orig_shutdown(self, *args, **kwargs)
            cls_name = type(self).__name__
            span = store.begin_span(
                f"view.{cls_name}.shutdown",
                category=DiagnosticCategory.VIEW,
                metadata={"class": cls_name},
            )
            try:
                return _orig_shutdown(self, *args, **kwargs)
            finally:
                store.end_span(span)
                # Record total lifetime
                view_id = id(self)
                with probe._lock:
                    info = probe._active_views.get(view_id)
                    if info is not None and info.get("shutdown_at") is None:
                        info["shutdown_at"] = time.perf_counter()
                        lifetime_s = info["shutdown_at"] - info["created_at"]
                        store.record_event(Event(
                            name=f"view.{cls_name}.lifetime",
                            category=DiagnosticCategory.VIEW,
                            metadata={
                                "class": cls_name,
                                "lifetime_s": round(lifetime_s, 2),
                                "created_at": info["created_at"],
                            },
                        ))

        self._originals["shutdown"] = _orig_shutdown
        BaseView.shutdown = _wrapped_shutdown

        # ═══════════════════════════════════════════════════════════════
        #  closeEvent
        # ═══════════════════════════════════════════════════════════════
        _orig_close = BaseView.closeEvent

        @functools.wraps(_orig_close)
        def _wrapped_closeEvent(self, event: Any, *args: Any, **kwargs: Any) -> Any:
            if getattr(self, "_diagnostics_disabled", False):
                return _orig_close(self, event, *args, **kwargs)
            cls_name = type(self).__name__
            span = store.begin_span(
                f"view.{cls_name}.closeEvent",
                category=DiagnosticCategory.VIEW,
                metadata={"class": cls_name},
            )
            try:
                return _orig_close(self, event, *args, **kwargs)
            finally:
                store.end_span(span)

        self._originals["closeEvent"] = _orig_close
        BaseView.closeEvent = _wrapped_closeEvent

        # ═══════════════════════════════════════════════════════════════
        #  resizeEvent — also detects resize storms
        # ═══════════════════════════════════════════════════════════════
        _orig_resize = BaseView.resizeEvent

        @functools.wraps(_orig_resize)
        def _wrapped_resizeEvent(self, event: Any, *args: Any, **kwargs: Any) -> Any:
            if getattr(self, "_diagnostics_disabled", False):
                return _orig_resize(self, event, *args, **kwargs)
            cls_name = type(self).__name__
            now = time.perf_counter()

            # ── Resize storm detection ──
            view_id = id(self)
            with probe._lock:
                info = probe._active_views.get(view_id)
                if info is not None:
                    resize_times: list[float] = info.setdefault("resize_times", [])
                    resize_times.append(now)
                    # Keep only those within the storm window
                    window_start = now - (RESIZE_STORM_WINDOW_MS / 1000.0)
                    info["resize_times"] = [t for t in resize_times if t > window_start]

                    if (
                        len(info["resize_times"]) > RESIZE_STORM_THRESHOLD
                        and not info.get("resize_storm_warned")
                    ):
                        info["resize_storm_warned"] = True
                        store.record_event(Event(
                            name=f"view.{cls_name}.resize_storm",
                            category=DiagnosticCategory.VIEW,
                            metadata={
                                "class": cls_name,
                                "count": len(info["resize_times"]),
                                "window_ms": RESIZE_STORM_WINDOW_MS,
                            },
                        ))

            # ── Time the resize ──
            span = store.begin_span(
                f"view.{cls_name}.resizeEvent",
                category=DiagnosticCategory.VIEW,
                metadata={"class": cls_name},
            )
            try:
                return _orig_resize(self, event, *args, **kwargs)
            finally:
                store.end_span(span)

        self._originals["resizeEvent"] = _orig_resize
        BaseView.resizeEvent = _wrapped_resizeEvent

        # ═══════════════════════════════════════════════════════════════
        #  _load_data_async
        # ═══════════════════════════════════════════════════════════════
        _orig_load_async = BaseView._load_data_async

        @functools.wraps(_orig_load_async)
        def _wrapped_load_data_async(self, *args: Any, **kwargs: Any) -> Any:
            if getattr(self, "_diagnostics_disabled", False):
                return _orig_load_async(self, *args, **kwargs)
            cls_name = type(self).__name__
            span = store.begin_span(
                f"view.{cls_name}._load_data_async",
                category=DiagnosticCategory.VIEW,
                metadata={"class": cls_name},
            )
            try:
                return _orig_load_async(self, *args, **kwargs)
            finally:
                store.end_span(span)

        self._originals["_load_data_async"] = _orig_load_async
        BaseView._load_data_async = _wrapped_load_data_async

        # ═══════════════════════════════════════════════════════════════
        #  _load_data
        # ═══════════════════════════════════════════════════════════════
        _orig_load = BaseView._load_data

        @functools.wraps(_orig_load)
        def _wrapped_load_data(self, *args: Any, **kwargs: Any) -> Any:
            if getattr(self, "_diagnostics_disabled", False):
                return _orig_load(self, *args, **kwargs)
            cls_name = type(self).__name__
            span = store.begin_span(
                f"view.{cls_name}._load_data",
                category=DiagnosticCategory.VIEW,
                metadata={"class": cls_name},
            )
            try:
                return _orig_load(self, *args, **kwargs)
            finally:
                store.end_span(span)

        self._originals["_load_data"] = _orig_load
        BaseView._load_data = _wrapped_load_data

        # ── Re-patch subclasses with overrides ────────────────────
        for subcls in BaseView.__subclasses__():
            self._repatch_subclass(subcls)

        self._installed = True
        logger.info("[DIAG] ViewLifecycleProbe installed")

    # ── Subclass re-patching ──────────────────────────────────────────

    def _repatch_subclass(self, subcls: type) -> None:
        """Re-patch methods on *subcls* if they override a patched base method.

        This catches classes that define their own override without calling
        ``super()``, so their custom logic is still instrumented.
        """
        store = self.store

        for method_name in self._originals:
            if method_name in subcls.__dict__:
                orig_method = subcls.__dict__[method_name]

                @functools.wraps(orig_method)
                def _sub_wrapper(
                    self: Any,
                    *args: Any,
                    _mname: str = method_name,
                    _orig: Any = orig_method,
                    **kwargs: Any,
                ) -> Any:
                    if getattr(self, "_diagnostics_disabled", False):
                        return _orig(self, *args, **kwargs)
                    view_name = type(self).__name__
                    span = store.begin_span(
                        f"view.{view_name}.{_mname}",
                        category=DiagnosticCategory.VIEW,
                        metadata={"class": view_name, "method": _mname},
                    )
                    try:
                        return _orig(self, *args, **kwargs)
                    finally:
                        store.end_span(span)

                setattr(subcls, method_name, _sub_wrapper)

    # ── Uninstall ─────────────────────────────────────────────────────

    def uninstall(self) -> None:
        """Restore all original BaseView methods."""
        if not self._installed:
            return

        from ui.base_view import BaseView

        for method_name, original in self._originals.items():
            try:
                setattr(BaseView, method_name, original)
            except Exception:
                logger.exception(
                    "[DIAG] Failed to restore %s on BaseView", method_name
                )
        self._originals.clear()
        self._installed = False
        logger.info("[DIAG] ViewLifecycleProbe uninstalled")

    # ── Sampling ──────────────────────────────────────────────────────

    def sample(self) -> None:
        """Periodic check for orphaned views and gauge updates.

        Called by the ``DiagnosticsEngine`` sampler loop every ~2 s.
        """
        now = time.perf_counter()

        with self._lock:
            # ── Orphan detection ─────────────────────────────────
            for view_id, info in list(self._active_views.items()):
                age_s = now - info["created_at"]
                if info.get("shutdown_at") is None and age_s > ORPHAN_TIMEOUT_S:
                    if not info.get("orphan_warned"):
                        info["orphan_warned"] = True
                        cls_name = info["class"]
                        self.store.record_event(Event(
                            name=f"view.{cls_name}.orphaned",
                            category=DiagnosticCategory.VIEW,
                            metadata={
                                "class": cls_name,
                                "age_s": round(age_s, 1),
                                "created_at": info["created_at"],
                            },
                        ))

                # ── Reset resize storm flag when calm ────────────
                if info.get("resize_storm_warned"):
                    resize_times: list[float] = info.get("resize_times", [])
                    window_start = now - (RESIZE_STORM_WINDOW_MS / 1000.0)
                    recent = [t for t in resize_times if t > window_start]
                    if len(recent) <= RESIZE_STORM_THRESHOLD:
                        info["resize_storm_warned"] = False

            # ── Active view count ────────────────────────────────
            active_count = sum(
                1 for info in self._active_views.values()
                if info.get("shutdown_at") is None
            )

        self.store.set_gauge("view.active_count", active_count)

        with self._lock:
            for cls_name, count in self._view_init_counts.items():
                self.store.set_gauge(
                    f"view.init_count.{cls_name}",
                    float(count),
                    labels={"class": cls_name},
                )
