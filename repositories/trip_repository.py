"""Trip repository — all trip DB access consolidated here."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class TripRepository(BaseRepository):
    TABLE = "trips"
    COLUMNS = [
        "id", "created_at", "truck_number", "driver_name", "client_name",
        "distance_km", "total_price_eur", "rate_per_km", "gross_per_km",
        "net_profit", "start_date", "end_date", "payment_date", "extra_costs",
        "fuel_cost", "toll_cost", "salary_cost", "currency", "status",
        "context_json", "route_history_v2_id", "truck_consumption_l_per_100km",
        "driver_id", "client_id",
    ]

    # ── Base CRUD ─────────────────────────────────────────────────────

    def get_by_id(self, trip_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (trip_id,)
        )

    def get_all(self, limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def create(self, data: Dict[str, Any]) -> int:
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def update(self, trip_id: int, data: Dict[str, Any]) -> None:
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ?",
            tuple(data.values()) + (trip_id,),
        )

    def delete(self, trip_id: int) -> None:
        self._execute(f"DELETE FROM {self.TABLE} WHERE id = ?", (trip_id,))

    # ── Domain-specific queries ───────────────────────────────────────

    def get_by_driver_id(self, driver_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE driver_id = ? ORDER BY created_at DESC",
            (driver_id,),
        )

    def get_by_status(self, status: str) -> List[Dict[str, Any]]:
        return self.get_by_statuses([status])

    def get_by_statuses(self, statuses: List[str]) -> List[Dict[str, Any]]:
        placeholders = ", ".join("?" for _ in statuses)
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE status IN ({placeholders}) ORDER BY created_at DESC",
            tuple(statuses),
        )

    def get_by_date_range(self, start: str, end: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE created_at >= ? AND created_at <= ? ORDER BY created_at DESC",
            (start, end),
        )

    def get_by_truck_number(self, truck_number: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE truck_number = ? ORDER BY created_at DESC",
            (truck_number,),
        )

    def get_last_activity(self, truck_number: str) -> Optional[str]:
        row = self._fetchone(
            f"SELECT MAX(created_at) AS last_date FROM {self.TABLE} WHERE truck_number = ?",
            (truck_number,),
        )
        return row["last_date"] if row else None

    def get_daily_profit(self, start: str, end: str) -> List[tuple]:
        """Return daily profit for date range: list of (day_str, profit)."""
        start = start.strip()
        end = end.strip()
        rows = self._fetchall(
            f"""SELECT start_date AS day,
                       SUM(COALESCE(net_profit,
                           total_price_eur - COALESCE(fuel_cost,0)
                           - COALESCE(toll_cost,0) - COALESCE(salary_cost,0)
                           - COALESCE(extra_costs,0), 0)) AS profit
                FROM {self.TABLE}
                WHERE LENGTH(start_date) >= 10
                  AND start_date >= ?
                  AND start_date <= ?
                  AND LOWER(status) IN ('delivered', 'completed', 'done', 'paid')
                GROUP BY start_date
                ORDER BY start_date""",
            (start, end),
        )
        return [(r["day"], float(r["profit"] or 0)) for r in rows]

    def get_top_trucks_by_revenue(self, month_start: str, month_end: str, limit: int = 4) -> List[Dict[str, Any]]:
        """Return top trucks by revenue for a date range."""
        month_start = month_start.strip()
        month_end = month_end.strip()
        return self._fetchall(
            f"""SELECT truck_number,
                       SUM(COALESCE(total_price_eur, 0)) AS revenue
                FROM {self.TABLE}
                WHERE LENGTH(start_date) >= 10
                  AND start_date >= ?
                  AND start_date <= ?
                  AND LOWER(status) IN ('delivered', 'completed', 'done', 'paid')
                GROUP BY truck_number
                ORDER BY revenue DESC
                LIMIT ?""",
            (month_start, month_end, limit),
        )
