import logging
import threading
import tkinter as tk
from tkinter import messagebox
import traceback
import sys
import os
import customtkinter as ctk

# Thread-safety: log tkinter violations from background threads so
# we get a full traceback instead of cryptic __del__ errors.
_thread_excepthook_installed = False


def _install_thread_excepthook():
    global _thread_excepthook_installed
    if _thread_excepthook_installed:
        return
    _thread_excepthook_installed = True

    _orig = threading.excepthook

    def _handler(args: threading.ExceptHookArgs):
        logger.error(
            "Uncaught exception in bg thread %s: %s: %s\n%s",
            args.thread.name,
            args.exc_type.__name__ if args.exc_type else "?",
            args.exc_value,
            "".join(
                traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
            ),
        )
        _orig(args)

    threading.excepthook = _handler
    logging.getLogger("core.thread_guard").debug("Installed global thread excepthook")


_install_thread_excepthook()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")
import signal

# Force TkAgg backend before any matplotlib import happens anywhere
import matplotlib
matplotlib.use('TkAgg')

# Adăugăm folderul curent în path pentru a evita erori de import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database.db_manager import DatabaseManager
    from config import Config
    from ui.ctk_styles import Theme
    from ui.main_window import MainWindow
    from services.api_service import APIService
    from services.i18n import init_language
    from services.preferences import PreferencesManager
    from services.operations.operations_engine import OperationsEngine
except Exception as e:
    logger.critical("Import failed: %s", traceback.format_exc())
    input("Press Enter to close...")
    sys.exit()

class CashflowApp:
    def __init__(self):
        try:
            # 0. Asigurare directoare
            Config.ensure_dirs()

            # 1. Inițializare Bază de Date
            self.db = DatabaseManager(Config.DB_PATH)

            # 2. Inițializare limbă (i18n)
            init_language()

            # 3. Inițializare Preferințe Centralizate (limbă, valută)
            self.prefs = PreferencesManager(self.db)
            self.prefs.load()

            # 4. Inițializare Serviciu API (Valută/Motorină)
            self.api = APIService()

            # 5. Inițializare Fereastră Principală (CustomTkinter)
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("dark-blue")
            ctk.set_widget_scaling(1.05)
            self.root = ctk.CTk()
            self.root.title(Config.APP_NAME)
            self.root.geometry("750x900")
            from ui.theme import COLORS
            self.root.configure(fg_color=COLORS["bg_base"])

            import tkinter.ttk as ttk
            from ui.theme import FONTS, S
            style = ttk.Style()
            style.theme_use("clam")
            style.configure("Treeview",
                background=COLORS["bg_surface"],
                foreground=COLORS["text_primary"],
                fieldbackground=COLORS["bg_surface"],
                bordercolor=COLORS["border"],
                rowheight=36,
                font=FONTS["body"]
            )
            style.configure("Treeview.Heading",
                background=COLORS["bg_base"],
                foreground=COLORS["text_muted"],
                bordercolor=COLORS["border"],
                relief="flat",
                font=FONTS["label"]
            )
            style.map("Treeview",
                background=[("selected", COLORS["bg_elevated"])],
                foreground=[("selected", COLORS["text_primary"])]
            )
            style.configure("Vertical.TScrollbar",
                background=COLORS["bg_surface"],
                troughcolor=COLORS["bg_base"],
                arrowcolor=COLORS["bg_base"],
                arrowsize=0, borderwidth=0, width=5
            )
            style.configure("Horizontal.TScrollbar",
                background=COLORS["bg_surface"],
                troughcolor=COLORS["bg_base"],
                arrowcolor=COLORS["bg_base"],
                arrowsize=0, borderwidth=0, height=5
            )

            Theme.apply(self.root)

            # 6. Inițializare Operations Engine (centralizat)
            self.ops = OperationsEngine(self.db)
            self.ops.start()

            # 7. Inițializare Fleet Tracking Service
            from services.fleet_tracking_service import fleet_tracking_service
            fleet_tracking_service.initialize(self.db)

            self.ui = MainWindow(self.root, self.db, self.api, prefs=self.prefs, ops=self.ops)

            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
            
        except Exception as e:
            logger.critical("Startup failed: %s", traceback.format_exc())
            input("Press Enter to see error...")
            sys.exit()

    def _on_close(self):
        try:
            self.ui.shutdown()
        except Exception:
            pass
        try:
            self.ops.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

def run_app(app):
    try:
        # Optionally ignore SIGINT so tkinter doesn't raise directly
        # signal.signal(signal.SIGINT, lambda *args: print("SIGINT received (ignored)"))
        app.root.mainloop()
    except KeyboardInterrupt:
        # Graceful shutdown
        try:
            app.root.quit()
            app.root.destroy()
        except Exception:
            pass
        print("Interrupted by user. Exiting.")
        sys.exit(0)

if __name__ == "__main__":
    app = CashflowApp()
    run_app(app)
