#!/usr/bin/env python3
"""Stall-guarded pytest runner (stdlib only; Windows + POSIX).

Full-suite runs in this repo stall/die at 95-99% (5 observed runs), so a
plain ``pytest`` invocation can hang forever without producing a summary.
This runner streams pytest output to a log file while watching for *output
silence*; when no new output appears for ``--stall-minutes`` (default 20)
it first appends a ``=== STALL STACKS ===`` block (a ``py-spy dump`` of the
pytest process and every live descendant Python process — the decisive
"which thread/test is holding the process open" evidence, captured *before*
anything is killed), then kills the entire process tree, records a
``=== STALL DETECTED ===`` block with timestamps in the log, and exits 2.
py-spy is looked up on ``PATH``/``<python>/Scripts``; when it is missing
the log gets a clear note naming the install command instead.

Usage::

    python scripts/run_pytest_guarded.py                      # full suite
    python scripts/run_pytest_guarded.py --stall-minutes 10
    python scripts/run_pytest_guarded.py -- tests/foo_test.py -q -n 0
    python scripts/run_pytest_guarded.py --serial-files ""     # no serial pass

(Use ``--serial-files=`` with the equals sign on Windows PowerShell, which
drops empty ``""`` arguments before the program ever sees them.)

Everything after ``--`` is passed straight to pytest and *replaces* the
default positional target (``tests/``) when it contains a path; other
default options stay in front so later user options win (``-n 0`` beats the
default ``-n 2``, etc.).  Default pytest args::

    tests/ -q -n 2 --dist=loadscope --timeout=900 --timeout-method=thread

Sharding (pytest-split is installed): add ``--splits N --group G`` after ``--`` for full-coverage sharded runs.

Live failure log
----------------
The runner always loads the ``pytest_live_log`` plugin
(``scripts/pytest_live_log.py``) by putting ``scripts/`` on ``PYTHONPATH``
and passing ``-p pytest_live_log``, and sets ``PYTEST_LIVE_LOG``
(default ``live_failures.log``).  Every failed/errored report is appended to
that file the moment it happens — including from xdist workers — so a run
that dies before its summary still names every ``E`` (setup ERROR) mark.
The file is append-only (never rotated by the runner, so a crashed run's
evidence survives the next one); delete it when you want a clean slate.
Under xdist a record is written twice — once by the worker that produced
the report, once by the controller that forwarded it — the leading ``pid``
tells them apart.

xdist-gated files (serial pass)
-------------------------------
These test files carry a module-level
``skipif(PYTEST_XDIST_WORKER)`` gate and therefore collect/skip under
``-n 2``; run them with ``-n 0`` to get real coverage.  Verified by grepping
``tests/`` for ``PYTEST_XDIST_WORKER``:

* ``tests/a11y/test_a11y_automail_template_editor_dialog.py``  (Qt dialog; gw5 crash run #4, qWaitForWindowExposed stall run #5)
* ``tests/e2e/test_e2e_api_flows.py``                          (worker death run #3, test_e2e_document_not_found stall run #5)
* ``tests/fuzz/test_dialog_fuzz.py``                           (native Qt crash: gw3 died at test_detail_drawer_keyboard_fuzz, run #4)
* ``tests/freight_exchange/test_resilience.py``                (gw1 died at TestPropertyFleetMatcherOrdering.test_similar_city_gets_75, run #4; module-level gate — widened from the original class-level gate)
 * ``tests/ui/test_freight_exchange_connect.py``                (native crash under xdist; Qt/webengine teardown)
 * ``tests/ui/test_freight_exchange_search.py``                 (gw1 died at TestSearchExecution::test_search_calls_api, shard-3e 2026-10-04)
 * ``tests/ui/signals/test_copilot_signals.py``                 (native Qt AV in the overlay fixture at QTest.qWait; gw0 died twice, shard-8 2026-10-07)
 * ``tests/test_route_planner_view.py``                        (gw2 died at TestQtRoutePlannerViewLifecycle::test_shutdown_unsubscribes_event_bus, shard-3e 2026-10-04)
 * ``tests/ui/test_dashboard_view.py``                         (native AV inside QEventLoop.exec: gw0 died at TestConstruction::test_creation, shard-3f 2026-10-04)
 * ``tests/test_network_worker.py``                            (native AV in qtbot.waitSignal: gw0 died at test_error_on_http_404, shard-3g 2026-10-04)
 * ``tests/test_overview.py``                                  (native AV in qtbot.wait: gw1 died at test_chart_container_has_widget, shard-3i 2026-10-04)
 * ``tests/test_api/test_route_demo.py``                        (worker-death gate)
* ``tests/test_api/test_oauth2.py``                            (worker-death gate)
* ``tests/test_api/test_drivers_router.py``                    (TestClient PUT portal hang → worker abort, run #3)
* ``tests/chaos/test_mobile_chaos.py``                         (native abort: create_test_app in pool threads, run #3)
* ``tests/copilot/test_audio_recorder.py``                     (audio-device gate)
* ``tests/test_team_view.py``                                  (worker-death gate)
* ``tests/loadtest/test_load_mobile.py``                       (native Fatal Aborted in run_concurrent)

``--serial-files`` defaults to exactly that list (comma-separated);
``--serial-files ""`` disables the serial pass.  The serial pass runs
``pytest -n 0`` on those files *after* the main run and its outcome is
included in the final report.

Exit codes
----------
* normal completion  -> pytest's return code (main run; if the main run
  passed, a failing serial pass contributes its own non-zero code)
* stall detected     -> 2
* startup failure    -> 3 (pytest could not be launched at all)
* Ctrl-C             -> 130 (process tree killed first)
"""
from __future__ import annotations

import argparse
import datetime
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPTS_DIR)

# Default pytest argv (documented in the module docstring).
DEFAULT_PYTEST_ARGS = [
    "tests/",
    "-q",
    "-n",
    "2",
    "--dist=loadscope",
    "--timeout=900",
    "--timeout-method=thread",
]

# xdist-gated test files: skipped under `-n 2`, run with `-n 0`.
# Verified by grepping tests/ for PYTEST_XDIST_WORKER (2026-09; refreshed
# 2026-10 — every gate is now MODULE-level: per-test / per-class gates were
# converted because siblings in the same file still crashed workers under
# `-n 2`, e.g. tests/ui/test_freight_exchange_connect.py::test_connect_
# success_emits_signal in the shard-3 run despite a per-test gate on its
# sibling).
GATED_FILES = [
    "tests/a11y/test_a11y_automail_template_editor_dialog.py",
    "tests/e2e/test_e2e_api_flows.py",
    "tests/fuzz/test_dialog_fuzz.py",
    "tests/freight_exchange/test_resilience.py",
    "tests/ui/test_freight_exchange_connect.py",
    "tests/ui/test_freight_exchange_search.py",
    "tests/ui/signals/test_copilot_signals.py",
    "tests/ui/test_dashboard_view.py",
    "tests/test_route_planner_view.py",
    "tests/test_network_worker.py",
    "tests/test_overview.py",
    "tests/test_api/test_route_demo.py",
    "tests/test_api/test_oauth2.py",
    "tests/test_api/test_drivers_router.py",
    "tests/chaos/test_mobile_chaos.py",
    "tests/copilot/test_audio_recorder.py",
    "tests/test_team_view.py",
    "tests/loadtest/test_load_mobile.py",
]
GATED_FILES_CSV = ",".join(GATED_FILES)


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _log(fh, text: str) -> None:
    fh.write(text)
    fh.flush()


def _build_env() -> dict:
    """Child env: scripts/ importable + PYTEST_LIVE_LOG set."""
    env = os.environ.copy()
    parts = [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
    if SCRIPTS_DIR not in parts:
        env["PYTHONPATH"] = os.pathsep.join([SCRIPTS_DIR] + parts)
    env.setdefault("PYTEST_LIVE_LOG", "live_failures.log")
    # Write pytest's progress output through the pipe immediately: with a
    # piped stdout Python block-buffers, which would otherwise hide output
    # for long stretches and trip the stall guard during a healthy run.
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _pytest_argv(passthrough: list) -> list:
    """Defaults first, user args last (later CLI options win in pytest)."""
    user = list(passthrough)
    # A user-supplied target path replaces the default `tests/` target;
    # without any positional pytest falls back to ini `testpaths` anyway.
    has_positional = any(not arg.startswith("-") for arg in user)
    has_verbosity = any(
        arg == "-q" or arg.startswith("-q") or arg.startswith("-v")
        for arg in user
    )
    has_live_plugin = any(
        (user[i] == "-p" and user[i + 1] == "pytest_live_log")
        or user[i] == "-p=pytest_live_log"
        for i in range(len(user) - 1)
    ) or "-p pytest_live_log" in user

    cmd = [sys.executable, "-m", "pytest"]
    if not has_live_plugin:
        cmd += ["-p", "pytest_live_log"]
    if not has_positional:
        cmd.append("tests/")
    if not has_verbosity:
        cmd.append("-q")
    cmd += DEFAULT_PYTEST_ARGS[2:]  # -n 2 --dist=loadscope --timeout=... --timeout-method=...
    cmd += user
    return cmd


def _windows_descendants(root_pid: int) -> list:
    """Best-effort: PIDs in the tree rooted at ``root_pid`` (Windows).

    Only used when ``taskkill /T`` could not do the job (root already dead),
    so the sweep can find orphaned children whose ParentProcessId still
    points at the dead root.
    """
    ps = (
        "$root=%d; "
        "$all=@(Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId); "
        "$targets=@($root); "
        "for($i=0; $i -lt 8; $i++){ "
        "$new=@(); "
        "foreach($p in $all){ "
        "if($targets -contains $p.ParentProcessId -and "
        "$targets -notcontains $p.ProcessId){ $new += $p.ProcessId } }; "
        "if($new.Count -eq 0){ break }; $targets += $new }; "
        "$targets | Where-Object { $_ -ne $root }"
    ) % root_pid
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=30,
        ).stdout or ""
    except Exception:
        return []
    pids = []
    for tok in out.replace("\r", " ").split():
        if tok.strip().isdigit():
            pids.append(int(tok))
    return pids


def _find_pyspy() -> list:
    """Locate py-spy as an argv prefix (``["py-spy"]``), or ``[]`` if absent.

    Installed with ``python -m pip install py-spy`` (a console script on
    ``PATH`` on POSIX, ``Scripts\\py-spy.exe`` next to the interpreter on
    Windows).
    """
    exe = shutil.which("py-spy")
    if exe:
        return [exe]
    for name in ("py-spy.exe", "py-spy"):
        cand = os.path.join(os.path.dirname(sys.executable), "Scripts", name)
        if os.path.exists(cand):
            return [cand]
    return []


def _descendant_processes(root_pid: int) -> list:
    """``[(pid, name)]`` for every descendant of ``root_pid`` (both platforms)."""
    pairs = []
    if os.name == "nt":
        ps = (
            "$root=%d; "
            "$all=@(Get-CimInstance Win32_Process | "
            "Select-Object ProcessId,ParentProcessId,Name); "
            "$targets=@($root); "
            "for($i=0; $i -lt 8; $i++){ "
            "$new=@(); "
            "foreach($p in $all){ "
            "if($targets -contains $p.ParentProcessId -and "
            "$targets -notcontains $p.ProcessId){ $new += $p.ProcessId } }; "
            "if($new.Count -eq 0){ break }; $targets += $new }; "
            "foreach($t in $targets){ "
            "if($t -eq $root){ continue }; "
            "$n=($all | Where-Object { $_.ProcessId -eq $t }).Name; "
            "Write-Output (\"{0}|{1}\" -f $t, $n) }"
        ) % root_pid
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, text=True, timeout=30,
            ).stdout or ""
        except Exception:
            return []
        for line in out.replace("\r", "").splitlines():
            pid_s, _, name = line.strip().partition("|")
            if pid_s.isdigit():
                pairs.append((int(pid_s), name.strip()))
        return pairs

    # POSIX: one `ps` snapshot, then walk the ppid tree in-process.
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,comm="],
            capture_output=True, text=True, timeout=30,
        ).stdout or ""
    except Exception:
        return []
    children = {}
    names = {}
    for line in out.splitlines():
        cols = line.split(None, 2)
        if len(cols) < 3:
            continue
        pid, ppid, comm = int(cols[0]), int(cols[1]), cols[2]
        names[pid] = comm
        children.setdefault(ppid, []).append(pid)
    stack, seen = list(children.get(root_pid, [])), set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        pairs.append((pid, names.get(pid, "?")))
        stack.extend(children.get(pid, []))
    return pairs


def _dump_stall_stacks(target_pid: int, fh) -> None:
    """Append ``py-spy dump`` output for the target + descendants to ``fh``.

    Runs on stall detection BEFORE ``_kill_tree`` (after the kill there is
    nothing left to sample).  This is the decisive evidence for *why* the
    run stalled: which worker never exited, which thread blocks interpreter
    shutdown, which test frame is stuck.  Never raises — a failed dump is
    logged as a note so the kill still proceeds.
    """
    _log(fh, "\n=== STALL STACKS ===\n")
    pyspy = _find_pyspy()
    if not pyspy:
        _log(
            fh,
            "py-spy not available — no stacks captured. "
            "Install it with:  python -m pip install py-spy\n"
            "=== END STALL STACKS ===\n",
        )
        return

    procs = [(target_pid, "(target pytest process)")] + _descendant_processes(
        target_pid
    )
    dumped = 0
    for pid, name in procs:
        if pid != target_pid and "python" not in (name or "").lower():
            _log(fh, f"--- pid {pid} ({name or '?'}) skipped (not python) ---\n")
            continue
        _log(fh, f"--- py-spy dump --pid {pid} ({name}) ---\n")
        try:
            res = subprocess.run(
                pyspy + ["dump", "--pid", str(pid)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60,
            )
        except subprocess.TimeoutExpired:
            _log(fh, "  py-spy dump timed out after 60s\n")
            continue
        except Exception as exc:  # pragma: no cover - defensive
            _log(fh, f"  py-spy dump failed: {exc!r}\n")
            continue
        out = ((res.stdout or "") + (res.stderr or "")).strip()
        if res.returncode != 0 and not out:
            _log(fh, f"  py-spy dump exited {res.returncode} (no output)\n")
            continue
        if out:
            _log(fh, out + "\n")
        dumped += 1
    _log(fh, f"=== END STALL STACKS ({dumped} dump(s)) ===\n")


def _kill_tree(pid: int) -> list:
    """Kill ``pid`` and its whole process tree.  Returns human notes."""

    notes = []
    if os.name == "nt":
        rc = None
        try:
            res = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, text=True, timeout=60,
            )
            rc = res.returncode
            detail = (res.stdout + res.stderr).strip().replace("\r", " ")
            notes.append(f"taskkill /F /T /PID {pid} -> exit {rc}: {detail[:300]}")
        except Exception as exc:  # pragma: no cover - defensive
            notes.append(f"taskkill /F /T /PID {pid} failed: {exc!r}")
        if rc not in (0, None):
            # Root already gone -> /T could not walk the tree; sweep orphans.
            for orphan in _windows_descendants(pid):
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(orphan)],
                        capture_output=True, timeout=60,
                    )
                    notes.append(f"orphan sweep killed PID {orphan}")
                except Exception as exc:  # pragma: no cover - defensive
                    notes.append(f"orphan sweep failed for {orphan}: {exc!r}")
    else:
        import signal

        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            notes.append(f"killpg(-{pid}) SIGKILL sent")
        except ProcessLookupError:
            notes.append("process group already gone")
        except Exception as exc:  # pragma: no cover - defensive
            notes.append(f"killpg failed: {exc!r}; trying os.kill()")
            try:
                os.kill(pid, signal.SIGKILL)
                notes.append(f"os.kill({pid}) SIGKILL sent")
            except Exception as exc2:  # pragma: no cover - defensive
                notes.append(f"os.kill failed: {exc2!r}")
    return notes


def _run_monitored(cmd: list, fh, stall_seconds: float, env: dict, label: str):
    """Run ``cmd``, tee output to ``fh``+stdout, guard against silence.

    Returns a tuple:
      ("stall", kill_notes, started, last_output)  -> process tree killed
      ("startup", exc, started, None)             -> could not launch
      ("done", rc, started, tail_lines)           -> process finished
    """
    _log(fh, f"\n=== {label} START {_now()} ===\n$ {' '.join(cmd)}\n")
    kwargs = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    if os.name != "nt":
        kwargs["start_new_session"] = True  # own pgid for killpg()
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except OSError as exc:
        _log(fh, f"STARTUP FAILURE: {exc!r}\n")
        return ("startup", exc, _now(), None)

    started = _now()
    out_q: queue.Queue = queue.Queue()

    def _reader():
        try:
            for line in iter(proc.stdout.readline, ""):
                out_q.put(line)
        except Exception as exc:  # pragma: no cover - defensive
            out_q.put(f"!!! output reader error: {exc!r}\n")
        finally:
            out_q.put(None)

    threading.Thread(target=_reader, daemon=True).start()

    last_activity = time.monotonic()
    last_output = started
    tail: deque = deque(maxlen=12)
    stalled = False

    try:
        while True:
            try:
                item = out_q.get(timeout=0.5)
            except queue.Empty:
                if time.monotonic() - last_activity >= stall_seconds:
                    stalled = True
                    break
                continue
            if item is None:  # stdout EOF -> child side closed the pipe
                break
            last_activity = time.monotonic()
            last_output = _now()
            fh.write(item)
            fh.flush()
            sys.stdout.write(item)
            sys.stdout.flush()
            tail.append(item.rstrip("\r\n"))
    except KeyboardInterrupt:
        notes = _kill_tree(proc.pid)
        _log(fh, f"\n=== INTERRUPTED {_now()} ===\n")
        for note in notes:
            _log(fh, f"  {note}\n")
        proc.wait()
        raise

    if stalled:
        detected = _now()
        block = [
            "",
            "=== STALL DETECTED ===",
            f"run:          {label}",
            f"started:      {started}",
            f"last output:  {last_output}",
            f"detected:     {detected}",
            f"threshold:    {stall_seconds:.1f}s of no new output "
            f"(--stall-minutes {stall_seconds / 60.0:g})",
            f"command:      {' '.join(cmd)}",
            f"target pid:   {proc.pid}",
        ]
        _log(fh, "\n".join(block) + "\n")
        # Capture WHERE each process is stuck while it is still alive —
        # the stacks are worthless once taskkill has reaped the tree.
        try:
            _dump_stall_stacks(proc.pid, fh)
        except Exception as exc:  # pragma: no cover - defensive
            _log(fh, f"stall stack dump failed: {exc!r}\n")
        for note in _kill_tree(proc.pid):
            _log(fh, f"  {note}\n")
        try:
            proc.wait(timeout=30)
        except Exception:  # pragma: no cover - defensive
            _log(fh, "  target did not exit after kill; abandoning wait\n")
        _log(fh, "=== END STALL DETECTED ===\n")
        return ("stall", [], started, last_output)

    rc = proc.wait()
    return ("done", rc, started, list(tail))


def _parse_args(argv: list) -> argparse.Namespace:
    # Everything after the first `--` belongs to pytest untouched.
    if "--" in argv:
        split = argv.index("--")
        our_argv, passthrough = argv[:split], argv[split + 1:]
    else:
        our_argv, passthrough = argv, []

    parser = argparse.ArgumentParser(
        prog="run_pytest_guarded.py",
        description="Run pytest with a stall guard (kill process tree on "
                    "output silence) and a live failure log.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "default --serial-files (xdist-gated files, run with -n 0):\n  "
            + "\n  ".join(GATED_FILES)
        ),
    )
    parser.add_argument(
        "--stall-minutes", type=float, default=20.0,
        help="kill the process tree after this many minutes with no new "
             "pytest output (default: 20)",
    )
    parser.add_argument(
        "--log", default="pytest_guarded.log",
        help="log file receiving the streamed pytest output "
             "(default: pytest_guarded.log)",
    )
    parser.add_argument(
        "--serial-files", default=GATED_FILES_CSV, metavar="CSV",
        help="comma-separated files to re-run serially with -n 0 after the "
             "main run; defaults to the xdist-gated list in the module "
             "docstring; pass '' to disable (--serial-files= under PowerShell)",
    )
    ns = parser.parse_args(our_argv)
    ns.passthrough = passthrough
    return ns


def _serial_argv(files: list) -> list:
    # No extra -q here: the ini addopts already add one, and a second one
    # (-qq) would suppress the `N passed in Xs` summary line the final
    # report wants to quote.
    return [
        sys.executable, "-m", "pytest",
        "-p", "pytest_live_log",
        "-n", "0",
        "--timeout=900",
        "--timeout-method=thread",
    ] + files


_SUMMARY_RE = re.compile(
    r"\b\d+\s+(passed|failed|error|errors|skipped|deselected|xfailed|xpassed|"
    r"warnings?|reruns?)\b|no tests ran"
)


def _extract_summary(lines) -> str:
    """Best-effort pytest outcome line from the tail of a run's output.

    Returns ``""`` when the run printed none (e.g. under ``-qq``, which
    suppresses the summary — the exit code remains authoritative).
    """
    for line in reversed(list(lines or [])):
        if line.strip() and _SUMMARY_RE.search(line):
            return line.strip()
    return ""


def main(argv: list = None) -> int:
    ns = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if ns.stall_minutes <= 0:
        print("--stall-minutes must be > 0", file=sys.stderr)
        return 3
    stall_seconds = ns.stall_minutes * 60.0
    serial_files = [f.strip() for f in (ns.serial_files or "").split(",") if f.strip()]

    env = _build_env()
    main_cmd = _pytest_argv(ns.passthrough)

    try:
        fh = open(ns.log, "a", encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"cannot open log file {ns.log!r}: {exc}", file=sys.stderr)
        return 3

    live_log = env.get("PYTEST_LIVE_LOG", "live_failures.log")
    _log(
        fh,
        f"\n{'=' * 72}\n"
        f"run_pytest_guarded.py started {_now()}\n"
        f"  log file:     {os.path.abspath(ns.log)}\n"
        f"  live log:     {live_log} (PYTEST_LIVE_LOG)\n"
        f"  stall limit:  {ns.stall_minutes:g} min without output\n"
        f"  serial pass:  {serial_files or '(disabled)'}\n"
        f"{'=' * 72}\n",
    )

    try:
        status, payload, started, extra = _run_monitored(
            main_cmd, fh, stall_seconds, env, "MAIN RUN",
        )
    except KeyboardInterrupt:
        fh.close()
        print("\ninterrupted; see log for details", file=sys.stderr)
        return 130

    if status == "startup":
        _log(fh, f"=== FINAL REPORT ===\nmain run: startup failure: {payload!r}\n")
        fh.close()
        print(f"pytest failed to start: {payload!r}", file=sys.stderr)
        return 3
    if status == "stall":
        _log(
            fh,
            f"\n=== FINAL REPORT ===\n{_now()}\n"
            f"main run: STALLED (no output for {stall_seconds:.0f}s) -> "
            f"process tree killed, exiting 2\n",
        )
        fh.close()
        return 2

    main_rc = payload
    main_summary = _extract_summary(extra)
    _log(fh, f"\n=== MAIN RUN FINISHED {_now()} exit={main_rc} ===\n")

    serial_rc = None
    serial_summary = ""
    if serial_files:
        s_status, s_payload, s_started, s_extra = _run_monitored(
            _serial_argv(serial_files), fh, stall_seconds, env, "SERIAL PASS (-n 0)",
        )
        if s_status == "startup":
            serial_rc, serial_summary = None, f"startup failure: {s_payload!r}"
        elif s_status == "stall":
            _log(
                fh,
                f"\n=== FINAL REPORT ===\n{_now()}\n"
                f"main run:   exit {main_rc}\n"
                f"serial pass: STALLED -> process tree killed, exiting 2\n",
            )
            fh.close()
            return 2
        else:
            serial_rc = s_payload
            serial_summary = _extract_summary(s_extra) or "(no outcome line)"

    # Live failure log stats (best effort).
    live_note = ""
    try:
        with open(live_log, "r", encoding="utf-8", errors="replace") as lf:
            live_note = f"{sum(1 for _ in lf)} record(s)"
    except OSError:
        live_note = "not created"

    main_line = f"main run    : exit {main_rc}  (started {started})"
    if main_summary:
        main_line += f" — {main_summary}"
    report = [
        "",
        "=== FINAL REPORT ===",
        _now(),
        main_line,
    ]
    if serial_files:
        report.append(
            f"serial pass : exit {serial_rc} — {serial_summary}\n"
            f"              files: {', '.join(serial_files)}"
        )
    report.append(f"live log    : {live_log} — {live_note}")
    report.append("=== END FINAL REPORT ===")
    _log(fh, "\n".join(report) + "\n")
    fh.close()

    for line in report:
        print(line)

    if main_rc != 0:
        return main_rc
    if serial_rc not in (None, 0):
        return serial_rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
