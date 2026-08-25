"""Final verification script for the Runtime Diagnostics Framework.
Run: python diagnostics/_verify.py
"""
from __future__ import annotations

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

errors = []

def check(cond, msg):
    if not cond:
        errors.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  OK: {msg}")

# ── 1. Core types ──────────────────────────────────────────────────
from diagnostics.models import DiagnosticCategory, Span, Event, Gauge, Counter, FreezeReport
check(True, "models.py imports")

# ── 2. Store ───────────────────────────────────────────────────────
from diagnostics.store import DiagnosticStore
store = DiagnosticStore()
s = Span("test.op", category=DiagnosticCategory.CUSTOM)
store.end_span(s)
store.increment("test.counter", 5)
store.set_gauge("test.gauge", 42.0)
store.record_event(Event("test.event", category=DiagnosticCategory.CUSTOM))

check(len(store.get_all_spans()) == 1, "store.record_span")
check(store.get_counter("test.counter") == 5, "store.increment/get_counter")
g = store.get_latest_gauge("test.gauge")
check(g is not None and g.value == 42.0, "store.set_gauge/get_latest_gauge")
check(len(store.get_all_events()) == 1, "store.record_event")

snap = store.snapshot()
check(snap["span_count"] == 1, "snapshot span_count")
check(snap["event_count"] == 1, "snapshot event_count")
check(snap["counter_snapshot"]["test.counter"] == 5, "snapshot counters")
check("custom" in snap["category_summary"], "snapshot category_summary")

# Slowest spans
slow = store.get_slowest_spans(10)
check(len(slow) == 1 and slow[0].name == "test.op", "get_slowest_spans")

# Freeze report
fr = FreezeReport(
    duration_ms=1500.0,
    timestamp=1234567890.0,
    thread_id=1234,
    stack_trace="File main.py, line 42, in run_app",
)
store.record_freeze(fr)
check(len(store.get_freeze_reports()) == 1, "FreezeReport/record_freeze")

# ── 3. Reporter ────────────────────────────────────────────────────
from diagnostics.reporter import ReportGenerator
import tempfile
tmpdir = tempfile.mkdtemp()
reporter = ReportGenerator(store, tmpdir)
path = reporter.generate_all()
check(os.path.exists(path), "ReportGenerator.generate_all creates file")

with open(path, encoding="utf-8") as f:
    content = f.read()

for keyword in ["Runtime Diagnostics Report", "custom", "test.op", "Recommendations",
                 "Category Breakdown", "Executive Summary"]:
    check(keyword in content, f"report contains '{keyword}'")

# ── 4. Non-Qt probe imports ─────────────────────────────────────────
probes_to_test = [
    ("startup_timeline", "StartupProbe"),
    ("view_lifecycle", "ViewLifecycleProbe"),
    ("widget_tracker", "WidgetTrackerProbe"),
    ("timer_diagnostics", "TimerDiagnosticsProbe"),
    ("signal_diagnostics", "SignalDiagnosticsProbe"),
    ("workerpool_diagnostics", "WorkerPoolProbe"),
    ("database_diagnostics", "DatabaseProbe"),
    ("memory_diagnostics", "MemoryProbe"),
    ("paint_diagnostics", "PaintProbe"),
    ("navigation_profiler", "NavigationProbe"),
    ("fullscreen_diagnostics", "FullscreenProbe"),
    ("freeze_detector", "FreezeDetectorProbe"),
    ("eventbus_diagnostics", "EventBusProbe"),
]

for mod_name, cls_name in probes_to_test:
    try:
        mod = __import__(f"diagnostics.{mod_name}", fromlist=[cls_name])
        cls = getattr(mod, cls_name)
        # Instantiate with store
        instance = cls(store)
        check(hasattr(instance, "install"), f"{mod_name}.{cls_name} has install()")
        check(hasattr(instance, "uninstall"), f"{mod_name}.{cls_name} has uninstall()")
        print(f"  OK: {mod_name}.{cls_name} instantiated")
    except Exception as e:
        errors.append(f"{mod_name}.{cls_name}: {e}")
        print(f"  FAIL: {mod_name}.{cls_name}: {e}")

# ── 5. Diagnostics Engine ──────────────────────────────────────────
from diagnostics import DiagnosticsEngine, get_store, install_and_start
engine = DiagnosticsEngine(output_dir=tmpdir)
check(True, "DiagnosticsEngine instantiated")
check(len(engine._probes) == 0, "engine has no probes before install_all")

# Engine methods exist
check(hasattr(engine, "install_all"), "engine.install_all()")
check(hasattr(engine, "start_monitoring"), "engine.start_monitoring()")
check(hasattr(engine, "stop_monitoring"), "engine.stop_monitoring()")
check(hasattr(engine, "shutdown"), "engine.shutdown()")
check(hasattr(engine, "generate_report"), "engine.generate_report()")

# ── Results ─────────────────────────────────────────────────────────
print()
print(f"=== RESULTS: {len(errors)} errors ===")
if errors:
    for e in errors:
        print(f"  • {e}")
    sys.exit(1)
else:
    print("ALL VERIFICATION CHECKS PASSED")
