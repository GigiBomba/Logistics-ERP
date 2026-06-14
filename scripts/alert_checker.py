"""Background alert checker — runs periodic checks and sends desktop notifications.

Designed to be invoked periodically via Windows Task Scheduler (e.g. every 15
minutes).  Loads the same database and services that the main app uses, runs
maintenance/inspection checks, and sends a native Windows toast notification
for any new alerts that were created.

Usage via Task Scheduler::

    python -m scripts.alert_checker

Zero external dependencies beyond what the project already requires.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from typing import List, Optional

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import winsound

from config import Config
from database.db_manager import DatabaseManager
from services.i18n import init_language
from services.preferences import PreferencesManager
from services.operations.event_bus import EventBus, SYSTEM_STARTUP, DAILY_CHECK
from services.operations.maintenance_engine import MaintenanceEngine
from services.fleet_maintenance_service import FleetMaintenanceService

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.alert_checker")


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _capture_alert_ids(engine) -> set:
    """Return the set of alert IDs currently known to the engine."""
    try:
        mgr = engine._alert_mgr if hasattr(engine, "_alert_mgr") else None
        if mgr is None:
            return set()
        return set(mgr._alerts.keys())
    except Exception:
        return set()


def _new_alerts(engine, before: set) -> list:
    """Return list of alert dicts created since *before* was captured."""
    try:
        mgr = engine._alert_mgr if hasattr(engine, "_alert_mgr") else None
        if mgr is None:
            return []
        after = set(mgr._alerts.keys())
        new_ids = after - before
        return [mgr._alerts[a].to_dict() for a in new_ids]
    except Exception:
        return []


def _play_sound() -> None:
    """Play the system exclamation sound."""
    try:
        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
    except Exception:
        pass


def _send_toast(title: str, message: str) -> None:
    """Send a native Windows toast notification via PowerShell.

    Falls back to a classic MessageBox if PowerShell fails.
    """
    # PowerShell script for native Windows toast notification
    ps_script = f"""
$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime]
$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
$toastXml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
$textNodes = $toastXml.GetElementsByTagName("text")
$textNodes.Item(0).AppendChild($toastXml.CreateTextNode("{_escape_ps(title)}")) | Out-Null
$textNodes.Item(1).AppendChild($toastXml.CreateTextNode("{_escape_ps(message)}")) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($toastXml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Operion ERP").Show($toast)
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        # Fallback: classic Windows message box via ctypes
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40 | 0x1000)
        except Exception:
            pass


def _escape_ps(text: str) -> str:
    """Escape text for embedding in a PowerShell string."""
    return text.replace("'", "''").replace('"', '""').replace("\n", " ").replace("\r", "")


# ──────────────────────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────────────────────


def run_checks() -> None:
    """Run all periodic checks and notify for new alerts."""
    Config.ensure_dirs()
    db = DatabaseManager(Config.DB_PATH)

    # Minimal service initialisation (same as the app's early boot)
    init_language()
    prefs = PreferencesManager(db)
    prefs.load()

    ops_engine = _init_ops_engine(db, prefs)
    if ops_engine is None:
        logger.warning("Operations engine not available — skipping checks")
        return

    # Capture alerts BEFORE running checks
    before = _capture_alert_ids(ops_engine)

    # Run the same checks the app runs on startup and daily
    logger.info("Running periodic checks…")
    try:
        ops_engine._event_bus.publish(DAILY_CHECK, {})

        if hasattr(ops_engine, "_maintenance_engine") and ops_engine._maintenance_engine:
            ops_engine._maintenance_engine.evaluate_all()
    except Exception as e:
        logger.exception("Check execution failed: %s", e)

    # Detect new alerts
    alerts = _new_alerts(ops_engine, before)
    if not alerts:
        logger.info("No new alerts — done")
        return

    logger.info("Found %d new alert(s)", len(alerts))

    # Play notification sound + show toast
    _play_sound()

    for alert in alerts[:5]:  # limit to 5 toasts to avoid spam
        title = f"[{alert.get('severity', '').upper()}] {alert.get('title', 'Alert')}"
        msg = alert.get("message", "")
        _send_toast(title, msg)
        time.sleep(0.5)

    if len(alerts) > 5:
        _send_toast(
            f"{len(alerts)} alerts",
            f"{len(alerts) - 5} more alerts not shown — open the app to view all.",
        )


def _init_ops_engine(db, prefs):
    """Initialise a lightweight operations engine for background checks."""
    try:
        from services.operations.operations_engine import OperationsEngine
        engine = OperationsEngine(db=db, prefs=prefs)
        # Manually wire what start() does, without timers or subscriptions
        # that assume a live GUI.
        engine._running = True
        engine._event_bus.publish(SYSTEM_STARTUP, {})
        if hasattr(engine, "_maintenance_engine") and engine._maintenance_engine:
            engine._maintenance_engine.evaluate_all()
        return engine
    except Exception as e:
        logger.exception("Failed to initialise operations engine: %s", e)
        return None


if __name__ == "__main__":
    run_checks()
