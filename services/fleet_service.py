import sqlite3
from datetime import datetime


class FleetService:
    def __init__(self, db):
        # db is expected to be a DatabaseManager instance
        self.db = db

    # --- Trucks CRUD and helpers ---
    def get_trucks(self):
        return self.db.conn.execute(
            "SELECT id, plate_number, model, manufacturer, year, vin, mileage, fuel_consumption, monthly_rate, status, insurance_expiry, inspection_expiry, maintenance_due, active_status FROM trucks"
        ).fetchall()

    def get_truck(self, truck_id):
        return self.db.conn.execute(
            "SELECT id, plate_number, model, manufacturer, year, vin, mileage, fuel_consumption, monthly_rate, status, insurance_expiry, inspection_expiry, maintenance_due, active_status FROM trucks WHERE id = ?",
            (truck_id,)
        ).fetchone()

    def get_assigned_routes(self, truck_id, status=None):
        """Return assigned/active/completed route history for one truck."""
        query = """
            SELECT a.*, h.last_calculated_at, h.total_distance_km, h.duration_min,
                   h.profile, h.stops_json
            FROM truck_route_assignments a
            JOIN route_history_v2 h ON h.id = a.route_id
            WHERE a.truck_id = ?
        """
        params = [str(truck_id)]
        if status:
            query += " AND a.status = ?"
            params.append(status)
        query += " ORDER BY COALESCE(a.started_at, a.assigned_at) DESC"
        return self.db.conn.execute(query, params).fetchall()

    def add_truck(self, data: dict):
        keys = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        query = f"INSERT INTO trucks ({keys}) VALUES ({placeholders})"
        cursor = self.db.conn.execute(query, tuple(data.values()))
        self.db.conn.commit()
        return cursor.lastrowid

    def update_truck(self, truck_id, data: dict):
        placeholders = ", ".join([f"{key} = ?" for key in data.keys()])
        query = f"UPDATE trucks SET {placeholders} WHERE id = ?"
        self.db.conn.execute(query, list(data.values()) + [truck_id])
        self.db.conn.commit()

    def delete_truck(self, truck_id):
        self.db.conn.execute("DELETE FROM trucks WHERE id = ?", (truck_id,))
        self.db.conn.commit()

    # --- Fleet financials & alerts ---
    def get_fleet_financials(self, month_year):
        """Calculează costurile totale ale flotei pe o lună (Leasing + Mentenanță)."""
        res = self.db.conn.execute("SELECT SUM(monthly_rate) FROM trucks WHERE active_status = 1").fetchone()
        total_leasing = res[0] or 0

        query = "SELECT SUM(cost) FROM maintenance WHERE SUBSTR(date, 4, 7) = ?"
        res = self.db.conn.execute(query, (month_year,)).fetchone()
        total_maint = res[0] or 0

        return total_leasing, total_maint

    def get_truck_alerts(self):
        """Detectează camioanele care necesită atenție (Asigurări, ITP, Service)."""
        today = datetime.now()
        alerts = []
        rows = self.db.conn.execute("SELECT * FROM trucks WHERE active_status = 1").fetchall()

        for t in rows:
            # Alertă ITP/Asigurare
            for date_key in ('insurance_expiry', 'inspection_expiry'):
                try:
                    val = t[date_key]
                    if val:
                        expiry = datetime.strptime(val, "%d/%m/%Y")
                        diff = (expiry - today).days
                        if diff < 10:
                            alerts.append({"type": "RED", "msg": f"Camion {t['plate_number']}: {date_key} expira in {diff} zile!"})
                except Exception:
                    # malformed date or missing -> skip
                    continue

            # Alertă Service (KM)
            try:
                if t['maintenance_due'] and t['mileage'] is not None and t['mileage'] >= t['maintenance_due']:
                    alerts.append({"type": "RED", "msg": f"Camion {t['plate_number']}: Service necesar (KM depasiti)!"})
            except Exception:
                continue

        return alerts

    # --- Maintenance ---
    def get_maintenance(self, truck_id):
        return self.db.conn.execute(
            "SELECT id, date, type, km_at_service, cost, description FROM maintenance WHERE truck_id = ? ORDER BY date DESC",
            (truck_id,)
        ).fetchall()

    def add_maintenance(self, truck_id, date, mtype, description, km_at_service, cost):
        cursor = self.db.conn.execute(
            "INSERT INTO maintenance (truck_id, date, type, description, km_at_service, cost) VALUES (?,?,?,?,?,?)",
            (truck_id, date, mtype, description, km_at_service, cost)
        )
        self.db.conn.commit()
        return cursor.lastrowid

    # --- Expenses ---
    def ensure_expenses_table(self):
        self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                truck_id INTEGER,
                date TEXT,
                category TEXT,
                description TEXT,
                amount REAL
            );
        """)
        self.db.conn.commit()

    def get_expenses(self, truck_id):
        return self.db.conn.execute(
            "SELECT id, date, category, amount, description FROM expenses WHERE truck_id = ? ORDER BY date DESC",
            (truck_id,)
        ).fetchall()

    def add_expense(self, truck_id, date, category, description, amount):
        cursor = self.db.conn.execute(
            "INSERT INTO expenses (truck_id, date, category, description, amount) VALUES (?,?,?,?,?)",
            (truck_id, date, category, description, amount)
        )
        self.db.conn.commit()
        return cursor.lastrowid
