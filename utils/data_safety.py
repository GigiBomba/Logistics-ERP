import os
import shutil
import json
import sqlite3
from datetime import datetime
from tkinter import messagebox

class DataSafetyService:
    def __init__(self, db_path):
        self.db_path = db_path
        self.backup_dir = os.path.abspath("data/backups")
        self.export_dir = os.path.abspath("data/exports")
        
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.export_dir, exist_ok=True)

    def auto_backup(self):
        """Creează o copie a bazei de date cu timestamp."""
        try:
            if not os.path.exists(self.db_path): return
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            backup_file = os.path.join(self.backup_dir, f"cashflow_backup_{timestamp}.db")
            
            shutil.copy2(self.db_path, backup_file)
            self._cleanup_old_backups()
            print(f"Backup creat: {backup_file}")
        except Exception as e:
            print(f"Eroare backup: {e}")

    def _cleanup_old_backups(self, limit=10):
        """Păstrează doar ultimele 10 backup-uri pentru a economisi spațiu."""
        files = [os.path.join(self.backup_dir, f) for f in os.listdir(self.backup_dir)]
        files.sort(key=os.path.getmtime)
        while len(files) > limit:
            os.remove(files.pop(0))

    def export_to_json(self, trips_list):
        """Exportă baza de date într-un fișier JSON (portabil)."""
        try:
            filename = f"export_data_{datetime.now().strftime('%Y%m%d')}.json"
            path = os.path.join(self.export_dir, filename)
            
            # Convertim obiectele sqlite3.Row în dicționare simple
            data = [dict(trip) for trip in trips_list]
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return path
        except Exception as e:
            raise Exception(f"Eroare export JSON: {e}")

    def import_from_json(self, json_path, db_manager):
        """Încarcă date dintr-un JSON înapoi în SQLite."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Adăugăm fiecare cursă în DB
            for trip in data:
                if 'id' in trip: del trip['id'] # Lăsăm DB să genereze ID-uri noi
                db_manager.add_trip(trip)
            return len(data)
        except Exception as e:
            raise Exception(f"Eroare import JSON: {e}")