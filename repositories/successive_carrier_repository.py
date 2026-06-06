"""Successive carrier repository — sub-contracted carriers per CMR trip."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class SuccessiveCarrierRepository(BaseRepository):
    TABLE = "successive_carriers"
    COLUMNS = [
        "id", "trip_id", "sequence_order", "carrier_name",
        "carrier_address", "carrier_country", "vehicle_plate",
        "trailer_plate", "driver_name", "from_location", "to_location",
    ]

    def get_by_trip(self, trip_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE trip_id = ? ORDER BY sequence_order ASC",
            (trip_id,),
        )

    def create(self, data: Dict[str, Any]) -> int:
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def update(self, carrier_id: int, data: Dict[str, Any]) -> None:
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ?",
            tuple(data.values()) + (carrier_id,),
        )

    def delete(self, carrier_id: int) -> None:
        self._execute(f"DELETE FROM {self.TABLE} WHERE id = ?", (carrier_id,))

    def delete_by_trip(self, trip_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE trip_id = ?", (trip_id,)
        )

    def replace_for_trip(self, trip_id: int, carriers: List[Dict[str, Any]]) -> None:
        self.delete_by_trip(trip_id)
        for i, c in enumerate(carriers):
            c = dict(c)
            c["trip_id"] = trip_id
            c["sequence_order"] = i + 1
            self.create(c)
