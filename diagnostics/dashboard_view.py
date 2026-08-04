"""Real-time diagnostics dashboard widget.

A standalone QWidget that reads from DiagnosticStore and displays live
metrics — FPS, widget count, memory, worker pool, slow operations, and
freeze events.  It refreshes on a QTimer and can be embedded as a view
or opened as a standalone window.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
)

from diagnostics import get_store
from diagnostics.store import DiagnosticStore


class DiagnosticsDashboardView(QWidget):
    """Live runtime diagnostics dashboard.

    Reads from a DiagnosticStore (or the global singleton) and updates
    metric cards and tables every REFRESH_MS milliseconds.
    """

    REFRESH_MS = 500

    def __init__(self, parent: QWidget | None = None, store: DiagnosticStore | None = None):
        super().__init__(parent)
        self._store = store or get_store()
        self._card_values: dict[str, QLabel] = {}
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(self.REFRESH_MS)
        self.setWindowTitle("Runtime Diagnostics")
        self.resize(900, 700)

    # ── UI construction ─────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Title
        title = QLabel("\U0001f9ec Runtime Diagnostics Dashboard")
        title.setProperty("role", "heading")
        layout.addWidget(title)

        # Top row: 4 metric cards in a grid
        cards_grid = QHBoxLayout()
        self._card_fps = self._make_card("FPS", "\u2014", "green")
        self._card_widgets = self._make_card("Widgets", "\u2014", "blue")
        self._card_memory = self._make_card("Memory", "\u2014", "purple")
        self._card_workers = self._make_card("Workers", "\u2014", "orange")
        cards_grid.addWidget(self._card_fps)
        cards_grid.addWidget(self._card_widgets)
        cards_grid.addWidget(self._card_memory)
        cards_grid.addWidget(self._card_workers)
        layout.addLayout(cards_grid)

        # Second row: key stats
        stats_grid = QHBoxLayout()
        self._card_frametime = self._make_card("Frame Time", "\u2014", "teal")
        self._card_timers = self._make_card("Active Timers", "\u2014", "brown")
        self._card_db = self._make_card("DB Queries", "\u2014", "navy")
        self._card_signals = self._make_card("Signal Rate", "\u2014", "maroon")
        stats_grid.addWidget(self._card_frametime)
        stats_grid.addWidget(self._card_timers)
        stats_grid.addWidget(self._card_db)
        stats_grid.addWidget(self._card_signals)
        layout.addLayout(stats_grid)

        # Slowest operations
        layout.addWidget(QLabel("Top 10 Slowest Operations"))
        self._slow_text = QLabel("(collecting data\u2026)")
        self._slow_text.setWordWrap(True)
        self._slow_text.setStyleSheet(
            "background: #1a1a2e; color: #e0e0e0; padding: 8px; font-family: monospace;"
        )
        layout.addWidget(self._slow_text, stretch=1)

        # Freeze events
        layout.addWidget(QLabel("Recent Freeze Events"))
        self._freeze_text = QLabel("(no freezes detected)")
        self._freeze_text.setWordWrap(True)
        self._freeze_text.setStyleSheet(
            "background: #2e1a1a; color: #ff8888; padding: 8px; font-family: monospace;"
        )
        layout.addWidget(self._freeze_text)

    def _make_card(self, title: str, value: str, color: str) -> QFrame:
        """Build a coloured metric card with title + large value label."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)  # type: ignore[attr-defined]
        frame.setStyleSheet(
            f"QFrame {{ background: {color}; border-radius: 8px; padding: 12px; }}"
        )
        frame.setMinimumSize(160, 80)
        fl = QVBoxLayout(frame)
        fl.setSpacing(4)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: white; font-size: 11px; font-weight: bold;")
        lbl_title.setAlignment(Qt.AlignCenter)
        self._card_values[title] = QLabel(value)
        self._card_values[title].setStyleSheet(
            "color: white; font-size: 24px; font-weight: bold;"
        )
        self._card_values[title].setAlignment(Qt.AlignCenter)
        fl.addWidget(lbl_title)
        fl.addWidget(self._card_values[title])
        return frame

    # ── Data refresh ────────────────────────────────────────────────

    def _refresh(self) -> None:
        """Read from store and update all display elements."""
        gauges = self._store.get_all_gauges()
        counters = self._store.get_all_counters()

        # FPS
        latest_fps = self._get_latest(gauges, "event_loop.fps", "0")
        self._card_values["FPS"].setText(f"{latest_fps}")

        # Widgets
        latest_widgets = self._get_latest(gauges, "widget.alive_count", "0")
        self._card_values["Widgets"].setText(f"{latest_widgets}")

        # Memory
        latest_rss = self._get_latest(gauges, "memory.rss_mb", "0")
        self._card_values["Memory"].setText(f"{latest_rss} MB")

        # Workers
        active_workers = self._get_latest(gauges, "workerpool.active_threads", "0")
        self._card_values["Workers"].setText(f"{active_workers} active")

        # Frame time
        latest_ft = self._get_latest(gauges, "event_loop.frame_time_ms", "0")
        self._card_values["Frame Time"].setText(f"{latest_ft} ms")

        # Active timers
        active_timers = self._get_latest(gauges, "timer.active_count", "0")
        self._card_values["Active Timers"].setText(f"{active_timers}")

        # DB Queries
        db_total = counters.get("db.queries_total", 0)
        self._card_values["DB Queries"].setText(f"{db_total}")

        # Signal rate (use a sample counter)
        sig_rate = counters.get("signal.emit_total", 0)
        self._card_values["Signal Rate"].setText(f"{sig_rate}")

        # Slow operations
        slow_spans = self._store.get_slowest_spans(10)
        if slow_spans:
            lines = []
            for i, s in enumerate(slow_spans, 1):
                lines.append(f"{i:2d}. {s.name:<50s} {s.elapsed_ms:>10.1f}ms")
            self._slow_text.setText("\n".join(lines))
        else:
            self._slow_text.setText("(no data yet)")

        # Freeze events
        freezes = self._store.get_freeze_reports()
        if freezes:
            lines = []
            for f in freezes[-5:]:  # Last 5
                ts = time.strftime("%H:%M:%S", time.localtime(f.timestamp))
                stack_line = (
                    f.stack_trace.split("\n")[0] if f.stack_trace else "?"
                )
                lines.append(
                    f"\U0001f4db {ts} \u2014 {f.duration_ms:.0f}ms \u2014 {stack_line[:80]}"
                )
            self._freeze_text.setText("\n".join(lines))
        else:
            self._freeze_text.setText("(no freezes detected)")

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _get_latest(
        gauges: dict[str, list], name: str, default: str = "\u2014"
    ) -> str:
        """Return the latest value for a gauge series as a string."""
        history = gauges.get(name, [])
        if not history:
            return default
        entry = history[-1]
        if isinstance(entry, dict):
            val = entry.get("value", default)
            return f"{val:.1f}" if isinstance(val, float) else str(val)
        return str(entry)

    # ── Lifecycle ───────────────────────────────────────────────────

    def closeEvent(self, event):  # type: ignore[no-untyped-def]
        self._timer.stop()
        super().closeEvent(event)
