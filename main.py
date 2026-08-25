"""PySide6 entry point for Operion ERP.

Running ``python main.py`` launches the Qt version of the app.
"""
from __future__ import annotations


import contextlib
import logging
import os
import sys
import time
import traceback

# Ensure the project root is on sys.path for absolute imports.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Load .env file if it exists (keeps environment variables out of git)
with contextlib.suppress(Exception):
    from dotenv import load_dotenv
    dotenv_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.isfile(dotenv_path):
        load_dotenv(dotenv_path)
        logging.info("Loaded environment from .env file")

# ── QWebEngine flags — must execute before any PySide6 import ──────
# The ``from PySide6.QtWebEngineWidgets import QWebEngineView`` chain
# transitively triggered by ``ui/main_window → ui/views → ui/map``
# initialises Qt's child Chromium process BEFORE ``window.show()``.
# Without these environment flags the GPU/compositor process creates
# a transient top-level window that flashes in the corner of the
# screen at startup.
from utils.webengine_flags import apply_webengine_flags
apply_webengine_flags()

# ── Plotly guard — must execute before any module imports plotly.io ──
# Register a dummy webbrowser so stray fig.show() calls never spawn
# a browser window.  This precedes every other import that could
# trigger ``import plotly.io`` (e.g. ui/main_window → ui/views → …).
import webbrowser as _webbrowser


class _DummyBrowser:
    def open(self, url, new=0, autoraise=True):
        pass
    def open_new(self, url):
        pass
    def open_new_tab(self, url):
        pass


_webbrowser.register("dummy", None, _DummyBrowser(), preferred=True)
import plotly.io as _pio
_pio.renderers.default = "json"
logging.getLogger("app").debug("Plotly renderer pinned to 'json'; dummy browser registered")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from config import Config
from ui.stylesheet import build_stylesheet
from utils.observability import log, metrics
from utils.resource_path import _is_packaged

# ── Startup logging ─────────────────────────────────────────────────
# Central rotating-file + stdout configuration shared with main_remote.py
# (see utils/logger.configure_app_logging).
from utils.logger import configure_app_logging
configure_app_logging(Config.LOG_FILE, level=logging.INFO)
logger = logging.getLogger("app")


def _register_operion_protocol() -> None:
    r"""Register the ``operion://`` custom protocol handler on Windows.

    Writes to ``HKEY_CLASSES_ROOT\operion`` so that clicking an
    ``operion://route?...`` link in a browser or chat app opens Operion
    and passes the URL as ``--open-url`` argument.

    This is a best-effort registration — it fails silently if the
    current user does not have write access to HKCR (admin rights).
    """
    try:
        import winreg

        exe_path = os.path.normpath(sys.executable if not _is_packaged() else sys.argv[0])
        cmd = f'"{exe_path}" --open-url "%1"'

        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, "operion") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Operion Route")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"operion\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd)

        # Also register .operionroute file association
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, ".operionroute") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Operion.Route")
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Operion.Route\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd.replace("--open-url", "--open-file"))

        logger.debug("operion:// protocol handler registered")
    except Exception:
        logger.debug("Could not register operion:// protocol (admin rights may be required)")


def setup_sync(db, main_window, api_client=None, interval_seconds: int = 60):
    """Wire the offline-first sync engine into the app (Phase 4b / F).

    Builds the ApiClient (unless one is injected), the outbox/pull services
    and the ``SyncEngine``, connects the engine's signals to the main
    window's sync status indicator + conflict journal, and returns the
    engine.

    Phase F (production wiring): the engine's per-user cursor namespace is
    locked to the logged-in user.  Login happens BEFORE this function runs
    (the ``require_admin_async`` gate in ``run_app``), so the initial user is
    set at construction; an ``on_auth_changed`` callback keeps the engine in
    lockstep with mid-session login/logout/user switches (each switch forces
    a full refresh for the new user — see ``SyncEngine.set_user``).

    NOTE (multi-company outbox, accepted design): pending outbox rows are
    pushed under the CURRENTLY logged-in user's JWT (the server stamps
    ``company_id`` from the JWT).  User B logging in while user A's rows are
    still pending would push them into B's company.  No drain/flush mechanism
    is built here — documented so a company switch with a non-empty outbox
    can be handled deliberately (flush first) if it ever becomes a real
    scenario.

    The app is local-first ALWAYS: this is best-effort.  If the API config
    is missing or the ApiClient cannot be constructed, a warning is logged
    and ``None`` is returned — the app continues fully local-only.

    Returns:
        The configured ``SyncEngine``, or ``None`` when sync is unavailable.
    """
    try:
        if api_client is None:
            from client.api_client import ApiClient
            from client.config import get_client_config
            api_client = ApiClient(config=get_client_config())

        from services.sync_conflict_service import SyncConflictService
        from services.sync_engine import SyncEngine
        from services.sync_outbox_service import SyncOutboxService
        from services.sync_pull_service import SyncPullService

        outbox = SyncOutboxService(db)
        pull = SyncPullService(db, api_client)

        # Phase F: the login gate ran before this function, so the initial
        # per-user cursor namespace comes from the already-established session.
        from client.auth_manager import get_auth, on_auth_changed
        auth = get_auth()
        initial_user_id = auth.user_id if auth is not None else 0

        # The sync client MUST carry the logged-in user's Bearer token —
        # without it the server rejects every push/pull with 401 (the sync
        # endpoints require a JWT).  Guarded with hasattr for test doubles
        # that don't implement update_auth.
        if hasattr(api_client, "update_auth"):
            api_client.update_auth(auth)

        engine = SyncEngine(
            db, api_client, outbox, pull,
            interval_seconds=interval_seconds,
            user_id=initial_user_id,
        )

        def _sync_user_for_auth(auth=None):
            """Keep the engine's per-user cursors in lockstep with login state."""
            if auth is None:
                auth = get_auth()
            uid = auth.user_id if auth is not None else 0
            # set_user also forces a one-shot full refresh, so a user switch
            # (or logout) can never leave polluted partial cursors behind.
            engine.set_user(uid)
            # Keep the sync client's Bearer header in lockstep with login /
            # logout — a stale header 401s every request after logout.
            if hasattr(api_client, "update_auth"):
                api_client.update_auth(auth)

        # Initial state (login already happened) — set_user also clears any
        # stale force flag / cursor namespace for the just-created engine.
        _sync_user_for_auth(auth)
        # Reactive: in-app login/logout/user switches (set_auth/clear_auth/
        # hydrate_from_storage all notify through auth_manager).
        on_auth_changed(_sync_user_for_auth)

        if main_window is not None:
            main_window.setup_sync_ui(
                engine,
                outbox=outbox,
                pull=pull,
                conflict_service=SyncConflictService(db),
            )
        return engine
    except Exception as exc:
        logger.warning(
            "Sync engine setup skipped (%s) — app continues local-only", exc
        )
        return None


def run_app(return_window: bool = False):
    """Run the Operion ERP application.

    Args:
        return_window: If True, returns ``(app, window)`` instead of the exit code.
                       Used by measurement scripts that need access to the window object.

    Returns:
        int exit code, or ``(QApplication, MainWindow)`` if *return_window* is True.
    """
    startup_start = time.perf_counter()

    # Parse CLI arguments for route sharing
    open_url = None
    open_file = None
    for arg in sys.argv[1:]:
        if arg.startswith("--open-url="):
            open_url = arg.split("=", 1)[1]
        elif arg.startswith("--open-file="):
            open_file = arg.split("=", 1)[1]
        elif arg.startswith("operion://"):
            open_url = arg

    logger.info(
        "Starting %s — packaged=%s cwd=%s meipass=%s",
        Config.APP_NAME,
        _is_packaged(),
        os.getcwd(),
        getattr(sys, "_MEIPASS", "N/A"),
    )
    if open_url:
        logger.info("Startup with --open-url (share link)")
    if open_file:
        logger.info("Startup with --open-file (route file)")

    logger.info("DB_PATH=%s LOG_FILE=%s", Config.DB_PATH, Config.LOG_FILE)

    # Register the operion:// protocol handler on Windows
    _register_operion_protocol()

    try:
        # Quick pre-flight check — ensure critical dependency is available early
        try:
            import qtawesome  # noqa: F401
        except ImportError:
            logger.warning("qtawesome not installed — some icons will use fallback rendering")

        # Health check — verify DB, filesystem, and core imports before heavy init
        from services.health_check import check_filesystem
        fs = check_filesystem()
        if fs["status"] != "healthy":
            logger.warning("Filesystem health check degraded: %s", fs.get("details"))
        # Note: full DB check deferred to after DB manager init below

        Config.ensure_dirs()

        # 7b. Choreographer — headless static image export
        try:
            from utils.chart_export import configure_choreographer_export
            configure_choreographer_export()
        except Exception:
            logger.debug("Choreographer config skipped (not installed)")

        # 1. Database
        from database.db_manager import DatabaseManager
        db = DatabaseManager(Config.DB_PATH)

        # 2. i18n
        from services.i18n import init_language
        init_language()

        # 3. Preferences
        from services.preferences import PreferencesManager
        prefs = PreferencesManager(db)
        prefs.load()

        # 4. API service
        from services.api_service import APIService
        api = APIService()

        # 5. Operations engine
        from services.operations.operations_engine import OperationsEngine
        ops = OperationsEngine(db, prefs=prefs)
        ops.start()

        # 6. Cloud OCR and AI Vision credentials from settings DB
        try:
            from services.document_automation.cloud_ocr import init_from_db
            init_from_db(db)
        except Exception:
            logger.warning("Cloud OCR init_from_db failed — env vars only")
        try:
            from services.document_automation.ai_fallback import init_from_db as ai_init
            ai_init(db)
        except Exception:
            logger.warning("AI Vision init_from_db failed")

        # Preload AI model in bg so first OCR call is fast
        try:
            import threading as _t

            from services.document_automation.ai_fallback import preload_model
            _t.Thread(target=preload_model, daemon=True).start()
        except Exception:
            logger.warning("AI model preload failed")

        # 7. Document Center migration
        try:
            from repositories.document_repository import DocumentRepository
            from services.document.upload_service import UploadService
            svc = UploadService(db, DocumentRepository(db))
            migrated = svc.migrate_all()
            if migrated > 0:
                logger.info("Document Center migration: %d existing files registered", migrated)
        except Exception as e:
            logger.warning("Document Center migration skipped: %s", e)

        # 8. Qt application + main window
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

        # 8a. Auto-login hydration — restore persisted token if still valid
        try:
            from client.auth_manager import hydrate_from_storage
            hydrate_from_storage()
        except Exception:
            logger.debug("Auto-login hydration skipped (first boot or no storage).")

        # 8b. Login gate — require authentication before showing the main window
        from client.auth_manager import is_admin, require_admin_async
        if not is_admin():
            if not require_admin_async():
                logger.info("Login cancelled or failed — exiting.")
                return 0

        app.setStyleSheet(build_stylesheet())

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

        from PySide6.QtCore import QTimer

        from ui.main_window import MainWindow
        window = MainWindow(db, api, prefs=prefs, ops=ops)
        window.show()

        # ── Offline-first sync (Phase 4b) ─────────────────────────────
        # Local-first ALWAYS: boot the background sync engine that pushes
        # the local outbox to the cloud API and pulls server rows when
        # online.  Best-effort — if no API config exists the app continues
        # local-only.
        sync_engine = setup_sync(db, window)
        if sync_engine is not None:
            sync_engine.start()
            logger.info("Sync engine started")

        # Handle route sharing URL or file passed via CLI args.
        # Deferred via QTimer so the event loop is running and the
        # window is fully laid out before we try to navigate.
        if open_url:
            QTimer.singleShot(500, lambda: window.open_route_url(open_url))
        if open_file:
            QTimer.singleShot(500, lambda: window.open_route_file(open_file))

        logger.info("PySide6 application started")
        metrics.gauge("startup_time_s", time.perf_counter() - startup_start)
        log.info("app_started", startup_ms=round((time.perf_counter() - startup_start) * 1000))

        if return_window:
            # Return early with app/window handles for measurement scripts
            return app, window

        result = app.exec()

        # 8. Cleanup — stop sync engine, close DB and shared browser after
        # the Qt event loop ends.
        # R4: engine.stop() MUST complete before db.close() — the engine's
        # worker thread owns a thread-local SQLite connection; closing the
        # pool out from under it would crash.  stop() waits for the cycle to
        # abort (stop flag + wait without a short ceiling), so this order is
        # safe.
        if sync_engine is not None:
            sync_engine.stop()
            logger.info("Sync engine stopped")
        ops.stop()
        with contextlib.suppress(Exception):
            from utils.chart_export import shutdown_browser_sync
            shutdown_browser_sync()
        with contextlib.suppress(Exception):
            db.close()
        with contextlib.suppress(Exception):
            from services.document_automation.ai_fallback import close_session
            close_session()
        return result

    except Exception:
        tb = traceback.format_exc()
        logger.critical("Startup failed: %s", tb)
        print(f"\nFATAL STARTUP ERROR:\n{tb}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # Show Python path for diagnostics
    print(f"Python: {sys.executable}")
    print(f"Working dir: {os.getcwd()}")
    sys.exit(run_app())  # type: ignore[arg-type]
