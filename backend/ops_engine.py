"""Server-side OperationsEngine bootstrap (remote-mode parity).

The desktop app runs ``OperationsEngine(db, prefs).start()`` in LOCAL mode
to power background alert generation (maintenance, trip status, invoice
reminders, auto-CMR, notifications).  In REMOTE mode the desktop has no
local database, so the FastAPI backend runs the same engine against its own
database and the desktop surfaces the results through the alerts API.

This module is the guarded bootstrap used by ``backend.main.create_app``:

* It is OPT-IN: only starts when ``OPERION_RUN_OPS_ENGINE=1``.
* It NEVER starts under pytest: ``TestClient`` triggers lifespan events in
  every API suite, so the guard additionally checks that ``pytest`` is not
  loaded (``sys.modules.get("pytest") is None``) as belt-and-braces.
* Startup failures are logged but never block the API server.

The engine uses ``PreferencesManager(db)`` — a settings-table-backed prefs
object, exactly matching the desktop ``main.py`` wiring (and the prefs
already used by the ``/api/v1/alerts`` router).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

logger = logging.getLogger("backend.ops_engine")

_OPS_ENGINE_ENV = "OPERION_RUN_OPS_ENGINE"


def should_run_ops_engine() -> bool:
    """Return True only when the engine is explicitly enabled AND pytest is
    not running (TestClient triggers lifespan in tests)."""
    if os.environ.get(_OPS_ENGINE_ENV) != "1":
        return False
    if sys.modules.get("pytest") is not None:
        logger.debug("ops engine disabled: running under pytest")
        return False
    return True


def start_ops_engine(app) -> Optional[object]:
    """Start the server-side OperationsEngine workers against *app*'s DB.

    Returns the engine instance, or ``None`` when disabled or on failure
    (a broken engine must never block API startup).
    """
    if not should_run_ops_engine():
        return None
    try:
        from backend.dependencies import init_db
        from services.operations.operations_engine import OperationsEngine
        from services.preferences import PreferencesManager

        db = init_db(app)
        prefs = PreferencesManager(db)
        ops = OperationsEngine(db, prefs=prefs)
        ops.start()
        logger.info(
            "Server-side OperationsEngine started (maintenance, dunner, "
            "notification, auto-CMR, trip workflow)"
        )
        return ops
    except Exception:
        logger.warning("Server-side OperationsEngine startup skipped", exc_info=True)
        return None


def stop_ops_engine(ops) -> None:
    """Gracefully stop the engine (daily timer, dunner shutdown, unsubscribes)."""
    if ops is None:
        return
    try:
        ops.stop()
        logger.info("Server-side OperationsEngine stopped")
    except Exception:
        logger.debug("Server-side OperationsEngine stop failed", exc_info=True)
