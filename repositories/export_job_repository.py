"""ExportJobRepository — CRUD for the mobile async export_jobs table.

Used by:
  - the mobile history export endpoint (job creation + status reads),
  - the analytics sync export handler (job row for download-token linkage),
  - the Celery ``export_trips_job`` task (status transitions).

Tenant scoping follows the API-layer pattern (``_company_filter_for`` /
``_company_params_for`` — explicit ``company_id`` binds from the caller's
JWT, exactly like ``ClientRepository.search_advanced``), so the row/rows are
scoped regardless of the tenant-context state.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from repositories import BaseRepository

_STATUS_PROCESSING = "processing"
_STATUS_SUCCESS = "success"
_STATUS_ERROR = "error"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ExportJobRepository(BaseRepository):
    TABLE = "export_jobs"
    COLUMNS = [
        "kind", "params_json", "status", "result_path", "error",
        "company_id", "created_at", "completed_at",
    ]

    def create(self, kind: str, params: Optional[dict], company_id: int,
               status: str = _STATUS_PROCESSING,
               result_path: str = "", error: str = "") -> int:
        now = _now_iso()
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} "
            "(kind, params_json, status, result_path, error, company_id, created_at, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (kind, json.dumps(params or {}), status, result_path, error,
             company_id, now, None),
            commit=True,
        )

    def get(self, job_id: int, company_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? "
            f"{self._company_filter_for(company_id)}",
            (job_id,) + self._company_params_for(company_id),
        )

    def get_raw(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a job row without a tenant filter (admin / task use)."""
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (job_id,),
        )

    def mark_success(self, job_id: int, result_path: str, company_id: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET status = ?, result_path = ?, "
            "error = NULL, completed_at = ? WHERE id = ? "
            f"{self._company_filter_for(company_id)}",
            (_STATUS_SUCCESS, result_path, _now_iso(), job_id)
            + self._company_params_for(company_id),
            commit=True,
        )

    def mark_error(self, job_id: int, error: str, company_id: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET status = ?, error = ?, completed_at = ? "
            "WHERE id = ? " + self._company_filter_for(company_id),
            (_STATUS_ERROR, error[:2000], _now_iso(), job_id)
            + self._company_params_for(company_id),
            commit=True,
        )
