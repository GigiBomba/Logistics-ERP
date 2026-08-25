"""Successive carrier repository — sub-contracted carriers per CMR trip."""
from __future__ import annotations

from typing import Any, Dict, List

from repositories import BaseRepository

class SuccessiveCarrierRepository(BaseRepository):
    TABLE = "successive_carriers"
    COLUMNS = [
        "id", "trip_id", "company_id", "sequence_order", "carrier_name",
        "carrier_address", "carrier_country", "vehicle_plate",
        "trailer_plate", "driver_name", "from_location", "to_location",
    ]

    def get_by_trip(self, trip_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE trip_id = ? {self._company_filter()} ORDER BY sequence_order ASC",
            (trip_id,) + self._company_params(),
        )

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
		)

    def update(self, carrier_id: int, data: Dict[str, Any]) -> None:
        self._validate_columns(data)
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (carrier_id,) + self._company_params(), commit=True,
		)

    def delete(self, carrier_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (carrier_id,) + self._company_params(), commit=True,
		)

    def delete_by_trip(self, trip_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE trip_id = ? {self._company_filter()}",
            (trip_id,) + self._company_params(), commit=True,
		)

    def replace_for_trip(self, trip_id: int, carriers: List[Dict[str, Any]]) -> None:
        self.begin_transaction()
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE trip_id = ? {self._company_filter()}",
            (trip_id,) + self._company_params(),
            commit=False,
        )
        for i, c in enumerate(carriers):
            c = dict(c)
            c["trip_id"] = trip_id
            c["sequence_order"] = i + 1
            c = self._set_company_from_context(c)
            cols = ", ".join(c.keys())
            vals = ", ".join("?" for _ in c)
            self._execute(
                f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
                tuple(c.values()),
                commit=False,
            )
        self.commit_transaction()
