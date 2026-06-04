import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
from database.schema import (
    INDEX_ROUTE_HISTORY_V2_CREATED,
    INDEX_ROUTE_HISTORY_V2_FINGERPRINT,
    INDEX_ROUTE_HISTORY_V2_LAST_CALCULATED,
    INDEX_ROUTE_HISTORY_V2_PROFILE,
    INDEX_ROUTE_HISTORY_V2_TRUCK,
    INDEX_ROUTE_EVENTS_ROUTE,
    INDEX_ROUTE_EVENTS_TYPE,
    INDEX_TRUCK_ROUTE_ASSIGNMENTS_ROUTE,
    INDEX_TRUCK_ROUTE_ASSIGNMENTS_STATUS,
    INDEX_TRUCK_ROUTE_ASSIGNMENTS_TRUCK,
    INDEX_TRIPS_DATE,
    INDEX_TRIPS_TRUCK,
    TABLE_ALERTS,
    TABLE_EMAIL_LOGS,
    TABLE_INVOICES,
    TABLE_MAINTENANCE_RECORDS,
    TABLE_MAINTENANCE_SCHEDULES,
    TABLE_TRUCK_HEALTH_SCORES,
    TABLE_OPERATION_EVENTS,
    TABLE_ROUTE_HISTORY_V2,
    TABLE_ROUTE_EVENTS,
    TABLE_SETTINGS,
    TABLE_TRIPS,
    TABLE_TRIP_STATUS_HISTORY,
    TABLE_TRUCKS,
    TABLE_TRUCK_ROUTE_ASSIGNMENTS,
    TABLE_DRIVERS,
    TABLE_DRIVER_TRUCK_ASSIGNMENTS,
    INDEX_ALERTS_TYPE,
    INDEX_ALERTS_TRUCK,
    INDEX_ALERTS_RESOLVED,
    INDEX_DRIVERS_ACTIVE,
    INDEX_MAINTENANCE_RECORDS_TRUCK,
    INDEX_MAINTENANCE_RECORDS_TYPE,
    INDEX_MAINTENANCE_RECORDS_DATE,
    INDEX_MAINTENANCE_SCHEDULES_TRUCK,
    INDEX_MAINTENANCE_SCHEDULES_ACTIVE,
    INDEX_OPERATION_EVENTS_TYPE,
    INDEX_TRIP_STATUS_HISTORY_TRIP,
    INDEX_DTA_DRIVER,
    INDEX_DTA_TRUCK,
    TABLE_TACHO_IMPORTS,
    TABLE_TACHO_DRIVER_ACTIVITY,
    TABLE_TACHO_VEHICLE_DATA,
    INDEX_TACHO_DRIVER_DATE,
    INDEX_TACHO_VEHICLE_TRUCK,
    INDEX_TACHO_IMPORTS_HASH,
    ALTER_TRUCKS_ADD_TRACKING_DEVICE_ID,
)


class DatabaseManager:
    def __init__(self, db_path):
        # Conectare la baza de date
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        # Row_factory permite accesarea coloanelor prin nume: trip['truck_number']
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    @staticmethod
    def row_to_dict(row):
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def rows_to_dicts(rows):
        return [dict(r) for r in rows] if rows else []

    def _init_db(self):
        """Creează tabelele și indecșii necesari."""
        self.conn.execute(TABLE_TRIPS)
        self.conn.execute(TABLE_INVOICES)
        self.conn.execute(TABLE_TRUCKS)
        self.conn.execute(TABLE_ROUTE_HISTORY_V2)
        self.conn.execute(INDEX_ROUTE_HISTORY_V2_CREATED)
        self.conn.execute(INDEX_ROUTE_HISTORY_V2_LAST_CALCULATED)
        self.conn.execute(INDEX_ROUTE_HISTORY_V2_TRUCK)
        self.conn.execute(INDEX_ROUTE_HISTORY_V2_PROFILE)
        self.conn.execute(INDEX_ROUTE_HISTORY_V2_FINGERPRINT)
        self.conn.execute(TABLE_ROUTE_EVENTS)
        self.conn.execute(TABLE_TRUCK_ROUTE_ASSIGNMENTS)
        self.conn.execute(INDEX_ROUTE_EVENTS_ROUTE)
        self.conn.execute(INDEX_ROUTE_EVENTS_TYPE)
        self.conn.execute(INDEX_TRUCK_ROUTE_ASSIGNMENTS_TRUCK)
        self.conn.execute(INDEX_TRUCK_ROUTE_ASSIGNMENTS_ROUTE)
        self.conn.execute(INDEX_TRUCK_ROUTE_ASSIGNMENTS_STATUS)
        self.conn.execute(INDEX_TRIPS_DATE)
        self.conn.execute(INDEX_TRIPS_TRUCK)
        self.conn.execute(TABLE_SETTINGS)
        self.conn.execute(TABLE_EMAIL_LOGS)
        # Operations Engine tables
        self.conn.execute(TABLE_ALERTS)
        self.conn.execute(TABLE_OPERATION_EVENTS)
        self.conn.execute(TABLE_TRIP_STATUS_HISTORY)
        self.conn.execute(INDEX_ALERTS_TYPE)
        self.conn.execute(INDEX_ALERTS_TRUCK)
        self.conn.execute(INDEX_ALERTS_RESOLVED)
        self.conn.execute(INDEX_OPERATION_EVENTS_TYPE)
        self.conn.execute(INDEX_TRIP_STATUS_HISTORY_TRIP)

        # Fleet Maintenance tables
        self.conn.execute(TABLE_MAINTENANCE_RECORDS)
        self.conn.execute(TABLE_MAINTENANCE_SCHEDULES)
        self.conn.execute(TABLE_TRUCK_HEALTH_SCORES)
        self.conn.execute(INDEX_MAINTENANCE_RECORDS_TRUCK)
        self.conn.execute(INDEX_MAINTENANCE_RECORDS_TYPE)
        self.conn.execute(INDEX_MAINTENANCE_RECORDS_DATE)
        self.conn.execute(INDEX_MAINTENANCE_SCHEDULES_TRUCK)
        self.conn.execute(INDEX_MAINTENANCE_SCHEDULES_ACTIVE)

        # Drivers table
        self.conn.execute(TABLE_DRIVERS)
        self.conn.execute(INDEX_DRIVERS_ACTIVE)

        # Driver-Truck assignments table
        self.conn.execute(TABLE_DRIVER_TRUCK_ASSIGNMENTS)
        self.conn.execute(INDEX_DTA_DRIVER)
        self.conn.execute(INDEX_DTA_TRUCK)

        # Tachograph tables
        self.conn.execute(TABLE_TACHO_IMPORTS)
        self.conn.execute(TABLE_TACHO_DRIVER_ACTIVITY)
        self.conn.execute(TABLE_TACHO_VEHICLE_DATA)
        self.conn.execute(INDEX_TACHO_DRIVER_DATE)
        self.conn.execute(INDEX_TACHO_VEHICLE_TRUCK)
        self.conn.execute(INDEX_TACHO_IMPORTS_HASH)

        self.conn.commit()
        # Migrate legacy maintenance table to maintenance_records (if both exist)
        try:
            has_legacy = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance'"
            ).fetchone()
            has_records = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_records'"
            ).fetchone()
            if has_legacy and has_records:
                migrated = self.conn.execute("""
                    INSERT OR IGNORE INTO maintenance_records
                    (truck_id, maintenance_type, date, km, cost, notes, created_at)
                    SELECT truck_id, type, date, km_at_service, cost, description,
                           COALESCE(date, datetime('now'))
                    FROM maintenance
                """).rowcount
                if migrated > 0:
                    self.conn.execute("DROP TABLE maintenance")
                    logger.info("Migrated %d legacy maintenance records and dropped old table", migrated)
        except Exception:
            pass
        # Migrations for trips table
        try:
            cols = [r[1] for r in self.conn.execute("PRAGMA table_info(trips)").fetchall()]
            if 'context_json' not in cols:
                try:
                    self.conn.execute("ALTER TABLE trips ADD COLUMN context_json TEXT")
                except Exception:
                    pass
            if 'route_history_v2_id' not in cols:
                try:
                    self.conn.execute("ALTER TABLE trips ADD COLUMN route_history_v2_id INTEGER REFERENCES route_history_v2(id)")
                except Exception:
                    pass
            if 'truck_consumption_l_per_100km' not in cols:
                try:
                    self.conn.execute("ALTER TABLE trips ADD COLUMN truck_consumption_l_per_100km REAL")
                except Exception:
                    pass
        except Exception:
            pass
        # Migration: tachograph_expiry on trucks
        try:
            truck_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(trucks)").fetchall()]
            if 'tachograph_expiry' not in truck_cols:
                try:
                    self.conn.execute("ALTER TABLE trucks ADD COLUMN tachograph_expiry TEXT")
                except Exception:
                    pass
        except Exception:
            pass
        # Migration: tracking_device_id on trucks
        try:
            truck_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(trucks)").fetchall()]
            if 'tracking_device_id' not in truck_cols:
                try:
                    self.conn.execute(ALTER_TRUCKS_ADD_TRACKING_DEVICE_ID)
                except Exception:
                    pass
        except Exception:
            pass
        # Migration: driver_id on trips (FK → drivers)
        try:
            trip_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(trips)").fetchall()]
            if 'driver_id' not in trip_cols:
                try:
                    self.conn.execute("ALTER TABLE trips ADD COLUMN driver_id INTEGER REFERENCES drivers(id)")
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.conn.commit()
        except Exception:
            pass

    # --- OPERAȚIUNI CURSE (TRIPS) ---

    # @deprecated — use TripService.add() → TripRepository.create() instead
    def add_trip(self, data: dict):
        """Salvează o cursă nouă și returnează ID-ul generat."""
        # Use a single transaction to write the trip (single full write)
        keys = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        query = f"INSERT INTO trips ({keys}) VALUES ({placeholders})"
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(query, tuple(data.values()))
            trip_id = cur.lastrowid
            cur.execute("COMMIT")
            return trip_id
        except Exception:
            try:
                cur.execute("ROLLBACK")
            except Exception:
                pass
            raise

    # @deprecated — use TripService.update() → TripRepository.update() instead
    def update_trip(self, trip_id, data: dict):
        """Actualizează datele unei curse existente."""
        placeholders = ", ".join([f"{key} = ?" for key in data.keys()])
        query = f"UPDATE trips SET {placeholders} WHERE id = ?"
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(query, list(data.values()) + [trip_id])
            cur.execute("COMMIT")
        except Exception:
            try:
                cur.execute("ROLLBACK")
            except Exception:
                pass
            raise

    # @deprecated — unused; use TripService + TripStatusEngine
    def update_status(self, trip_id, status):
        """Actualizează doar statusul unei curse."""
        self.conn.execute("UPDATE trips SET status = ? WHERE id = ?", (status, trip_id))
        self.conn.commit()

    # @deprecated — use TripService.delete() → TripRepository.delete() instead
    def delete_trip(self, trip_id):
        """Șterge o cursă permanent."""
        self.conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        self.conn.commit()

    def get_all_trips(self, limit: int = 500):
        """Returnează curse, limitat implicit la 500."""
        return self.rows_to_dicts(self.conn.execute(
            f"SELECT * FROM trips ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall())

    def get_trip_by_id(self, trip_id):
        """Caută o singură cursă după ID."""
        return self.row_to_dict(self.conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone())

    # --- FILTRE ȘI CĂUTARE ---

    def get_filtered_trips(self, search="", truck="", status="", limit: int = 200):
        """Filtrare dinamică pentru istoricul curselor — cu paginare."""
        query = "SELECT * FROM trips WHERE 1=1"
        params = []
        
        if search:
            query += " AND (client_name LIKE ? OR driver_name LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if truck:
            query += " AND truck_number = ?"
            params.append(truck)
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self.rows_to_dicts(self.conn.execute(query, params).fetchall())

    def get_unique_lists(self):
        """Listele de camioane și șoferi pentru dropdown-uri."""
        trucks = [r[0] for r in self.conn.execute("SELECT DISTINCT truck_number FROM trips WHERE truck_number IS NOT NULL").fetchall()]
        drivers = [r[0] for r in self.conn.execute("SELECT DISTINCT driver_name FROM trips WHERE driver_name IS NOT NULL").fetchall()]
        return trucks, drivers

    # --- INVOICE LINKING ---

    def create_invoice_record(self, trip_id, inv_number, amount, due_date):
        """Leagă o factură de o cursă."""
        try:
            self.conn.execute("""
                INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status)
                VALUES (?, ?, ?, ?, ?, 'Unpaid')
            """, (trip_id, inv_number, datetime.now().strftime("%Y-%m-%d"), due_date, amount))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def mark_invoice_as_paid(self, trip_id):
        """Confirmă plata."""
        self.conn.execute("UPDATE invoices SET status = 'Paid' WHERE trip_id = ?", (trip_id,))
        self.conn.commit()

    # --- DASHBOARD & ANALYTICS ---

    def get_stats_by_period(self, start=None, end=None):
        """Statistici calculate pe o perioadă (format date: YYYY-MM-DD)."""
        query = f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN net_profit > 0 THEN 1 ELSE 0 END) as profitable,
                SUM(CASE WHEN net_profit <= 0 THEN 1 ELSE 0 END) as losing,
                SUM(net_profit) as total_p,
                SUM(distance_km) as total_km,
                SUM(total_price_eur) as total_rev
            FROM trips
            WHERE 1=1
        """
        params = []
        if start and end:
            query += " AND created_at BETWEEN ? AND ?"
            params.extend([start, end])
        
        return self.row_to_dict(self.conn.execute(query, params).fetchone())

    def get_extended_stats(self):
        """Statistici globale + cea mai bună lună."""
        stats = self.get_stats_by_period()
        best_month = self.row_to_dict(self.conn.execute("""
            SELECT SUBSTR(created_at, 1, 7) as month, SUM(net_profit) as m_profit 
            FROM trips 
            GROUP BY month 
            ORDER BY m_profit DESC LIMIT 1
        """).fetchone())
        return stats, best_month

    def get_advanced_analytics(self):
        """Top performeri: Camion, Șofer, Lună."""
        bt = self.row_to_dict(self.conn.execute("SELECT truck_number, SUM(net_profit) as p FROM trips GROUP BY truck_number ORDER BY p DESC LIMIT 1").fetchone())
        bd = self.row_to_dict(self.conn.execute("SELECT driver_name, SUM(net_profit) as p FROM trips GROUP BY driver_name ORDER BY p DESC LIMIT 1").fetchone())
        bm = self.row_to_dict(self.conn.execute("SELECT SUBSTR(created_at, 1, 7) as month, SUM(net_profit) as m_profit FROM trips GROUP BY month ORDER BY m_profit DESC LIMIT 1").fetchone())
        return bt, bd, bm

    def get_dashboard_charts(self):
        """Date pentru graficul evolutiv (ultimele 6 luni)."""
        top_clients = self.rows_to_dicts(self.conn.execute("SELECT client_name, SUM(net_profit) as p FROM trips GROUP BY client_name ORDER BY p DESC LIMIT 5").fetchall())
        monthly = self.conn.execute("SELECT SUBSTR(created_at, 1, 7) as month, SUM(net_profit) as p FROM trips GROUP BY month ORDER BY id DESC LIMIT 6").fetchall()
        return top_clients, self.rows_to_dicts(monthly[::-1])

    def get_available_years(self):
        """Anii disponibili pentru filtre."""
        return [r[0] for r in self.conn.execute("SELECT DISTINCT SUBSTR(created_at, 1, 4) as year FROM trips ORDER BY year DESC").fetchall() if r[0]]

    def get_kpi_stats(self):
        """Calculează cifrele cheie pentru luna curentă."""
        current_month = datetime.now().strftime("%Y-%m")
        
        # 1. Venit și Profit Luna Curentă
        m_stats = self.conn.execute("""
            SELECT SUM(total_price_eur), SUM(net_profit), SUM(distance_km) 
            FROM trips WHERE created_at LIKE ?
        """, (f"%{current_month}%",)).fetchone()

        # 2. Facturi neplătite
        unpaid = self.conn.execute("SELECT COUNT(*) FROM invoices WHERE status = 'Unpaid'").fetchone()[0]

        # 3. Curse Active (orice nu e 'Paid')
        active = self.conn.execute("SELECT COUNT(*) FROM trips WHERE status NOT IN ('Paid', 'Cancelled')").fetchone()[0]

        return {
            "rev": m_stats[0] or 0,
            "profit": m_stats[1] or 0,
            "km": m_stats[2] or 0,
            "unpaid": unpaid,
            "active": active
        }

    def get_overdue_data(self):
        today = datetime.now()
        alerts = []
        total_overdue_amount = 0

        query = """
            SELECT t.id, t.client_name, i.invoice_number, i.due_date, i.total_amount
            FROM trips t
            JOIN invoices i ON t.id = i.trip_id
            WHERE i.status = 'Unpaid'
        """
        try:
            rows = self.conn.execute(query).fetchall()
            for r in rows:
                due_dt = datetime.strptime(r['due_date'], "%Y-%m-%d")
                if today > due_dt:
                    days_late = (today - due_dt).days
                    total_overdue_amount += r['total_amount']
                    alerts.append({
                        "type": "RED",
                        "msg": f"Factura {r['invoice_number']} ({r['client_name']}) intarziata cu {days_late} zile!"
                    })
                elif (due_dt - today).days <= 3:
                    alerts.append({
                        "type": "YELLOW",
                        "msg": f"Factura {r['invoice_number']} expira in {(due_dt - today).days} zile."
                    })
        except Exception as e:
            logger.error("SQL Overdue error: %s", e)

        neg_margin = self.conn.execute("SELECT id, truck_number FROM trips WHERE net_profit < 0 AND status != 'Paid'").fetchall()
        for nm in neg_margin:
            alerts.append({"type": "RED", "msg": f"ATENTIE: Cursa #{nm['id']} ({nm['truck_number']}) are profit NEGATIV!"})

        return alerts, total_overdue_amount

    def get_analytics_data(self, from_date=None, to_date=None):
        """Date grupate pentru grafice — optional date range filtering."""
        date_clause = ""
        date_params = []
        if from_date and to_date:
            date_clause = """
                WHERE LENGTH(created_at) >= 10
                  AND created_at >= ?
                  AND created_at <= ?
            """
            date_params = [from_date, to_date]

        per_truck = self.rows_to_dicts(self.conn.execute(
            f"SELECT truck_number, SUM(net_profit) as p FROM trips {date_clause} GROUP BY truck_number ORDER BY SUM(net_profit) DESC LIMIT 10",
            date_params).fetchall())
        per_driver = self.rows_to_dicts(self.conn.execute(
            f"SELECT driver_name, SUM(net_profit) as p FROM trips {date_clause} GROUP BY driver_name ORDER BY SUM(net_profit) DESC LIMIT 10",
            date_params).fetchall())
        rev_exp = self.conn.execute(f"""
            SELECT SUBSTR(created_at, 1, 7) as month, 
            SUM(total_price_eur) as rev, 
            SUM(total_price_eur - net_profit) as exp 
            FROM trips {date_clause} GROUP BY month ORDER BY month DESC LIMIT 6
        """, date_params).fetchall()
        return per_truck, per_driver, self.rows_to_dicts(rev_exp[::-1])

    def get_settings(self, keys: List[str]) -> Dict[str, str]:
        rows = self.conn.execute(
            f"SELECT key, value FROM settings WHERE key IN ({','.join('?' * len(keys))})",
            keys,
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def save_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        self.conn.commit()

    def get_setting(self, key: str) -> Optional[str]:
        res = self.get_settings([key])
        return res.get(key) if res else None

    # ── Truck CRUD ────────────────────────────────────────────────────

    def get_all_trucks(self, active_only=False):
        query = "SELECT id, plate_number, model, manufacturer, year, vin, mileage, fuel_consumption, monthly_rate, status, insurance_expiry, inspection_expiry, maintenance_due, active_status FROM trucks"
        params = ()
        if active_only:
            query += " WHERE active_status = 1"
        return self.rows_to_dicts(self.conn.execute(query, params).fetchall())

    def get_truck_by_id(self, truck_id):
        return self.row_to_dict(self.conn.execute(
            "SELECT id, plate_number, model, manufacturer, year, vin, mileage, fuel_consumption, monthly_rate, status, insurance_expiry, inspection_expiry, maintenance_due, active_status FROM trucks WHERE id = ?",
            (truck_id,),
        ).fetchone())

    def add_truck(self, data: dict):
        keys = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        cursor = self.conn.execute(f"INSERT INTO trucks ({keys}) VALUES ({placeholders})", tuple(data.values()))
        self.conn.commit()
        return cursor.lastrowid

    def update_truck(self, truck_id, data: dict):
        placeholders = ", ".join([f"{key} = ?" for key in data.keys()])
        self.conn.execute(f"UPDATE trucks SET {placeholders} WHERE id = ?", list(data.values()) + [truck_id])
        self.conn.commit()

    def delete_truck(self, truck_id):
        self.conn.execute("DELETE FROM trucks WHERE id = ?", (truck_id,))
        self.conn.commit()

    # @deprecated — use TruckRouteAssignmentRepository.get_by_truck() via FleetService
    def get_truck_routes(self, truck_id, status=None):
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
        return self.rows_to_dicts(self.conn.execute(query, params).fetchall())

    # ── Expenses CRUD ─────────────────────────────────────────────────

    def ensure_expenses_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                truck_id INTEGER,
                date TEXT,
                category TEXT,
                description TEXT,
                amount REAL
            );
        """)
        self.conn.commit()

    def get_expenses(self, truck_id):
        return self.rows_to_dicts(self.conn.execute(
            "SELECT id, date, category, amount, description FROM expenses WHERE truck_id = ? ORDER BY date DESC",
            (truck_id,),
        ).fetchall())

    def add_expense(self, truck_id, date, category, description, amount):
        cursor = self.conn.execute(
            "INSERT INTO expenses (truck_id, date, category, description, amount) VALUES (?,?,?,?,?)",
            (truck_id, date, category, description, amount),
        )
        self.conn.commit()
        return cursor.lastrowid

