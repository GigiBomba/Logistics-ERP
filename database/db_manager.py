import sqlite3
from datetime import datetime
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
    TABLE_EMAIL_LOGS,
    TABLE_INVOICES,
    TABLE_MAINTENANCE,
    TABLE_ROUTE_HISTORY_V2,
    TABLE_ROUTE_EVENTS,
    TABLE_SETTINGS,
    TABLE_TRIPS,
    TABLE_TRUCKS,
    TABLE_TRUCK_ROUTE_ASSIGNMENTS,
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
        return [dict(r) for r in rows]

    def _init_db(self):
        """Creează tabelele și indecșii necesari."""
        self.conn.execute(TABLE_TRIPS)
        self.conn.execute(TABLE_INVOICES)
        # Trucks and maintenance tables required by fleet management
        self.conn.execute(TABLE_TRUCKS)
        self.conn.execute(TABLE_MAINTENANCE)
        # Routes tables
        try:
            from database.schema import TABLE_ROUTES, TABLE_ROUTE_HISTORY
            self.conn.execute(TABLE_ROUTES)
            self.conn.execute(TABLE_ROUTE_HISTORY)
        except Exception:
            pass
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
        
        self.conn.commit()
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
        try:
            self.conn.commit()
        except Exception:
            pass

    # --- OPERAȚIUNI CURSE (TRIPS) ---

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

    def update_status(self, trip_id, status):
        """Actualizează doar statusul unei curse."""
        self.conn.execute("UPDATE trips SET status = ? WHERE id = ?", (status, trip_id))
        self.conn.commit()

    def delete_trip(self, trip_id):
        """Șterge o cursă permanent."""
        self.conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        self.conn.commit()

    def get_all_trips(self):
        """Returnează absolut toate cursele."""
        return self.rows_to_dicts(self.conn.execute("SELECT * FROM trips ORDER BY id DESC").fetchall())

    def get_trip_by_id(self, trip_id):
        """Caută o singură cursă după ID."""
        return self.row_to_dict(self.conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone())

    # --- FILTRE ȘI CĂUTARE ---

    def get_filtered_trips(self, search="", truck="", status=""):
        """Filtrare dinamică pentru istoricul curselos."""
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
        
        query += " ORDER BY id DESC"
        return self.rows_to_dicts(self.conn.execute(query, params).fetchall())

    def get_unique_lists(self):
        """Listele de camioane și șoferi pentru dropdown-uri."""
        trucks = [r[0] for r in self.conn.execute("SELECT DISTINCT truck_number FROM trips WHERE truck_number IS NOT NULL").fetchall()]
        drivers = [r[0] for r in self.conn.execute("SELECT DISTINCT driver_name FROM trips WHERE driver_name IS NOT NULL").fetchall()]
        return trucks, drivers

    # --- INVOICE LINKING & WORKFLOW ---

    def create_invoice_record(self, trip_id, inv_number, amount, due_date):
        """Leagă o factură de o cursă și mută statusul în 'Invoiced'."""
        try:
            # Inserăm factura în tabelul invoices
            self.conn.execute("""
                INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status)
                VALUES (?, ?, ?, ?, ?, 'Unpaid')
            """, (trip_id, inv_number, datetime.now().strftime("%d/%m/%Y"), due_date, amount))
            
            # Actualizăm statusul cursei
            self.conn.execute("UPDATE trips SET status = 'Invoiced' WHERE id = ?", (trip_id,))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Dacă există deja o factură pentru acest ID, doar actualizăm statusul cursei
            self.conn.execute("UPDATE trips SET status = 'Invoiced' WHERE id = ?", (trip_id,))
            self.conn.commit()

    def mark_invoice_as_paid(self, trip_id):
        """Confirmă plata: actualizează și factura și cursa."""
        self.conn.execute("UPDATE invoices SET status = 'Paid' WHERE trip_id = ?", (trip_id,))
        self.conn.execute("UPDATE trips SET status = 'Paid' WHERE id = ?", (trip_id,))
        self.conn.commit()

    # --- DASHBOARD & ANALYTICS ---

    def get_stats_by_period(self, start=None, end=None):
        """Statistici calculate pe o perioadă (format date: YYYY-MM-DD)."""
        date_iso = "SUBSTR(created_at, 7, 4) || '-' || SUBSTR(created_at, 4, 2) || '-' || SUBSTR(created_at, 1, 2)"
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
            query += f" AND {date_iso} BETWEEN ? AND ?"
            params.extend([start, end])
        
        return self.row_to_dict(self.conn.execute(query, params).fetchone())

    def get_extended_stats(self):
        """Statistici globale + cea mai bună lună."""
        stats = self.get_stats_by_period()
        best_month = self.row_to_dict(self.conn.execute("""
            SELECT SUBSTR(created_at, 4, 7) as month, SUM(net_profit) as m_profit 
            FROM trips 
            GROUP BY month 
            ORDER BY m_profit DESC LIMIT 1
        """).fetchone())
        return stats, best_month

    def get_advanced_analytics(self):
        """Top performeri: Camion, Șofer, Lună."""
        bt = self.row_to_dict(self.conn.execute("SELECT truck_number, SUM(net_profit) as p FROM trips GROUP BY truck_number ORDER BY p DESC LIMIT 1").fetchone())
        bd = self.row_to_dict(self.conn.execute("SELECT driver_name, SUM(net_profit) as p FROM trips GROUP BY driver_name ORDER BY p DESC LIMIT 1").fetchone())
        bm = self.row_to_dict(self.conn.execute("SELECT SUBSTR(created_at, 4, 7) as month, SUM(net_profit) as m_profit FROM trips GROUP BY month ORDER BY m_profit DESC LIMIT 1").fetchone())
        return bt, bd, bm

    def get_dashboard_charts(self):
        """Date pentru graficul evolutiv (ultimele 6 luni)."""
        top_clients = self.rows_to_dicts(self.conn.execute("SELECT client_name, SUM(net_profit) as p FROM trips GROUP BY client_name ORDER BY p DESC LIMIT 5").fetchall())
        monthly = self.conn.execute("SELECT SUBSTR(created_at, 4, 7) as month, SUM(net_profit) as p FROM trips GROUP BY month ORDER BY id DESC LIMIT 6").fetchall()
        return top_clients, self.rows_to_dicts(monthly[::-1])

    def get_available_years(self):
        """Anii disponibili pentru filtre."""
        return [r[0] for r in self.conn.execute("SELECT DISTINCT SUBSTR(created_at, 7, 4) as year FROM trips ORDER BY year DESC").fetchall() if r[0]]

    def get_kpi_stats(self):
        """Calculează cifrele cheie pentru luna curentă."""
        current_month = datetime.now().strftime("%m/%Y")
        
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

    def get_analytics_data(self):
        """Date grupate pentru grafice."""
        per_truck = self.rows_to_dicts(self.conn.execute("SELECT truck_number, SUM(net_profit) as p FROM trips GROUP BY truck_number ORDER BY SUM(net_profit) DESC LIMIT 10").fetchall())
        per_driver = self.rows_to_dicts(self.conn.execute("SELECT driver_name, SUM(net_profit) as p FROM trips GROUP BY driver_name ORDER BY SUM(net_profit) DESC LIMIT 10").fetchall())
        rev_exp = self.conn.execute("""
            SELECT SUBSTR(created_at, 4, 7) as month, 
            SUM(total_price_eur) as rev, 
            SUM(total_price_eur - net_profit) as exp 
            FROM trips GROUP BY month ORDER BY id DESC LIMIT 6
        """).fetchall()
        return per_truck, per_driver, self.rows_to_dicts(rev_exp[::-1])

    def get_overdue_data(self):
        """Detecteaza facturile neplatite care au depasit scadenta."""
        today = datetime.now()
        alerts = []
        total_overdue_amount = 0
        
        # CORECTIE: Am scos t.margin_percent din SELECT pentru ca nu exista in baza de date
        query = """
            SELECT t.id, t.client_name, i.invoice_number, i.due_date, i.total_amount
            FROM trips t
            JOIN invoices i ON t.id = i.trip_id
            WHERE i.status = 'Unpaid'
        """
        try:
            rows = self.conn.execute(query).fetchall()
            for r in rows:
                due_dt = datetime.strptime(r['due_date'], "%d/%m/%Y")
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
            print(f"Eroare SQL Overdue: {e}")

        # Detectare Marja Negativa (bazat pe net_profit care exista in DB)
        neg_margin = self.conn.execute("SELECT id, truck_number FROM trips WHERE net_profit < 0 AND status != 'Paid'").fetchall()
        for nm in neg_margin:
            alerts.append({"type": "RED", "msg": f"ATENTIE: Cursa #{nm['id']} ({nm['truck_number']}) are profit NEGATIV!"})

        return alerts, total_overdue_amount

        for r in rows:
            try:
                due_dt = datetime.strptime(r['due_date'], "%d/%m/%Y")
                if today > due_dt:
                    days_late = (today - due_dt).days
                    total_overdue_amount += r['total_amount']
                    alerts.append({
                        "type": "RED",
                        "msg": f"Factura {r['invoice_number']} ({r['client_name']}) intarziata cu {days_late} zile!",
                        "trip_id": r['id']
                    })
                elif (due_dt - today).days <= 3:
                    alerts.append({
                        "type": "YELLOW",
                        "msg": f"Factura {r['invoice_number']} expira in {(due_dt - today).days} zile.",
                        "trip_id": r['id']
                    })
            except: continue

        # Detectare Marjă Negativă
        neg_margin = self.conn.execute("SELECT id, truck_number FROM trips WHERE net_profit < 0 AND status != 'Paid'").fetchall()
        for nm in neg_margin:
            alerts.append({"type": "RED", "msg": f"ATENTIE: Cursa #{nm['id']} ({nm['truck_number']}) are profit NEGATIV!", "trip_id": nm['id']})

        return alerts, total_overdue_amount

    def add_email_log(self, trip_id, rec, subj, status, err=""):
        self.conn.execute("INSERT INTO email_logs (trip_id, recipient, subject, timestamp, status, error_msg) VALUES (?,?,?,?,?,?)",
                         (trip_id, rec, subj, datetime.now().strftime("%d/%m/%Y %H:%M"), status, err))
        self.conn.commit()

    def update_smtp_setting(self, server, port, user, pwd):
        data = [('smtp_server', server), ('smtp_port', port), ('smtp_user', user), ('smtp_password', pwd)]
        for k, v in data:
            self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (k, v))
        self.conn.commit()

    def get_net_operational_profit(self, month):
        # Profit curse
        trips_profit = self.conn.execute("SELECT SUM(net_profit) FROM trips WHERE SUBSTR(created_at, 4, 7) = ?", (month,)).fetchone()[0] or 0
        
        # Cheltuieli flotă (Leasing)
        leasing = self.conn.execute("SELECT SUM(monthly_rate) FROM trucks WHERE active_status = 1").fetchone()[0] or 0
        
        # Cheltuieli Mentenanță
        maint = self.conn.execute("SELECT SUM(cost) FROM maintenance WHERE SUBSTR(date, 4, 7) = ?", (month,)).fetchone()[0] or 0
        
        return trips_profit - leasing - maint
