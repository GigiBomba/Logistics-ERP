"""Alert repository — alerts table persistence."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

logger = logging.getLogger(__name__)


class AlertRepository(BaseRepository):
    TABLE = "alerts"
    COLUMNS = [
        "id", "type", "severity", "title", "message", "truck_id", "trip_id",
        "created_at", "resolved", "resolved_at", "metadata_json", "company_id",
    ]

    def create(self, id: str, alert_type: str, severity: str, title: str,
               message: str, truck_id: Optional[str], trip_id: Optional[int],
               created_at: str, resolved: int, resolved_at: Optional[str],
               metadata_json: Optional[str]) -> None:
        data = {
            "id": id,
            "type": alert_type,
            "severity": severity,
            "title": title,
            "message": message,
            "truck_id": truck_id,
            "trip_id": trip_id,
            "created_at": created_at,
            "resolved": resolved,
            "resolved_at": resolved_at,
            "metadata_json": metadata_json,
        }
        self._validate_columns(data, extra_allowed={"company_id"})
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        self._execute(
            f"INSERT OR REPLACE INTO alerts ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
        )

    def create_batch(self, alerts: List[tuple]) -> int:
        """Bulk insert alerts. Each tuple: (id, type, severity, title, message,
        truck_id, trip_id, created_at, resolved, resolved_at, metadata_json)."""
        count = 0
        try:
            self.begin_transaction()
            for alert in alerts:
                data = {
                    "id": alert[0],
                    "type": alert[1],
                    "severity": alert[2],
                    "title": alert[3],
                    "message": alert[4],
                    "truck_id": alert[5],
                    "trip_id": alert[6],
                    "created_at": alert[7],
                    "resolved": alert[8],
                    "resolved_at": alert[9],
                    "metadata_json": alert[10],
                }
                self._validate_columns(data, extra_allowed={"company_id"})
                data = self._set_company_from_context(data)
                cols = ", ".join(data.keys())
                vals = ", ".join("?" for _ in data)
                self._execute(
                    f"INSERT OR IGNORE INTO alerts ({cols}) VALUES ({vals})",
                    tuple(data.values()),
                    commit=False,
                )
                count += 1
            self.commit_transaction()
        except Exception:
            logger.exception("Failed to persist alert batch")
            self.rollback_transaction()
            return 0
        return count

    def get_unresolved(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT id, type, severity, title, message, truck_id, trip_id, "
            "created_at, resolved, resolved_at, metadata_json "
            f"FROM {self.TABLE} WHERE resolved = 0 {self._company_filter()} ORDER BY created_at ASC",
            self._company_params(),
        )

    def resolve(self, alert_id: str, resolved_at: Optional[str]) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET resolved = 1, resolved_at = ? WHERE id = ? {self._company_filter()}",
            (resolved_at, alert_id) + self._company_params(), commit=True,
        )

    def cleanup_old(self, days: int = 90) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE created_at < ? AND resolved = 1 {self._company_filter()}",
            (cutoff,) + self._company_params(), commit=True,
        )
