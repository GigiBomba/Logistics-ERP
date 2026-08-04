"""Startup benchmark for Operion ERP.

Measures startup wall-clock time in phases, reports structured results.

Usage:
    python scripts/bench_startup.py                  # remote mode (main_remote.py)
    python scripts/bench_startup.py --local          # local mode (main.py)
    python scripts/bench_startup.py --runs 5         # 5 iterations
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("bench_startup")

# Suppress app logging during benchmark
os.environ.setdefault("OPERION_DIAGNOSTICS", "0")
os.environ.setdefault("OPERION_ENV", "development")
os.environ.setdefault("OPERION_PERF_LOG", "1")
os.environ.setdefault("OPERION_DB", "test_group1.db")

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


@dataclass
class StartupPhase:
    name: str
    elapsed_ms: float


@dataclass
class StartupResult:
    iteration: int
    total_ms: float
    phases: list[StartupPhase] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "total_ms": round(self.total_ms, 1),
            "phases": [{"name": p.name, "elapsed_ms": round(p.elapsed_ms, 1)} for p in self.phases],
            "error": self.error,
        }


def run_local(iteration: int) -> StartupResult:
    """Benchmark startup via main.py (local DB mode).

    Uses subprocess because QApplication is a singleton — only one
    instance can exist per process.
    """
    import subprocess as _sp
    import json as _json

    project_root = Path(__file__).parent.parent
    _python = sys.executable
    _bench_script = project_root / "scripts" / "_bench_local_runner.py"

    # Create the runner script if it doesn't exist
    if not _bench_script.exists():
        _bench_script.write_text(r'''"""Internal: run main.py and output JSON timing."""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["OPERION_DIAGNOSTICS"] = "0"
from main import run_app
from PySide6.QtCore import QCoreApplication

start = time.perf_counter()
app, window = run_app(return_window=True)
t_ready = time.perf_counter()
for _ in range(10):
    QCoreApplication.processEvents()
    time.sleep(0.01)
t_painted = time.perf_counter()

result = {
    "app_ready_ms": round((t_ready - start) * 1000, 1),
    "first_paint_ms": round((t_painted - start) * 1000, 1),
    "total_ms": round((time.perf_counter() - start) * 1000, 1),
}
print(json.dumps(result))
window.close()
app.quit()
''')

    env = os.environ.copy()
    env.update({"OPERION_DIAGNOSTICS": "0", "PYTHONUNBUFFERED": "1"})
    t0 = time.perf_counter()
    try:
        proc = _sp.run(
            [_python, str(_bench_script)],
            capture_output=True, text=True, timeout=60, env=env,
        )
        total_wall = (time.perf_counter() - t0) * 1000
    except _sp.TimeoutExpired:
        return StartupResult(iteration=iteration, total_ms=60000, error="timeout")

    if proc.returncode != 0:
        return StartupResult(iteration=iteration, total_ms=total_wall,
                             error=proc.stderr[-300:] or "non-zero exit")

    # Find the LAST line starting with '{' — that's our JSON result
    import re as _re
    json_line = None
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            json_line = line
            break
    if not json_line:
        return StartupResult(iteration=iteration, total_ms=total_wall,
                             error="no JSON line in output:\n" + proc.stdout[-300:])
    try:
        data = _json.loads(json_line)
    except _json.JSONDecodeError as e:
        return StartupResult(iteration=iteration, total_ms=total_wall,
                             error=f"JSON parse: {e}\nline={json_line[:200]}")

    phases = [
        StartupPhase("app_ready", data.get("app_ready_ms", 0)),
        StartupPhase("first_paint", data.get("first_paint_ms", 0)),
        StartupPhase("total", data.get("total_ms", total_wall)),
    ]
    return StartupResult(iteration=iteration, total_ms=data.get("total_ms", total_wall), phases=phases)


def run_remote(iteration: int) -> StartupResult:
    """Benchmark startup via main_remote.py subprocess (remote client mode).

    Runs the real entry point as a subprocess with a 30s timeout,
    parses startup log lines for phase markers.
    """
    import subprocess as _sp

    project_root = Path(__file__).parent.parent
    _python = sys.executable
    env = os.environ.copy()
    env.update({
        "OPERION_DIAGNOSTICS": "0",
        "OPERION_ENV": "development",
        "OPERION_PERF_LOG": "1",
        "PYTHONUNBUFFERED": "1",
    })

    t0 = time.perf_counter()
    try:
        proc = _sp.run(
            [_python, str(project_root / "main_remote.py")],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        total_ms = (time.perf_counter() - t0) * 1000
    except _sp.TimeoutExpired:
        return StartupResult(iteration=iteration, total_ms=30000,
                             error="timeout (30s)")
    except Exception as e:
        return StartupResult(iteration=iteration, total_ms=0, error=str(e))

    # Parse output for startup markers
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    phases: list[StartupPhase] = []

    # Extract startup_ms from the JSON log line
    import re
    m = re.search(r'"startup_ms":\s*(\d+)', stdout)
    if m:
        phases.append(StartupPhase("app_startup_logged", float(m.group(1))))

    # Look for "PySide6 remote application started"
    if "PySide6 remote application started" in stdout:
        phases.append(StartupPhase("window_shown", total_ms))
    else:
        # Check for errors
        if "FATAL STARTUP ERROR" in stdout or "FATAL STARTUP ERROR" in stderr:
            error_text = stdout[-500:] + stderr[-500:]
            phases.append(StartupPhase("error", total_ms))
            return StartupResult(iteration=iteration, total_ms=total_ms,
                                 phases=phases, error=error_text[:200])

    phases.append(StartupPhase("total", total_ms))

    return StartupResult(iteration=iteration, total_ms=total_ms, phases=phases)


def run_benchmark(mode: str, runs: int) -> list[StartupResult]:
    """Run *runs* iterations of the startup benchmark."""
    results: list[StartupResult] = []

    for i in range(runs):
        logger.info("Iteration %d/%d (%s mode)…", i + 1, runs, mode)
        if mode == "local":
            r = run_local(i + 1)
        else:
            r = run_remote(i + 1)
        results.append(r)

        if r.error:
            logger.warning("  Iteration %d failed: %s", i + 1, r.error)
        else:
            phases_detail = " | ".join(
                f"{p.name}={p.elapsed_ms:.0f}ms" for p in r.phases
            )
            logger.info("  Total: %.0fms | %s", r.total_ms, phases_detail)

        # Cooldown between runs
        if i < runs - 1:
            time.sleep(2)

    return results


def generate_report(results: list[StartupResult], mode: str) -> str:
    """Generate structured startup benchmark report."""
    successful = [r for r in results if not r.error]

    if not successful:
        report_data = {
            "mode": mode,
            "iterations": len(results),
            "all_failed": True,
            "results": [r.to_dict() for r in results],
        }
    else:
        # Stats per phase across successful runs
        all_phases: dict[str, list[float]] = {}
        for r in successful:
            for p in r.phases:
                all_phases.setdefault(p.name, []).append(p.elapsed_ms)

        phase_stats = {}
        for name, times in sorted(all_phases.items()):
            times_sorted = sorted(times)
            n = len(times_sorted)
            phase_stats[name] = {
                "min_ms": round(min(times), 1),
                "max_ms": round(max(times), 1),
                "avg_ms": round(sum(times) / n, 1),
                "median_ms": round(times_sorted[n // 2], 1),
            }

        totals = [r.total_ms for r in successful]
        totals_sorted = sorted(totals)
        n = len(totals_sorted)

        report_data = {
            "mode": mode,
            "iterations": len(results),
            "successful": len(successful),
            "phase_stats": phase_stats,
            "overall": {
                "min_ms": round(min(totals), 1),
                "max_ms": round(max(totals), 1),
                "avg_ms": round(sum(totals) / n, 1),
                "median_ms": round(totals_sorted[n // 2], 1),
            },
            "results": [r.to_dict() for r in results],
        }

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"startup_bench_{mode}_{timestamp}.json"
    path = REPORTS_DIR / filename
    with open(path, "w") as f:
        json.dump(report_data, f, indent=2)

    # Generate markdown summary too
    md_path = REPORTS_DIR / f"startup_bench_{mode}_{timestamp}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Startup Benchmark — {mode} mode\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Iterations:** {len(results)} ({len(successful)} successful)  \n\n")

        if not successful:
            f.write("*All iterations failed.*\n")
        else:
            f.write("## Phase Timing (ms)\n\n")
            f.write("| Phase | Avg | Min | Max | Median |\n")
            f.write("|-------|-----|-----|-----|--------|\n")
            for name, stats in sorted(phase_stats.items()):
                f.write(f"| {name} | {stats['avg_ms']:.0f} | {stats['min_ms']:.0f} | {stats['max_ms']:.0f} | {stats['median_ms']:.0f} |\n")

            f.write("\n## Overall\n\n")
            o = report_data["overall"]
            f.write(f"| Metric | Value |\n|--------|-------|\n")
            f.write(f"| Avg | {o['avg_ms']:.0f} ms |\n")
            f.write(f"| Min | {o['min_ms']:.0f} ms |\n")
            f.write(f"| Max | {o['max_ms']:.0f} ms |\n")
            f.write(f"| Median | {o['median_ms']:.0f} ms |\n\n")

            f.write("## Per-Iteration Results\n\n")
            for r in results:
                status = "✅" if not r.error else f"❌ {r.error}"
                phases_str = " → ".join(f"{p.name}={p.elapsed_ms:.0f}ms" for p in r.phases)
                f.write(f"- Iteration {r.iteration}: **{r.total_ms:.0f}ms** {status}\n")
                if r.phases:
                    f.write(f"  {phases_str}\n")

    logger.info("Report saved: %s", path)
    logger.info("Summary: %s", md_path)

    # Print console summary
    if successful:
        print(f"\n{'='*60}")
        print(f"STARTUP BENCHMARK — {mode.upper()} MODE")
        print(f"{'='*60}")
        print(f"  Iterations: {len(results)} ({len(successful)} successful)")
        print(f"\n  Phase Timing (ms):")
        for name, stats in sorted(phase_stats.items()):
            print(f"    {name:20s}  avg={stats['avg_ms']:>7.0f}  min={stats['min_ms']:>7.0f}  max={stats['max_ms']:>7.0f}")
        print(f"\n  Overall:")
        print(f"    Avg:    {report_data['overall']['avg_ms']:>7.0f} ms")
        print(f"    Min:    {report_data['overall']['min_ms']:>7.0f} ms")
        print(f"    Max:    {report_data['overall']['max_ms']:>7.0f} ms")
        print(f"    Median: {report_data['overall']['median_ms']:>7.0f} ms")
        print(f"{'='*60}\n")

    return str(path)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Operion startup benchmark")
    parser.add_argument("--local", action="store_true", help="Use local main.py mode (default: remote)")
    parser.add_argument("--runs", type=int, default=3, help="Number of iterations (default: 3)")
    args = parser.parse_args()

    mode = "local" if args.local else "remote"
    results = run_benchmark(mode, args.runs)
    generate_report(results, mode)

    # Exit with error if any run failed
    if any(r.error for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
