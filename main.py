"""PySide6 entry point for Operion ERP.

Running ``python main.py`` launches the Qt version of the app.
"""

import sys
import os
import time
import logging
import traceback

# Ensure the project root is on sys.path for absolute imports.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from config import Config  # noqa: E402
from ui.stylesheet import build_stylesheet  # noqa: E402
from utils.observability import log, metrics, perf_timer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")


def run_app() -> int:
    startup_start = time.perf_counter()
    try:
        # Quick pre-flight check — ensure critical dependency is available early
        try:
            import qtawesome  # noqa: F401
        except ImportError:
            print(f"\nERROR: qtawesome is not installed in this Python environment.", file=sys.stderr)
            print(f"Python path: {sys.executable}", file=sys.stderr)
            print(f"Run: py -3 -m pip install qtawesome\n", file=sys.stderr)
            return 1

        # Health check — verify DB, filesystem, and core imports before heavy init
        from services.health_check import check_filesystem
        fs = check_filesystem()
        if fs["status"] != "healthy":
            logger.warning("Filesystem health check degraded: %s", fs.get("details"))
        # Note: full DB check deferred to after DB manager init below

        Config.ensure_dirs()

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

        # 6. Document Center migration
        try:
            from services.document_service import DocumentService
            ds = DocumentService(db)
            migrated = ds.migrate_all()
            if migrated > 0:
                logger.info("Document Center migration: %d existing files registered", migrated)
        except Exception as e:
            logger.warning("Document Center migration skipped: %s", e)

        # 7. Qt application + main window
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)
        app.setApplicationName(Config.APP_NAME)
        app.setApplicationDisplayName(Config.APP_NAME)

        app.setStyleSheet(build_stylesheet())

        from ui.main_window import MainWindow  # noqa: E402
        window = MainWindow(db, api, prefs=prefs, ops=ops)
        window.show()

        logger.info("PySide6 application started")
        metrics.gauge("startup_time_s", time.perf_counter() - startup_start)
        log.info("app_started", startup_ms=round((time.perf_counter() - startup_start) * 1000))
        result = app.exec()

        # 8. Cleanup — close DB after Qt event loop ends
        ops.stop()
        try:
            db.close()
        except Exception:
            pass
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
