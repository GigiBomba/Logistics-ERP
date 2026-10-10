"""pytest plugin: append every failed/errored report to a live log file.

Purpose
-------
Full-suite runs in this repo die before pytest can print its summary, so the
names of the thousands of setup-ERROR (``E``) progress marks are never seen.
This plugin writes each failure/ERROR report the *moment* it happens, so a
crashed run still leaves a complete, timestamped list behind.

Activation
----------
Loaded with ``-p pytest_live_log`` (``scripts/`` must be on ``PYTHONPATH``);
``scripts/run_pytest_guarded.py`` does both automatically.  The destination
file comes from ``PYTEST_LIVE_LOG`` (default ``live_failures.log``).

xdist
-----
``pytest_runtest_logreport`` runs in whichever process produces the report —
for xdist that is the *worker* — so records are appended from worker
processes too.  The controller also sees the forwarded report and appends a
second copy, so under xdist each failure appears twice; the leading ``pid``
tells the two writers apart.  No controller-side hook is required.

Record format (one line per failed/errored report)::

    <pid> <YYYY-MM-DDTHH:MM:SS+HH:MM> <nodeid> [<phase>] :: <~200 chars, newlines flattened>

where ``<phase>`` is ``setup`` / ``call`` / ``teardown`` (distinguishes the
``E`` setup-error marks from ordinary assertion failures).

Only reports whose ``outcome`` is ``failed`` are written: setup errors,
call-phase assertion failures and teardown errors alike.  Skips and passes
are ignored (the console already shows those).  Appends are opened and
closed per record so concurrent writers (xdist workers) can share the file.
"""
from __future__ import annotations

import datetime
import os

_MAX_REPR = 200


def _live_log_path() -> str:
    return os.environ.get("PYTEST_LIVE_LOG") or "live_failures.log"


def _flatten(text: str, limit: int = _MAX_REPR) -> str:
    """Collapse newlines/whitespace and truncate to ``limit`` chars."""
    flat = " ".join(text.split())
    if len(flat) > limit:
        flat = flat[: limit - 1] + "..."
    return flat


def _append(line: str) -> None:
    """Append one record; never let logging break the test run."""
    path = _live_log_path()
    try:
        with open(path, "a", encoding="utf-8", errors="replace") as fh:
            fh.write(line + "\n")
            fh.flush()
    except Exception:  # pragma: no cover - best-effort diagnostics only
        pass


def pytest_runtest_logreport(report):  # noqa: D401 - pytest hook
    """Write a record immediately for every failed/errored test phase."""
    if getattr(report, "outcome", None) != "failed":
        return

    longrepr = getattr(report, "longrepr", None)
    if longrepr is None:
        text = "(no longrepr)"
    else:
        try:
            text = str(longrepr)
        except Exception:  # pragma: no cover - repr() of a broken object
            text = "(unprintable longrepr)"

    when = getattr(report, "when", "?")
    nodeid = getattr(report, "nodeid", "<unknown>")
    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    _append(
        "{pid} {when} {node} [{phase}] :: {text}".format(
            pid=os.getpid(),
            when=stamp,
            node=nodeid,
            phase=when,
            text=_flatten(text),
        )
    )
