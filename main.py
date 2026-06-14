"""PySide6 entry point for Operion ERP.

Running ``python main.py`` launches the Qt version of the app.
"""

import sys
import os
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")


def run_app() -> int:
    try:
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
        return app.exec()

    except Exception:
        logger.critical("Startup failed: %s", traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(run_app())
