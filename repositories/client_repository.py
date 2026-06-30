"""Client repository — all client DB access consolidated here."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class ClientRepository(BaseRepository):
    TABLE = "clients"

    def get_by_id(self, client_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (client_id,)
        )

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE name = ?", (name,)
        )

    def search_by_name(self, name: str, fuzzy: bool = True, limit: int = 5) -> List[Dict[str, Any]]:
        """Exact match first, then fuzzy LIKE match.

        Used by the document automation trip-matcher to find the
        client whose name appeared in OCR text.
        """
        name = (name or "").strip()
        if not name:
            return []
        # Exact match wins.
        exact = self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE is_active = 1 AND LOWER(TRIM(name)) = LOWER(TRIM(?))",
            (name,),
        )
        results: List[Dict[str, Any]] = []
        if exact:
            results.append(exact)
        if fuzzy:
            like_results = self._fetchall(
                f"SELECT * FROM {self.TABLE} "
                "WHERE is_active = 1 AND name LIKE ? ESCAPE '\\' "
                "ORDER BY name ASC LIMIT ?",
                (f"%{self._escape_like(name)}%", limit),
            )
            for r in like_results:
                if r["id"] not in {x["id"] for x in results}:
                    results.append(r)
        return results[:limit]

    def get_all(self, include_inactive: bool = False, limit: int = 500) -> List[Dict[str, Any]]:
        where = "" if include_inactive else "WHERE is_active = 1"
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} {where} ORDER BY name ASC LIMIT ?",
            (limit,),
        )

    @staticmethod
    def _escape_like(s: str) -> str:
        return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE is_active = 1 AND name LIKE ? ESCAPE '\\' ORDER BY name ASC LIMIT ?",
            (f"%{self._escape_like(query)}%", limit),
        )

    def create(self, data: Dict[str, Any]) -> int:
        from datetime import datetime
        data = dict(data)
        data.setdefault("created_at", datetime.utcnow().isoformat(timespec="seconds") + "Z")
        data.setdefault("is_active", 1)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def update(self, client_id: int, data: Dict[str, Any]) -> None:
        from datetime import datetime
        data = dict(data)
        data["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ?",
            tuple(data.values()) + (client_id,),
        )

    def deactivate(self, client_id: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET is_active = 0 WHERE id = ?", (client_id,)
        )

    def get_trip_count(self, client_id: int) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM trips WHERE client_id = ?",
            (client_id,),
        )
        return row["cnt"] if row else 0

    def get_top_by_revenue(self, limit: int = 5) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT c.*, SUM(COALESCE(t.total_price_eur, 0)) AS total_revenue
                FROM {self.TABLE} c
                JOIN trips t ON t.client_id = c.id
                WHERE t.status NOT IN ('Cancelled')
                GROUP BY c.id
                ORDER BY total_revenue DESC
                LIMIT ?""",
            (limit,),
        )

    def get_trips(self, client_id: int, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM trips WHERE client_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (client_id, limit, offset),
        )

    def get_trips_status_counts(self, client_id: int) -> Dict[str, int]:
        rows = self._fetchall(
            "SELECT LOWER(status) AS status, COUNT(*) AS cnt FROM trips WHERE client_id = ? GROUP BY LOWER(status)",
            (client_id,),
        )
        return {r["status"]: r["cnt"] for r in rows}

    def get_revenue_summary(self, client_id: int) -> Dict[str, Any]:
        row = self._fetchone(
            """SELECT COUNT(*) AS total_trips,
                      COALESCE(SUM(total_price_eur), 0) AS total_revenue,
                      COALESCE(SUM(net_profit), 0) AS total_profit,
                      COALESCE(AVG(net_profit), 0) AS avg_profit,
                      COALESCE(SUM(distance_km), 0) AS total_km,
                      COALESCE(MAX(created_at), '') AS last_trip_date
               FROM trips WHERE client_id = ? AND status NOT IN ('Cancelled')""",
            (client_id,),
        )
        return row or {}

    def get_revenue_history(self, client_id: int, months: int = 12) -> List[Dict[str, Any]]:
        return self._fetchall(
            """SELECT SUBSTR(start_date, 1, 7) AS month,
                      COUNT(*) AS trip_count,
                      COALESCE(SUM(total_price_eur), 0) AS revenue,
                      COALESCE(SUM(net_profit), 0) AS profit,
                      COALESCE(SUM(distance_km), 0) AS km
               FROM trips
               WHERE client_id = ? AND status NOT IN ('Cancelled')
               GROUP BY month
               ORDER BY month DESC
               LIMIT ?""",
            (client_id, months),
        )

    def get_outstanding_invoices(self, client_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        return self._fetchall(
            """SELECT i.*, t.client_name, t.truck_number, t.distance_km,
                      t.total_price_eur AS trip_revenue, t.start_date
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ?
               ORDER BY i.due_date ASC
               LIMIT ?""",
            (client_id, limit),
        )

    def get_outstanding_balance(self, client_id: int) -> float:
        row = self._fetchone(
            """SELECT COALESCE(SUM(i.total_amount), 0) AS balance
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ? AND i.status = 'Unpaid'""",
            (client_id,),
        )
        return float(row["balance"]) if row else 0.0

    def get_invoices(self, client_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        return self._fetchall(
            """SELECT i.*, t.client_name, t.truck_number, t.distance_km,
                      t.total_price_eur AS trip_revenue, t.start_date, t.status AS trip_status
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ?
               ORDER BY i.issue_date DESC
               LIMIT ?""",
            (client_id, limit),
        )

    def get_trip_count_in_range(self, client_id: int, days: int = 30) -> int:
        from datetime import datetime, timedelta
        since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM trips WHERE client_id = ? AND start_date >= ?",
            (client_id, since),
        )
        return row["cnt"] if row else 0

    def search_advanced(self, query: str, include_inactive: bool = False, limit: int = 200) -> List[Dict[str, Any]]:
        q = f"%{self._escape_like(query)}%"
        active_clause = "" if include_inactive else "AND c.is_active = 1"
        return self._fetchall(
            f"""SELECT c.*
                FROM {self.TABLE} c
                WHERE (c.name LIKE ? ESCAPE '\\' OR c.contact_person LIKE ? ESCAPE '\\' OR c.phone LIKE ? ESCAPE '\\'
                       OR c.email LIKE ? ESCAPE '\\' OR c.address LIKE ? ESCAPE '\\' OR c.notes LIKE ? ESCAPE '\\')
                      {active_clause}
                ORDER BY c.name ASC
                LIMIT ?""",
            (q, q, q, q, q, q, limit),
        )

    def get_all_with_revenue(self, include_inactive: bool = False, limit: int = 500) -> List[Dict[str, Any]]:
        active_clause = "" if include_inactive else "WHERE c.is_active = 1"
        return self._fetchall(
            f"""SELECT c.*,
                      COALESCE(SUM(CASE WHEN t.status NOT IN ('Cancelled') THEN t.total_price_eur ELSE 0 END), 0) AS total_revenue,
                      COUNT(DISTINCT t.id) AS trip_count,
                      COALESCE(SUM(CASE WHEN i.status = 'Unpaid' THEN i.total_amount ELSE 0 END), 0) AS outstanding_balance
               FROM {self.TABLE} c
               LEFT JOIN trips t ON t.client_id = c.id
               LEFT JOIN invoices i ON i.trip_id = t.id
               {active_clause}
               GROUP BY c.id
               ORDER BY c.name ASC
               LIMIT ?""",
            (limit,),
        )
