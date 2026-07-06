"""Alert repository — alerts table persistence."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

logger = logging.getLogger(__name__)


class AlertRepository(BaseRepository):
    TABLE = "alerts"

    def create(self, id: str, alert_type: str, severity: str, title: str,
               message: str, truck_id: Optional[str], trip_id: Optional[int],
               created_at: str, resolved: int, resolved_at: Optional[str],
               metadata_json: Optional[str]) -> None:
        self._execute(
            "INSERT OR REPLACE INTO alerts "
            "(id, type, severity, title, message, truck_id, trip_id, "
            "created_at, resolved, resolved_at, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (id, alert_type, severity, title, message, truck_id,
             trip_id, created_at, resolved, resolved_at, metadata_json),
        )

    def create_batch(self, alerts: List[tuple]) -> int:
        """Bulk insert alerts. Each tuple: (id, type, severity, title, message,
        truck_id, trip_id, created_at, resolved, resolved_at, metadata_json)."""
        count = 0
        try:
            self.begin_transaction()
            for alert in alerts:
                self._execute(
                    "INSERT OR IGNORE INTO alerts "
                    "(id, type, severity, title, message, truck_id, trip_id, "
                    "created_at, resolved, resolved_at, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    alert,
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
            f"FROM {self.TABLE} WHERE resolved = 0 ORDER BY created_at ASC"
        )

    def resolve(self, alert_id: str, resolved_at: Optional[str]) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET resolved = 1, resolved_at = ? WHERE id = ?",
            (resolved_at, alert_id),
        )

    def cleanup_old(self, days: int = 90) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE created_at < ? AND resolved = 1",
            (cutoff,),
        )
