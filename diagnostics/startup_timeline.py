"""Phase 1 — Startup Timeline Probe.

Records every phase of the application startup sequence from process
launch through to first user interaction.  Monkey-patches ``run_app``
in ``main.py`` to intercept key milestones.

Output:
    startup_timeline.json       — raw span data
    startup_timeline.md         — human-readable timeline
    startup_flamegraph_data.json — Chrome-compatible flame graph events
"""

from __future__ import annotations

import functools
import json
import logging
import os
import time
import threading
from typing import Any, Optional

from diagnostics.models import DiagnosticCategory, Span, Event
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.startup")

# ── Probe ─────────────────────────────────────────────────────────────


class StartupProbe:
    """Instruments the application startup sequence.

    Must be installed BEFORE ``run_app()`` is called.
    """

    def __init__(self, store: DiagnosticStore, output_dir: str = "logs/diagnostics"):
        self.store = store
        self.output_dir = output_dir
        self._original_run_app = None
        self._startup_span: Optional[Span] = None
        self._milestones: dict[str, float] = {}
        self._phase_stack: list[Span] = []
        self._installed = False

    # ── Public API ─────────────────────────────────────────────────

    def mark(self, phase: str, metadata: Optional[dict] = None) -> Span:
        """Record a named startup milestone and begin a span for it.

        Returns the span so callers can ``end_span(span)`` after the
        phase completes.
        """
        parent_id = self._phase_stack[-1].span_id if self._phase_stack else None
        span = self.store.begin_span(
            name=f"startup.{phase}",
            category=DiagnosticCategory.STARTUP,
            parent_id=parent_id,
            metadata={"phase": phase, **(metadata or {})},
        )
        self._milestones[phase] = time.perf_counter()
        self._phase_stack.append(span)

        logger.debug("[STARTUP] %s — begin", phase)
        return span

    def end_mark(self, phase: str, span: Span, metadata: Optional[dict] = None) -> None:
        """Complete a startup milestone span."""
        self.store.end_span(span, metadata=metadata)
        if self._phase_stack and self._phase_stack[-1] is span:
            self._phase_stack.pop()
        elapsed = span.elapsed_ms
        logger.info("[STARTUP] %s — %.1f ms", phase, elapsed)

    def mark_event(self, name: str, metadata: Optional[dict] = None) -> None:
        """Record a point-in-time startup event."""
        self.store.record_event(
            Event(
                name=f"startup.{name}",
                category=DiagnosticCategory.STARTUP,
                metadata={"phase": name, **(metadata or {})},
            )
        )

    def set_milestone(self, name: str, metadata: Optional[dict] = None) -> None:
        """Record a simple named milestone with current timestamp."""
        self._milestones[name] = time.perf_counter()
        self.mark_event(name, metadata)

    # ── Monkey-patch ───────────────────────────────────────────────

    def install(self) -> None:
        if self._installed:
            return

        try:
            import main as main_module
        except ImportError:
            logger.warning("[DIAG] Cannot import main module — startup probe skipped")
            return

        self._original_run_app = main_module.run_app
        original = main_module.run_app

        @functools.wraps(original)
        def instrumented_run_app(return_window=False):
            self._startup_span = self.store.begin_span(
                name="startup.total",
                category=DiagnosticCategory.STARTUP,
                metadata={"phase": "total"},
            )
            self.set_milestone("process_start")

            try:
                result = original(return_window=return_window)
            finally:
                self.store.end_span(self._startup_span)
                total_ms = self._startup_span.elapsed_ms
                logger.info(
                    "[STARTUP] Total startup: %.1f ms (%.2f s)",
                    total_ms, total_ms / 1000.0,
                )
                self._export()
            return result

        main_module.run_app = instrumented_run_app
        self._installed = True
        logger.info("[DIAG] Startup probe installed")

    def uninstall(self) -> None:
        if self._installed and self._original_run_app:
            try:
                import main as main_module
                main_module.run_app = self._original_run_app
            except Exception:
                pass
            self._installed = False

    # ── Export ──────────────────────────────────────────────────────

    def _export(self) -> None:
        """Write startup-specific output files."""
        spans = self.store.get_spans(category=DiagnosticCategory.STARTUP)
        events = [
            e for e in self.store.get_all_events()
            if e.category == DiagnosticCategory.STARTUP
        ]

        # ── Timeline JSON ──────────────────────────────────────────
        data = {
            "total_startup_ms": self._startup_span.elapsed_ms if self._startup_span else 0,
            "milestones": {
                name: ts - (self._milestones.get("process_start", ts))
                for name, ts in self._milestones.items()
            },
            "phases": [s.to_dict() for s in spans],
            "events": [e.to_dict() for e in events],
        }
        out_dir = self.output_dir
        os.makedirs(out_dir, exist_ok=True)

        with open(os.path.join(out_dir, "startup_timeline.json"), "w") as f:
            json.dump(data, f, indent=2, default=str)

        # ── Flame graph data (Chrome-compatible) ───────────────────
        flame_events = []
        for s in spans:
            if s.end_time > 0:
                flame_events.append({
                    "name": s.name,
                    "cat": s.category.value,
                    "ph": "X",  # Complete event
                    "ts": int(s.start_time * 1_000_000),  # microseconds
                    "dur": int(s.elapsed_ms * 1000),       # microseconds
                    "tid": s.thread_id,
                    "pid": os.getpid(),
                    "args": s.metadata,
                })
        with open(os.path.join(out_dir, "startup_flamegraph_data.json"), "w") as f:
            json.dump(flame_events, f, indent=2, default=str)

        # ── Timeline Markdown ──────────────────────────────────────
        lines = [
            "# Startup Timeline\n",
            f"**Total startup:** {data['total_startup_ms']:.1f} ms "
            f"({data['total_startup_ms']/1000:.1f} s)\n",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
            "",
            "## Phase Breakdown\n",
            "| Phase | Elapsed (ms) | % of Total | Thread |",
            "|-------|-------------|-----------|--------|",
        ]
        total = data["total_startup_ms"]
        for s in sorted(spans, key=lambda x: x.start_time):
            pct = (s.elapsed_ms / total * 100) if total > 0 else 0
            lines.append(
                f"| {s.name} | {s.elapsed_ms:.1f} | {pct:.1f}% | {s.thread_name} |"
            )
        lines.append("")
        lines.append("## Milestone Timeline\n")
        base_ts = self._milestones.get("process_start", 0)
        for name, ts in sorted(self._milestones.items(), key=lambda x: x[1]):
            offset_ms = (ts - base_ts) * 1000 if base_ts else 0
            lines.append(f"- **+{offset_ms:.0f}ms** — {name}")

        with open(os.path.join(out_dir, "startup_timeline.md"), "w") as f:
            f.write("\n".join(lines))

        logger.info("[DIAG] Startup timeline exported to %s", out_dir)
