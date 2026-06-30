"""Analytics repository — all analytics queries consolidated here.

Extracted from DatabaseManager to reduce the God class. All 33 analytics
methods preserved with identical signatures and SQL.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

logger = logging.getLogger(__name__)


class AnalyticsRepository(BaseRepository):

    _month_col_available: Optional[bool] = None
    _month_check_done: bool = False
    _month_lock: Any = None  # set via threading.Lock() lazily

    def _ensure_month_checked(self) -> None:
        import threading
        if AnalyticsRepository._month_lock is None:
            AnalyticsRepository._month_lock = threading.Lock()
        with AnalyticsRepository._month_lock:
            if AnalyticsRepository._month_check_done:
                return
            try:
                cols = [r[1] for r in self.db.conn.execute("PRAGMA table_info(trips)").fetchall()]
                AnalyticsRepository._month_col_available = "month" in cols
            except Exception:
                AnalyticsRepository._month_col_available = False
                AnalyticsRepository._month_check_done = True  # Don't retry forever
                return
            AnalyticsRepository._month_check_done = True

    def _month_expr(self) -> str:
        self._ensure_month_checked()
        return "month" if self._month_col_available else "SUBSTR(created_at, 1, 7)"

    @staticmethod
    def _date_clause(from_date, to_date):
        if from_date and to_date:
            return ("WHERE created_at >= ? AND created_at <= ?",
                    [from_date, to_date])
        return ("WHERE 1=1", [])

    def get_stats_by_period(self, start=None, end=None):
        """Statistici calculate pe o perioada (format date: YYYY-MM-DD)."""
        query = """
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

        return self._fetchone(query, tuple(params))

    def get_extended_stats(self):
        """Statistici globale + cea mai buna luna."""
        stats = self.get_stats_by_period()
        month_expr = self._month_expr()
        best_month = self._fetchone(
            f"SELECT {month_expr} as month, SUM(net_profit) as m_profit "
            "FROM trips "
            "GROUP BY month "
            "ORDER BY m_profit DESC LIMIT 1"
        )
        return stats, best_month

    def get_advanced_analytics(self):
        """Top performeri: Camion, Sofer, Luna."""
        bt = self._fetchone(
            "SELECT COALESCE(t.plate_number, trips.truck_number) as truck_number, SUM(trips.net_profit) as p "
            "FROM trips LEFT JOIN trucks t ON trips.truck_id = t.id "
            "GROUP BY COALESCE(trips.truck_id, trips.truck_number) "
            "ORDER BY p DESC LIMIT 1"
        )
        bd = self._fetchone(
            "SELECT driver_name, SUM(net_profit) as p FROM trips GROUP BY driver_name ORDER BY p DESC LIMIT 1"
        )
        month_expr = self._month_expr()
        bm = self._fetchone(
            f"SELECT {month_expr} as month, SUM(net_profit) as m_profit FROM trips GROUP BY month ORDER BY m_profit DESC LIMIT 1"
        )
        return bt, bd, bm

    def get_dashboard_charts(self):
        """Date pentru graficul evolutiv (ultimele 6 luni)."""
        top_clients = self._fetchall(
            "SELECT client_name, SUM(net_profit) as p FROM trips GROUP BY client_name ORDER BY p DESC LIMIT 5"
        )
        month_expr = self._month_expr()
        monthly_rows = self.db.conn.execute(
            f"SELECT {month_expr} as month, SUM(net_profit) as p FROM trips GROUP BY month ORDER BY month DESC LIMIT 6"
        ).fetchall()
        monthly = self.db.rows_to_dicts(monthly_rows[::-1])
        return top_clients, monthly

    def get_available_years(self):
        """Anii disponibili pentru filtre."""
        return [r[0] for r in self.db.conn.execute(
            "SELECT DISTINCT SUBSTR(created_at, 1, 4) as year FROM trips ORDER BY year DESC"
        ).fetchall() if r[0]]

    def get_kpi_stats(self):
        """Calculeaza cifrele cheie pentru luna curenta."""
        current_month = datetime.now().strftime("%Y-%m")

        # 1. Venit si Profit Luna Curenta
        m_stats = self.db.conn.execute("""
            SELECT SUM(total_price_eur), SUM(net_profit), SUM(distance_km)
            FROM trips WHERE created_at LIKE ?
        """, (f"%{current_month}%",)).fetchone()
        m_rev = (m_stats[0] or 0) if m_stats else 0
        m_profit = (m_stats[1] or 0) if m_stats else 0
        m_km = (m_stats[2] or 0) if m_stats else 0

        # 2. Facturi neplatite
        unpaid_row = self.db.conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status = 'Unpaid'"
        ).fetchone()
        unpaid = (unpaid_row[0] or 0) if unpaid_row else 0

        # 3. Curse Active (orice nu e 'Paid')
        active_row = self.db.conn.execute(
            "SELECT COUNT(*) FROM trips WHERE status NOT IN ('Paid', 'Cancelled')"
        ).fetchone()
        active = (active_row[0] or 0) if active_row else 0

        return {
            "rev": m_rev,
            "profit": m_profit,
            "km": m_km,
            "unpaid": unpaid,
            "active": active,
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
            rows = self.db.conn.execute(query).fetchall()
            for r in rows:
                due_str = r.get("due_date")
                if not due_str:
                    continue
                try:
                    due_dt = datetime.strptime(str(due_str)[:10], "%Y-%m-%d")
                except (ValueError, TypeError):
                    continue
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

        neg_margin = self.db.conn.execute(
            "SELECT id, truck_number FROM trips WHERE net_profit < 0 AND status != 'Paid'"
        ).fetchall()
        for nm in neg_margin:
            alerts.append({
                "type": "RED",
                "msg": f"ATENTIE: Cursa #{nm['id']} ({nm['truck_number']}) are profit NEGATIV!"
            })

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

        per_truck = self._fetchall(
            f"SELECT COALESCE(t.plate_number, trips.truck_number) as truck_number, SUM(trips.net_profit) as p "
            f"FROM trips LEFT JOIN trucks t ON trips.truck_id = t.id {date_clause} "
            f"GROUP BY COALESCE(trips.truck_id, trips.truck_number) "
            f"ORDER BY SUM(trips.net_profit) DESC LIMIT 10",
            tuple(date_params))
        per_driver = self._fetchall(
            f"SELECT driver_name, SUM(net_profit) as p FROM trips {date_clause} GROUP BY driver_name ORDER BY SUM(net_profit) DESC LIMIT 10",
            tuple(date_params))
        rev_exp_rows = self.db.conn.execute(f"""
            SELECT {self._month_expr()} as month,
            SUM(total_price_eur) as rev,
            SUM(total_price_eur - net_profit) as exp
            FROM trips {date_clause} GROUP BY month ORDER BY month DESC LIMIT 6
        """, tuple(date_params)).fetchall()
        rev_exp = self.db.rows_to_dicts(rev_exp_rows[::-1])
        return per_truck, per_driver, rev_exp

    # ── Comprehensive Analytics Queries ──────────────────────────────

    def get_financial_analytics(self, from_date=None, to_date=None):
        """Revenue, profit, margin over time by month."""
        clause, params = self._date_clause(from_date, to_date)
        month_expr = self._month_expr()
        monthly = self._fetchall(f"""
            SELECT {month_expr} AS month,
                   SUM(total_price_eur) AS revenue,
                   SUM(net_profit) AS profit,
                   AVG(CASE WHEN total_price_eur > 0 THEN net_profit * 100.0 / total_price_eur END) AS margin_pct
            FROM trips {clause}
            GROUP BY month ORDER BY month ASC LIMIT 24
        """, tuple(params))
        return monthly

    def get_revenue_by_client(self, from_date=None, to_date=None):
        clause, params = self._date_clause(from_date, to_date)
        return self._fetchall(f"""
            SELECT COALESCE(NULLIF(client_name, ''), 'Unknown') AS client,
                   SUM(total_price_eur) AS revenue,
                   SUM(net_profit) AS profit,
                   COUNT(*) AS trip_count
            FROM trips {clause}
            GROUP BY COALESCE(NULLIF(client_name, ''), 'Unknown')
            ORDER BY revenue DESC LIMIT 10
        """, tuple(params))

    def get_revenue_by_country(self, from_date=None, to_date=None):
        clause, params = self._date_clause(from_date, to_date)
        return self._fetchall(f"""
            SELECT COALESCE(NULLIF(delivery_country, ''), NULLIF(loading_country, ''), 'Unknown') AS country,
                   SUM(total_price_eur) AS revenue,
                   COUNT(*) AS trip_count
            FROM trips {clause}
            GROUP BY COALESCE(NULLIF(delivery_country, ''), NULLIF(loading_country, ''), 'Unknown')
            ORDER BY revenue DESC LIMIT 10
        """, tuple(params))

    def get_route_profitability(self, from_date=None, to_date=None):
        clause, params = self._date_clause(from_date, to_date)
        return self._fetchall(f"""
            SELECT COALESCE(NULLIF(place_of_loading, ''), 'Route') || ' → ' ||
                   COALESCE(NULLIF(delivery_country, ''), COALESCE(NULLIF(loading_country, ''), 'Dest'))
                   AS route_label,
                   AVG(distance_km) AS avg_km,
                   AVG(net_profit) AS avg_profit,
                   AVG(CASE WHEN distance_km > 0 THEN net_profit / distance_km END) AS profit_per_km,
                   AVG(CASE WHEN distance_km > 0 THEN fuel_cost / distance_km END) AS fuel_per_km,
                   COUNT(*) AS trip_count
            FROM trips {clause}
            GROUP BY 1 ORDER BY avg_profit DESC LIMIT 15
        """, tuple(params))

    def get_client_analytics(self, from_date=None, to_date=None):
        clause, params = self._date_clause(from_date, to_date)
        return self._fetchall(f"""
            SELECT COALESCE(NULLIF(client_name, ''), 'Unknown') AS client,
                   COUNT(*) AS trip_count,
                   SUM(total_price_eur) AS revenue,
                   SUM(net_profit) AS profit,
                   ROUND(AVG(JULIANDAY(COALESCE(payment_date, 'now')) - JULIANDAY(created_at)), 1) AS avg_payment_delay_days
            FROM trips {clause}
            GROUP BY COALESCE(NULLIF(client_name, ''), 'Unknown')
            ORDER BY profit DESC LIMIT 12
        """, tuple(params))

    def get_fleet_analytics(self, from_date=None, to_date=None):
        clause, params = self._date_clause(from_date, to_date)
        truck_stats = self._fetchall(f"""
            SELECT COALESCE(t.plate_number, trips.truck_number, 'Unknown') AS truck,
                   COUNT(*) AS trip_count,
                   SUM(trips.distance_km) AS total_km,
                   SUM(trips.net_profit) AS profit,
                   AVG(trips.truck_consumption_l_per_100km) AS avg_consumption,
                   SUM(trips.fuel_cost) AS total_fuel_cost
            FROM trips LEFT JOIN trucks t ON trips.truck_id = t.id {clause}
            GROUP BY COALESCE(t.plate_number, trips.truck_number, 'Unknown')
            ORDER BY profit DESC LIMIT 15
        """, tuple(params))
        return truck_stats

    def get_driver_analytics(self, from_date=None, to_date=None):
        clause, params = self._date_clause(from_date, to_date)
        return self._fetchall(f"""
            SELECT COALESCE(NULLIF(driver_name, ''), 'Unassigned') AS driver,
                   COUNT(*) AS trip_count,
                   SUM(distance_km) AS total_km,
                   SUM(net_profit) AS profit
            FROM trips {clause}
            GROUP BY COALESCE(NULLIF(driver_name, ''), 'Unassigned')
            ORDER BY profit DESC LIMIT 12
        """, tuple(params))

    def get_driver_comparison(self, from_date=None, to_date=None):
        """Driver comparison table: all metrics per driver for tabular view.

        Returns: driver, trip_count, total_km, revenue, profit, profit_per_km.
        Excludes Unassigned drivers.
        """
        clause, params = self._date_clause(from_date, to_date)
        return self._fetchall(f"""
            SELECT COALESCE(NULLIF(driver_name, ''), 'Driver') AS driver,
                   COUNT(*) AS trip_count,
                   COALESCE(SUM(distance_km), 0) AS total_km,
                   COALESCE(SUM(total_price_eur), 0) AS revenue,
                   COALESCE(SUM(net_profit), 0) AS profit,
                   CASE WHEN SUM(distance_km) > 0
                        THEN ROUND(SUM(net_profit) * 1.0 / SUM(distance_km), 4)
                        ELSE 0 END AS profit_per_km
            FROM trips {clause}
            WHERE driver_name IS NOT NULL AND driver_name != ''
              AND driver_name != 'Unassigned'
            GROUP BY driver_name
            ORDER BY profit DESC LIMIT 15
        """, tuple(params))

    def get_document_analytics(self):
        inv_row = self._fetchone("SELECT COUNT(*) AS cnt FROM invoices")
        inv_count = (inv_row.get("cnt", 0) or 0) if inv_row else 0
        cmr_row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM documents WHERE tags LIKE '%cmr%'"
        )
        cmr_count = (cmr_row.get("cnt", 0) or 0) if cmr_row else 0
        expiring = self._fetchall(
            "SELECT title, expiry_date FROM documents WHERE expiry_date IS NOT NULL "
            "AND expiry_date <= date('now', '+30 days') ORDER BY expiry_date ASC LIMIT 10"
        )
        total_row = self._fetchone("SELECT COUNT(*) AS cnt FROM documents")
        total_docs = (total_row.get("cnt", 0) or 0) if total_row else 0
        return {
            "invoice_count": inv_count,
            "cmr_count": cmr_count,
            "total_docs": total_docs,
            "expiring": expiring or [],
        }

    def get_maintenance_alerts(self):
        return self._fetchall("""
            SELECT t.plate_number AS truck, s.maintenance_type AS description,
                   s.fixed_expiry_date AS next_due_date, s.interval_km AS next_due_mileage
            FROM maintenance_schedules s
            JOIN trucks t ON t.id = s.truck_id
            WHERE s.active = 1
            ORDER BY s.fixed_expiry_date ASC LIMIT 10
        """)

    # ── Analytics 2.0: Additional query methods ──────────────────────

    def get_client_growth(self, months: int = 12, from_date=None, to_date=None):
        extra = ""
        extra_params = []
        if from_date and to_date:
            extra = " AND created_at >= ? AND created_at <= ?"
            extra_params = [from_date, to_date]
        return self._fetchall(
            f"SELECT SUBSTR(created_at, 1, 7) AS month, COUNT(*) AS new_clients "
            f"FROM clients WHERE is_active = 1{extra} "
            "GROUP BY month ORDER BY month ASC LIMIT ?",
            tuple(extra_params + [months]),
        )

    def get_truck_utilization(self) -> list:
        return self._fetchall("""
            SELECT t.plate_number AS truck,
                   COUNT(tr.id) AS trip_count,
                   COALESCE(SUM(tr.distance_km), 0) AS total_km,
                   MAX(tr.created_at) AS last_trip,
                   MIN(tr.created_at) AS first_trip
            FROM trucks t LEFT JOIN trips tr ON t.id = tr.truck_id
            WHERE t.active_status = 1
            GROUP BY t.id ORDER BY trip_count DESC LIMIT 15
        """)

    def get_document_upload_trend(self, months: int = 12):
        return self._fetchall(
            "SELECT SUBSTR(uploaded_at, 1, 7) AS month, COUNT(*) AS count, "
            "SUM(CASE WHEN category IN ('invoices','trips','cmr') THEN 1 ELSE 0 END) AS doc_count, "
            "SUM(CASE WHEN category = 'cmr' THEN 1 ELSE 0 END) AS cmr_count "
            "FROM documents WHERE is_archived = 0 "
            "GROUP BY month ORDER BY month ASC LIMIT ?",
            (months,),
        )

    def get_driver_tacho_violations(self):
        return self._fetchall("""
            SELECT d.name AS driver, COUNT(da.id) AS activity_days,
                   COALESCE(SUM(da.violations), 0) AS total_violations,
                   COALESCE(SUM(da.driving_minutes) / 60.0, 0) AS driving_hours,
                   COALESCE(SUM(da.rest_minutes) / 60.0, 0) AS rest_hours
            FROM tacho_driver_activity da
            JOIN drivers d ON da.driver_id = d.id
            WHERE da.activity_date >= DATE('now', '-90 days')
            GROUP BY da.driver_id ORDER BY total_violations DESC LIMIT 15
        """)

    def get_profit_per_km_by_country(self):
        return self._fetchall("""
            SELECT delivery_country AS country, COUNT(*) AS trip_count,
                   COALESCE(SUM(net_profit), 0) AS profit,
                   COALESCE(SUM(distance_km), 0) AS total_km,
                   CASE WHEN SUM(distance_km) > 0
                        THEN ROUND(SUM(net_profit) * 1.0 / SUM(distance_km), 4)
                        ELSE 0 END AS profit_per_km
            FROM trips WHERE delivery_country IS NOT NULL AND delivery_country != ''
            GROUP BY delivery_country ORDER BY profit DESC LIMIT 15
        """)

    def get_revenue_concentration(self):
        return self._fetchall("""
            SELECT COALESCE(NULLIF(client_name, ''), 'Unknown') AS client,
                   COALESCE(SUM(total_price_eur), 0) AS revenue,
                   COALESCE(SUM(net_profit), 0) AS profit
            FROM trips GROUP BY client_name ORDER BY revenue DESC
        """)

    def get_driver_profit_per_km(self):
        return self._fetchall("""
            SELECT driver_name, COUNT(*) AS trip_count,
                   COALESCE(SUM(distance_km), 0) AS total_km,
                   COALESCE(SUM(net_profit), 0) AS total_profit,
                   CASE WHEN SUM(distance_km) > 0
                        THEN ROUND(SUM(net_profit) * 1.0 / SUM(distance_km), 4)
                        ELSE 0 END AS profit_per_km
            FROM trips WHERE driver_name IS NOT NULL AND driver_name != ''
            GROUP BY driver_name ORDER BY profit_per_km DESC LIMIT 15
        """)

    def get_monthly_financial_summary(self, months: int = 24, from_date=None, to_date=None):
        month_expr = self._month_expr()
        clause, clause_params = self._date_clause(from_date, to_date)
        return self._fetchall(
            f"SELECT {month_expr} AS month, "
            "COALESCE(SUM(total_price_eur), 0) AS revenue, "
            "COALESCE(SUM(net_profit), 0) AS profit, "
            "COUNT(*) AS trip_count, "
            "CASE WHEN SUM(total_price_eur) > 0 "
            "     THEN ROUND(SUM(net_profit) * 100.0 / SUM(total_price_eur), 1) "
            "     ELSE 0 END AS margin_pct, "
            "SUM(CASE WHEN status IN ('Invoiced', 'Paid') THEN 1 ELSE 0 END) AS invoiced_count, "
            "SUM(CASE WHEN status = 'Paid' THEN 1 ELSE 0 END) AS paid_count "
            f"FROM trips {clause} GROUP BY month ORDER BY month ASC LIMIT ?",
            tuple(list(clause_params) + [months]),
        )

    # ── New Analytics Queries (Phase 2) ───────────────────────────────

    def get_trip_status_distribution(self, from_date=None, to_date=None):
        """Count of trips grouped by status."""
        clause, clause_params = self._date_clause(from_date, to_date)
        return self._fetchall(f"""
            SELECT LOWER(status) AS status, COUNT(*) AS count
            FROM trips {clause} AND status IS NOT NULL AND status != ''
            GROUP BY LOWER(status) ORDER BY count DESC
        """, tuple(clause_params))

    def get_cost_breakdown(self, months: int = 12, from_date=None, to_date=None):
        """Monthly cost breakdown: fuel, toll, salary, extra costs."""
        month_expr = self._month_expr()
        clause, clause_params = self._date_clause(from_date, to_date)
        return self._fetchall(
            f"SELECT {month_expr} AS month, "
            "COALESCE(SUM(fuel_cost), 0) AS fuel_cost, "
            "COALESCE(SUM(toll_cost), 0) AS toll_cost, "
            "COALESCE(SUM(salary_cost), 0) AS salary_cost, "
            "COALESCE(SUM(extra_costs), 0) AS extra_costs, "
            "COALESCE(SUM(total_price_eur), 0) AS revenue, "
            "COALESCE(SUM(net_profit), 0) AS net_profit "
            f"FROM trips {clause} GROUP BY month ORDER BY month ASC LIMIT ?",
            tuple(list(clause_params) + [months]),
        )

    def get_monthly_trip_volume(self, months: int = 12, from_date=None, to_date=None):
        """Number of trips per month."""
        month_expr = self._month_expr()
        clause, clause_params = self._date_clause(from_date, to_date)
        return self._fetchall(
            f"SELECT {month_expr} AS month, COUNT(*) AS trip_count, "
            "COALESCE(SUM(distance_km), 0) AS total_distance, "
            "COALESCE(AVG(distance_km), 0) AS avg_distance "
            f"FROM trips {clause} GROUP BY month ORDER BY month ASC LIMIT ?",
            tuple(list(clause_params) + [months]),
        )

    def get_profit_vs_distance(self, limit: int = 100):
        """Scatter data: net_profit vs distance_km for each trip."""
        return self._fetchall(
            "SELECT distance_km, net_profit, truck_number, driver_name, "
            "COALESCE(NULLIF(place_of_loading, ''), 'Unknown') AS origin, "
            "COALESCE(NULLIF(delivery_country, ''), 'Unknown') AS destination "
            "FROM trips WHERE distance_km IS NOT NULL AND distance_km > 0 "
            "AND net_profit IS NOT NULL ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    def get_truck_age_distribution(self):
        """Distribution of trucks by manufacture year."""
        return self._fetchall("""
            SELECT year AS truck_year, COUNT(*) AS count,
                   COALESCE(SUM(mileage), 0) AS total_mileage
            FROM trucks WHERE year IS NOT NULL AND year != ''
            GROUP BY year ORDER BY year DESC
        """)

    def get_driver_efficiency_trend(self, months: int = 12):
        """Monthly profit per km trend per driver."""
        month_expr = self._month_expr()
        return self._fetchall(
            f"SELECT {month_expr} AS month, "
            "COALESCE(NULLIF(driver_name, ''), 'Unassigned') AS driver, "
            "COUNT(*) AS trip_count, "
            "COALESCE(SUM(distance_km), 0) AS total_distance, "
            "COALESCE(SUM(net_profit), 0) AS total_profit, "
            "CASE WHEN SUM(distance_km) > 0 "
            "     THEN ROUND(SUM(net_profit) * 1.0 / SUM(distance_km), 4) "
            "     ELSE 0 END AS profit_per_km "
            "FROM trips WHERE driver_name IS NOT NULL AND driver_name != '' "
            "GROUP BY month, driver_name ORDER BY month ASC LIMIT ?",
            (months * 15,),
        )

    def get_client_retention(self):
        """Active vs inactive clients with trip counts."""
        return self._fetchall("""
            SELECT c.is_active, COUNT(DISTINCT c.id) AS client_count,
                   COUNT(t.id) AS total_trips,
                   COALESCE(SUM(t.total_price_eur), 0) AS total_revenue
            FROM clients c LEFT JOIN trips t ON c.id = t.client_id
            GROUP BY c.is_active
        """)

    def get_revenue_quarterly(self, quarters: int = 8, from_date=None, to_date=None):
        """Quarterly revenue and profit summary."""
        clause, clause_params = self._date_clause(from_date, to_date)
        return self._fetchall(
            f"SELECT SUBSTR(created_at, 1, 4) || '-Q' || "
            "(CAST(SUBSTR(created_at, 6, 2) AS INTEGER) + 2) / 3 AS quarter, "
            "COALESCE(SUM(total_price_eur), 0) AS revenue, "
            "COALESCE(SUM(net_profit), 0) AS profit, "
            "COUNT(*) AS trip_count "
            f"FROM trips {clause} GROUP BY quarter ORDER BY quarter ASC LIMIT ?",
            tuple(list(clause_params) + [quarters]),
        )

    def get_invoice_aging(self):
        """Invoice aging breakdown: unpaid invoices by overdue days.

        Returns buckets: current (0-30d overdue), 31-60d, 61-90d, 90+ days.
        """
        today = datetime.now()
        d_today = today.strftime("%Y-%m-%d")
        d_30 = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        d_31 = (today - timedelta(days=31)).strftime("%Y-%m-%d")
        d_60 = (today - timedelta(days=60)).strftime("%Y-%m-%d")
        d_61 = (today - timedelta(days=61)).strftime("%Y-%m-%d")
        d_90 = (today - timedelta(days=90)).strftime("%Y-%m-%d")
        return self._fetchone("""
            SELECT
                COALESCE(SUM(CASE WHEN due_date BETWEEN ? AND ? THEN total_amount ELSE 0 END), 0) AS current_bucket,
                COALESCE(SUM(CASE WHEN due_date BETWEEN ? AND ? THEN total_amount ELSE 0 END), 0) AS bucket_31_60,
                COALESCE(SUM(CASE WHEN due_date BETWEEN ? AND ? THEN total_amount ELSE 0 END), 0) AS bucket_61_90,
                COALESCE(SUM(CASE WHEN due_date < ? THEN total_amount ELSE 0 END), 0) AS overdue_bucket,
                COALESCE(SUM(total_amount), 0) AS total_outstanding
            FROM invoices WHERE status = 'Unpaid'
        """, (d_30, d_today, d_60, d_31, d_90, d_61, d_90))

    def get_client_payment_timeline(self, from_date=None, to_date=None):
        """Per-client payment history: last 6 invoices with payment delay.

        Returns rows: client_name, invoice_number, issue_date, due_date,
        total_amount, status, payment_date, delay_days.
        Ordered by client revenue DESC, then invoice issue_date DESC.
        Limited to top 5 clients by total invoice amount.
        """
        clause = "WHERE 1=1"
        params: list = []
        if from_date and to_date:
            clause = "WHERE i.issue_date >= ? AND i.issue_date <= ?"
            params = [from_date, to_date]
        return self._fetchall(
            f"""WITH client_totals AS (
                    SELECT t.client_name,
                           COALESCE(SUM(i.total_amount), 0) AS total_invoiced
                    FROM invoices i
                    JOIN trips t ON t.id = i.trip_id
                    {clause}
                    GROUP BY t.client_name
                    ORDER BY total_invoiced DESC
                    LIMIT 5
                ),
                ranked_invoices AS (
                    SELECT t.client_name, i.invoice_number, i.issue_date,
                           i.due_date, i.total_amount, i.status,
                           t.payment_date,
                           CASE WHEN t.payment_date IS NOT NULL AND t.payment_date != ''
                                THEN ROUND(JULIANDAY(t.payment_date) - JULIANDAY(i.issue_date), 0)
                                ELSE ROUND(JULIANDAY(i.due_date) - JULIANDAY(i.issue_date), 0)
                           END AS delay_days,
                           ROW_NUMBER() OVER (
                               PARTITION BY t.client_name
                               ORDER BY i.issue_date DESC
                           ) AS rn
                    FROM invoices i
                    JOIN trips t ON t.id = i.trip_id
                    JOIN client_totals ct ON ct.client_name = t.client_name
                    {clause}
                )
                SELECT client_name, invoice_number, issue_date, due_date,
                       total_amount, status, payment_date, delay_days
                FROM ranked_invoices
                WHERE rn <= 6
                ORDER BY client_name, issue_date DESC""",
            tuple(params + params),
        )

    def get_driver_monthly_activity(self, months: int = 12, from_date=None, to_date=None):
        """Weekly activity per driver: which weeks had active trips.

        Returns rows: driver_name, week_start, trip_count.
        Each row represents one driver-week with at least one trip.
        """
        clause, clause_params = self._date_clause(from_date, to_date)
        filter_condition = "driver_name IS NOT NULL AND driver_name != '' AND driver_name != 'Unassigned'"
        if clause.strip() == "WHERE 1=1":
            drivers_clause = f"WHERE {filter_condition}"
        else:
            drivers_clause = f"{clause} AND {filter_condition}"
        return self._fetchall(
            f"""SELECT driver_name,
                       DATE(created_at, '-' || CAST((JULIANDAY(created_at) - JULIANDAY(
                           DATE(created_at, 'weekday 0'))) AS INTEGER) || ' days') AS week_start,
                       COUNT(*) AS trip_count
                FROM trips
                {drivers_clause}
                GROUP BY driver_name, week_start
                ORDER BY driver_name, week_start ASC
                LIMIT 500""",
            tuple(clause_params),
        )
