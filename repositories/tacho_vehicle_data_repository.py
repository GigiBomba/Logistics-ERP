"""Tacho vehicle data repository."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class TachoVehicleDataRepository(BaseRepository):
    TABLE = "tacho_vehicle_data"

    def create(self, data: Dict[str, Any]) -> int:
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def get_by_truck(self, truck_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE truck_id = ? ORDER BY id DESC",
            (truck_id,),
        )

    def get_by_import(self, import_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE import_id = ?", (import_id,)
        )

    def get_latest_by_truck(self, truck_id: int) -> Optional[Dict[str, Any]]:
        """Return the most recent vehicle unit import for a specific truck."""
        return self._fetchone(
            f"""SELECT tvd.* FROM {self.TABLE} tvd
                JOIN tacho_imports ti ON ti.id = tvd.import_id
                WHERE tvd.truck_id = ?
                ORDER BY ti.imported_at DESC LIMIT 1""",
            (truck_id,),
        )

    def get_latest_per_truck(self) -> List[Dict[str, Any]]:
        """Return the most recent vehicle unit import for each truck."""
        return self._fetchall(
            f"""SELECT tvd.* FROM {self.TABLE} tvd
                JOIN (
                    SELECT truck_id, MAX(ti.imported_at) AS latest_at
                    FROM {self.TABLE}
                    JOIN tacho_imports ti ON ti.id = import_id
                    WHERE truck_id IS NOT NULL
                    GROUP BY truck_id
                ) latest ON latest.truck_id = tvd.truck_id
                JOIN tacho_imports ti2 ON ti2.id = tvd.import_id AND ti2.imported_at = latest.latest_at"""
        )
