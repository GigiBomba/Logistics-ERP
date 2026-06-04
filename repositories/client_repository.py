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

    def get_all(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        if include_inactive:
            return self._fetchall(
                f"SELECT * FROM {self.TABLE} ORDER BY name ASC"
            )
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE is_active = 1 ORDER BY name ASC"
        )

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE is_active = 1 AND name LIKE ? ORDER BY name ASC LIMIT ?",
            (f"%{query}%", limit),
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
