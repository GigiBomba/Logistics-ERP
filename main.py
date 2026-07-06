"""PySide6 entry point for Operion ERP.

Running ``python main.py`` launches the Qt version of the app.
"""

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
logger = logging.getLogger("app")  # re-bind after the guard line
logger.debug("Plotly renderer pinned to 'json'; dummy browser registered")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from config import Config
from ui.stylesheet import build_stylesheet
from utils.observability import log, metrics
from utils.resource_path import _is_packaged

# ── Startup logging ─────────────────────────────────────────────────
# Ensure the log directory exists before setting up the file handler.
_log_dir = os.path.dirname(Config.LOG_FILE)
os.makedirs(_log_dir, exist_ok=True)
_handler = logging.FileHandler(Config.LOG_FILE, encoding="utf-8", delay=True)
_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s %(name)s: %(message)s"
))
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), _handler],
)
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


def run_app() -> int:
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

        # 8a. Auto-login hydration — restore persisted token if still valid
        try:
            from client.auth_manager import hydrate_from_storage
            hydrate_from_storage()
        except Exception:
            logger.debug("Auto-login hydration skipped (first boot or no storage).")

        app.setStyleSheet(build_stylesheet())

        from PySide6.QtCore import QTimer

        from ui.main_window import MainWindow
        window = MainWindow(db, api, prefs=prefs, ops=ops)
        window.show()

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
        result = app.exec()

        # 8. Cleanup — close DB and shared browser after Qt event loop ends
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
    sys.exit(run_app())
