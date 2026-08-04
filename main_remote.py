"""PySide6 remote-only entry point for Operion ERP.

Running ``python main_remote.py`` launches the Qt application as a
pure API client — no local SQLite database, no repositories, no
backend services.  All data operations flow through ``ApiClient``
over HTTP/JSON to the FastAPI backend.

Usage::

    set OPERION_ENV=production
    set OPERION_API_URL=https://api.operionerp.com
    python main_remote.py

Or for local development::

    set OPERION_ENV=development
    python main_remote.py      # defaults to http://127.0.0.1:8000
"""

import contextlib
import logging
import os
import sys
import threading
import time
import traceback

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Load .env file if it exists (keeps environment variables out of git)
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.isfile(dotenv_path):
        load_dotenv(dotenv_path)
        logging.info("Loaded environment from .env file")
except Exception:
    pass

# Apply the QWebEngine Chromium flags BEFORE any PySide6 import.
from utils.webengine_flags import apply_webengine_flags
apply_webengine_flags()

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from config import Config
from ui.stylesheet import build_stylesheet

# ── Startup logging ─────────────────────────────────────────────────
# Central rotating-file + stdout configuration shared with main.py
# (see utils/logger.configure_app_logging).
from utils.logger import configure_app_logging
configure_app_logging(Config.LOG_FILE, level=logging.INFO)
logger = logging.getLogger("remote_app")


def run_remote() -> int:
    startup_start = time.perf_counter()

    env = os.environ.get("OPERION_ENV", "development").strip().lower()
    logger.info("Startup time: %.2fs", time.perf_counter() - startup_start)
    api_url = os.environ.get("OPERION_API_URL", "").strip()
    logger.info(
        "Starting Operion ERP (REMOTE) — env=%s api_url=%s",
        env, api_url or "<default>",
    )
    logger.info("ROOT=%s cwd=%s", PROJECT_ROOT, os.getcwd())

    try:
        Config.ensure_dirs()

        from services.i18n import init_language
        init_language()

        from client.config import get_client_config
        client_cfg = get_client_config()
        logger.info("Client config: base=%s ssl=%s env=%s",
                     client_cfg.base_url, client_cfg.verify_ssl, client_cfg.env)

        from client.api_client import ApiClient
        api_client = ApiClient(config=client_cfg)
        if api_client.is_online():
            logger.info("API server reachable at %s", client_cfg.base_url)
        else:
            logger.warning("API server NOT reachable at %s — views will run in degraded mode",
                           client_cfg.base_url)

        from client.remote_preferences import RemotePreferences
        prefs = RemotePreferences()
        prefs.load()

        from client.remote_ops_stub import RemoteOpsStub
        ops = RemoteOpsStub(api_client=api_client)

        # ── Pre-load heavy imports on a background thread ──────────
        # The ``from ui.main_window import MainWindow`` import triggers a
        # cascade of imports (all view modules, their dependencies) that can
        # take several seconds.  We start this on a daemon thread NOW so the
        # imports resolve concurrently with the login dialog.  Python imports
        # are GIL-protected and safe to run on any thread as long as they
        # don't create Qt widgets (which only happens inside constructors,
        # not at module level).
        _main_window_class: list = [None]
        _imports_ready = threading.Event()

        def _preload_imports() -> None:
            try:
                from ui.main_window import MainWindow
                _main_window_class[0] = MainWindow
            except Exception:
                logger.exception("Background preload of MainWindow failed")
            finally:
                _imports_ready.set()

        _preload_thread = threading.Thread(target=_preload_imports, daemon=True)
        _preload_thread.start()
        logger.info("Pre-loading MainWindow imports on background thread…")

        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.Round
        )
        app = QApplication(sys.argv)
        app.setApplicationName(Config.APP_NAME)
        app.setApplicationDisplayName(Config.APP_NAME)

        # Global exception handling — uncaught exceptions (Python or Qt) log
        # a full traceback and surface a user-facing dialog instead of
        # crashing silently.  Must run after QApplication creation and before
        # app.exec() so dialogs can be shown.
        from utils.error_handling import install_global_handlers
        install_global_handlers()

        # Auto-login hydration — restore persisted token if still valid
        from client.auth_manager import get_auth, hydrate_from_storage, require_auth_async
        try:
            hydrated = hydrate_from_storage()
        except Exception:
            logger.debug("Auto-login hydration skipped (first boot or no storage).")
            hydrated = False

        app.setStyleSheet(build_stylesheet())

        # ── Diagnostics Engine ─────────────────────────────────────
        diagnostics_enabled = os.environ.get("OPERION_DIAGNOSTICS", "1") == "1"
        diagnostics_engine = None
        if diagnostics_enabled:
            try:
                from diagnostics import DiagnosticsEngine
                diagnostics_engine = DiagnosticsEngine(output_dir="logs/diagnostics")
                diagnostics_engine.install_all()
                diagnostics_engine.start_monitoring()
                logger.info("[DIAG] Runtime diagnostics engine started")
            except Exception as exc:
                logger.warning("[DIAG] Diagnostics engine skipped: %s", exc)

        # ── Pre-warm QWebEngine Chromium process ──────────────────
        # Force-initialize the embedded Chromium engine NOW, while
        # no visible window exists, so its transient GPU/compositor
        # windows flash harmlessly in the background rather than
        # appearing as ghost boxes after the main window is shown.
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            _prewarm = QWebEngineView()
            _prewarm.resize(1, 1)
            app.processEvents()
            _prewarm.deleteLater()
            del _prewarm
        except Exception:
            pass

        # If no stored session was restored, prompt the user to log in now.
        # The login dialog is modal so the main thread blocks here — but the
        # background import thread keeps running, resolving all view modules
        # while the user types their credentials.
        if not hydrated:
            if not require_auth_async():
                logger.info("Login cancelled or failed — exiting.")
                return 0

        # After login (or token restore), push the current auth onto the
        # ApiClient so all subsequent HTTP requests carry the Bearer token.
        auth = get_auth()
        if auth is not None:
            api_client.update_auth(auth)
            logger.info("Remote app — auth token set on API client.")

        # Wait for background imports to finish (should already be done
        # if the user spent more than a couple of seconds logging in).
        _imports_ready.wait()
        logger.info("MainWindow imports ready (waited %.1fs after login)",
                     time.perf_counter() - startup_start)

        MainWindow = _main_window_class[0]
        if MainWindow is None:
            # Fallback: import synchronously if the background thread failed
            from ui.main_window import MainWindow

        window = MainWindow(db=None, api=None, prefs=prefs, ops=ops,
                           api_client=api_client)
        window.show()

        # ── Deferred: Choreographer browser init ───────────────────
        try:
            from utils.chart_export import configure_choreographer_export
            configure_choreographer_export()
        except Exception:
            logger.debug("Choreographer config skipped (not installed)")

        logger.info("PySide6 remote application started")
        result = app.exec()

        ops.stop()
        with contextlib.suppress(Exception):
            from utils.chart_export import shutdown_browser_sync
            shutdown_browser_sync()
        api_client.close()
        if diagnostics_engine:
            diagnostics_engine.shutdown()
        return result

    except Exception:
        tb = traceback.format_exc()
        logger.critical("Startup failed: %s", tb)
        print(f"\nFATAL STARTUP ERROR:\n{tb}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    print(f"Python: {sys.executable}")
    print(f"Working dir: {os.getcwd()}")
    print(f"Env: {os.environ.get('OPERION_ENV', 'development')}")
    sys.exit(run_remote())
