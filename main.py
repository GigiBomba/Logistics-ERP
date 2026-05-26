import tkinter as tk
from tkinter import messagebox
import traceback
import sys
import os
import signal

# Adăugăm folderul curent în path pentru a evita erori de import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database.db_manager import DatabaseManager
    from config import Config
    from ui.styles import Theme
    from ui.main_window import MainWindow
    from services.api_service import APIService
    from services.i18n import init_language
    from services.preferences import PreferencesManager
    from utils.data_safety import DataSafetyService
except Exception as e:
    print(f"EROARE LA IMPORT: {traceback.format_exc()}")
    input("Apasa Enter pentru a Inchide...")
    sys.exit()

class CashflowApp:
    def __init__(self):
        try:
            # 1. Inițializare Bază de Date
            self.db = DatabaseManager(Config.DB_PATH)

            # 2. Inițializare limbă (i18n)
            init_language()

            # 3. Inițializare Preferințe Centralizate (limbă, valută)
            self.prefs = PreferencesManager(self.db)
            self.prefs.load()

            # 4. Inițializare Serviciu API (Valută/Motorină)
            self.api = APIService()

            # 5. Inițializare Serviciu Siguranță (Backup/JSON)
            self.safety = DataSafetyService(Config.DB_PATH)
            self.safety.auto_backup() # Backup automat la fiecare pornire

            # 6. Inițializare Fereastră Principală (Tkinter)
            self.root = tk.Tk()
            self.root.title(Config.APP_NAME)
            self.root.geometry("750x900")
            Theme.apply(self.root)

            self.ui = MainWindow(self.root, self.db, self.api, self.safety, prefs=self.prefs)
            
        except Exception as e:
            print(f"EROARE LA PORNIRE: {traceback.format_exc()}")
            input("Apasă Enter pentru a vedea eroarea...")
            sys.exit()

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
