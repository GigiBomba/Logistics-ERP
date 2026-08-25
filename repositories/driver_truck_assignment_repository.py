from __future__ import annotations

from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class DriverTruckAssignmentRepository(BaseRepository):
    TABLE = "driver_truck_assignments"
    COLUMNS = [
        "id", "driver_id", "truck_id", "assigned_at", "company_id",
    ]

    def get_by_driver(self, driver_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE driver_id = ? {self._company_filter()}",
            (driver_id,) + self._company_params(),
        )

    def get_by_truck(self, truck_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE truck_id = ? {self._company_filter()}",
            (truck_id,) + self._company_params(),
        )

    def get_all(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE 1=1 {self._company_filter()}",
            self._company_params(),
        )

    def assign(self, driver_id: int, truck_id: int) -> None:
        data = {"driver_id": driver_id, "truck_id": truck_id}
        self._validate_columns(data, extra_allowed={"company_id", "assigned_at"})
        self._execute(
            f"INSERT OR REPLACE INTO {self.TABLE} (driver_id, truck_id, assigned_at{', company_id' if self._scoped else ''}) "
            f"VALUES (?, ?, datetime('now'){', ?' if self._scoped else ''})",
            (driver_id, truck_id) + self._company_params(), commit=True,
		)

    def unassign_driver(self, driver_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE driver_id = ? {self._company_filter()}",
            (driver_id,) + self._company_params(), commit=True,
		)

    def unassign_truck(self, truck_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE truck_id = ? {self._company_filter()}",
            (truck_id,) + self._company_params(), commit=True,
		)

    def swap(self, driver1_id: int, truck1_id: int, driver2_id: int, truck2_id: int) -> None:
        self.begin_transaction()
        self._execute(
            f"UPDATE {self.TABLE} SET truck_id = ? WHERE driver_id = ? {self._company_filter()}",
            (truck2_id, driver1_id) + self._company_params(),
            commit=False,
        )
        self._execute(
            f"UPDATE {self.TABLE} SET truck_id = ? WHERE driver_id = ? {self._company_filter()}",
            (truck1_id, driver2_id) + self._company_params(),
            commit=False,
        )
        self.commit_transaction()

    def get_truck_plate_for_driver(self, driver_id: int) -> str:
        row = self._fetchone(
            f"SELECT t.plate_number FROM trucks t "
            f"JOIN {self.TABLE} dta ON dta.truck_id = t.id "
            f"WHERE dta.driver_id = ? {self._company_filter('dta')}",
            (driver_id,) + self._company_params(),
        )
        return row["plate_number"] if row and row.get("plate_number") else ""

    def get_plates_by_driver_ids(self, driver_ids: list[int]) -> dict[int, str]:
        """Return ``{driver_id: plate_number}`` for a batch of drivers.

        One query instead of N sequential ``get_truck_plate_for_driver``
        JOINs (used by the driver manager's per-row "truck" column).
        """
        if not driver_ids:
            return {}
        placeholders = ", ".join("?" for _ in driver_ids)
        rows = self._fetchall(
            f"""SELECT dta.driver_id, t.plate_number
                FROM {self.TABLE} dta
                JOIN trucks t ON dta.truck_id = t.id
                WHERE dta.driver_id IN ({placeholders})
                  {self._company_filter('dta')}""",
            tuple(driver_ids) + self._company_params(),
        )
        return {
            row["driver_id"]: row["plate_number"]
            for row in rows
            if row.get("plate_number")
        }

    def get_driver_name_for_truck(self, truck_id: int) -> str:
        row = self._fetchone(
            f"SELECT d.name FROM drivers d "
            f"JOIN {self.TABLE} dta ON dta.driver_id = d.id "
            f"WHERE dta.truck_id = ? {self._company_filter('dta')}",
            (truck_id,) + self._company_params(),
        )
        return row["name"] if row and row.get("name") else ""

    def get_driver_names_for_trucks(self, truck_ids: list[int]) -> dict[int, str]:
        """Return {truck_id: driver_name} mapping for a batch of trucks."""
        if not truck_ids:
            return {}
        placeholders = ", ".join("?" for _ in truck_ids)
        rows = self._fetchall(
            f"""SELECT da.truck_id, d.name
                FROM driver_truck_assignments da
                JOIN drivers d ON da.driver_id = d.id
                WHERE da.truck_id IN ({placeholders})
                  AND da.active = 1""",
            tuple(truck_ids)
        )
        return {row["truck_id"]: row["name"] for row in rows}

    def get_driver_id_for_truck(self, truck_id: int) -> Optional[int]:
        row = self._fetchone(
            f"SELECT driver_id FROM {self.TABLE} WHERE truck_id = ? {self._company_filter()}", (truck_id,) + self._company_params(),
        )
        return row["driver_id"] if row else None
