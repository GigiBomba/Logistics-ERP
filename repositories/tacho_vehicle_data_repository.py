"""Tacho vehicle data repository."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class TachoVehicleDataRepository(BaseRepository):
    TABLE = "tacho_vehicle_data"
    COLUMNS = [
        "id", "import_id", "truck_id", "vu_serial_number", "calibration_date",
        "calibration_expiry", "odometer_km", "k_factor", "w_factor",
        "speed_violations", "recorded_from", "recorded_to", "company_id",
    ]

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def get_by_truck(self, truck_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE truck_id = ? {self._company_filter()} ORDER BY id DESC",
            (truck_id,) + self._company_params(),
        )

    def get_by_import(self, import_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE import_id = ? {self._company_filter()}",
            (import_id,) + self._company_params(),
        )

    def get_latest_by_truck(self, truck_id: int) -> Optional[Dict[str, Any]]:
        """Return the most recent vehicle unit import for a specific truck."""
        return self._fetchone(
            f"""SELECT tvd.* FROM {self.TABLE} tvd
                JOIN tacho_imports ti ON ti.id = tvd.import_id
                WHERE tvd.truck_id = ? {self._company_filter('tvd')}
                ORDER BY ti.imported_at DESC LIMIT 1""",
            (truck_id,) + self._company_params(),
        )

    def get_tacho_status_data(self) -> List[Dict[str, Any]]:
        rows = self._fetchall(
            """SELECT
                t.id AS truck_id,
                t.plate_number,
                tvd.calibration_date,
                tvd.calibration_expiry,
                ti.imported_at,
                ti.id AS import_id
            FROM trucks t
            LEFT JOIN (
                SELECT tvd2.*,
                       ROW_NUMBER() OVER (PARTITION BY tvd2.truck_id ORDER BY ti2.imported_at DESC) AS rn
                FROM tacho_vehicle_data tvd2
                JOIN tacho_imports ti2 ON ti2.id = tvd2.import_id
            ) tvd ON tvd.truck_id = t.id AND tvd.rn = 1
            LEFT JOIN tacho_imports ti ON ti.id = tvd.import_id
            WHERE t.active_status = 1
            ORDER BY t.plate_number ASC"""
        )
        return rows

    def get_latest_per_truck(self) -> List[Dict[str, Any]]:
        """Return the most recent vehicle unit import for each truck."""
        return self._fetchall(
            f"""SELECT tvd.* FROM {self.TABLE} tvd
                JOIN (
                    SELECT tvd_inner.truck_id, MAX(ti.imported_at) AS latest_at
                    FROM {self.TABLE} tvd_inner
                    JOIN tacho_imports ti ON ti.id = tvd_inner.import_id
                    WHERE tvd_inner.truck_id IS NOT NULL
                    GROUP BY tvd_inner.truck_id
                ) latest ON latest.truck_id = tvd.truck_id
                JOIN tacho_imports ti2 ON ti2.id = tvd.import_id AND ti2.imported_at = latest.latest_at"""
        )
