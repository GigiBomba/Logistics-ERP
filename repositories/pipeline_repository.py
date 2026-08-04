"""Repository for the Document Automation Pipeline.

Persists pipeline runs, customer packages, and package-document
membership rows.  All state transitions (status / stage / matched trip)
are written through this class so the rest of the system only sees
fully-formed dicts.
"""

import json
import logging
import threading
import time as _time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

logger = logging.getLogger("repositories.pipeline")


_NOW_CACHE: Optional[str] = None
_NOW_CACHE_TS: float = 0
_NOW_LOCK = threading.Lock()

def _now_iso() -> str:
    """Return ISO-formatted datetime, cached within the same second.

    Avoids creating a new ``datetime`` object on every call in tight
    loops (e.g., bulk INSERTs in ``replace_package_items``).
    Uses double-checked locking to avoid lock contention in the fast path.
    """
    global _NOW_CACHE, _NOW_CACHE_TS
    now = _time.time()
    # Fast path: cache is valid, no lock needed
    if _NOW_CACHE and now - _NOW_CACHE_TS < 1.0:
        return _NOW_CACHE
    with _NOW_LOCK:
        # Re-check after acquiring lock (another thread may have refreshed)
        if _NOW_CACHE and now - _NOW_CACHE_TS < 1.0:
            return _NOW_CACHE
        _NOW_CACHE = datetime.now().isoformat()
        _NOW_CACHE_TS = now
        return _NOW_CACHE


class PipelineRepository(BaseRepository):
    COLUMNS_PIPELINE_RUNS = [
        "id", "run_uuid", "source_file_path", "source_file_name", "source_mime_type",
        "source_file_size", "source_file_hash", "status", "stage", "error_message",
        "processed_file_path", "processed_pdf_path", "pages_count",
        "ocr_text", "extracted_data_json", "matched_trip_id", "match_confidence",
        "match_signals_json", "document_id", "created_at", "updated_at",
        "completed_at", "company_id",
    ]
    COLUMNS_PACKAGE = [
        "id", "trip_id", "package_uuid", "status", "recipient_email", "subject",
        "body", "email_message_id", "error_message", "sent_at",
        "created_at", "updated_at", "company_id",
    ]
    COLUMNS_PACKAGE_ITEMS = [
        "id", "package_id", "document_id", "sort_order", "company_id",
    ]

    # ── Pipeline runs ─────────────────────────────────────────────────

    def create_run(
        self,
        source_file_path: str,
        source_file_name: str,
        source_mime_type: str,
        source_file_size: int,
        source_file_hash: str = "",
        run_uuid: Optional[str] = None,
    ) -> int:
        """Insert a new pipeline run row. Returns the new row id."""
        # Defensive: strip NULs and other dangerous characters from
        # file paths / names.  SQLite tolerates arbitrary bytes in TEXT
        # but a stray newline or NUL in a name can break downstream
        # loggers and exporters.
        def _clean(value: str, *, allow_slash: bool = True) -> str:
            if not value:
                return ""
            cleaned = value.replace("\0", "").replace("\r", " ").replace("\n", " ")
            if not allow_slash:
                cleaned = cleaned.replace("/", " ")
            return cleaned.strip()
        source_file_path = _clean(source_file_path, allow_slash=True)[:1024]
        source_file_name = _clean(source_file_name, allow_slash=False)[:512]
        source_mime_type = _clean(source_mime_type, allow_slash=True)[:128]
        run_uuid = run_uuid or uuid.uuid4().hex
        try:
            source_file_size = int(source_file_size)
        except (TypeError, ValueError):
            source_file_size = 0
        if source_file_size < 0:
            source_file_size = 0
        now = _now_iso()
        data = {
            "run_uuid": run_uuid,
            "source_file_path": source_file_path,
            "source_file_name": source_file_name,
            "source_mime_type": source_mime_type,
            "source_file_size": source_file_size,
            "source_file_hash": source_file_hash,
            "status": "imported",
            "stage": "import",
            "created_at": now,
            "updated_at": now,
        }
        self._validate_columns(data, extra_allowed={"company_id"}, columns=self.COLUMNS_PIPELINE_RUNS)
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO document_pipeline_runs ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
		)

    def update_stage(
        self,
        run_id: int,
        stage: str,
        status: str,
        error_message: str = "",
    ) -> None:
        """Update stage + status atomically.  Sets completed_at if status is terminal."""
        now = _now_iso()
        completed_at = now if status in ("complete", "failed") else None
        self._execute(
            f"""
            UPDATE document_pipeline_runs
            SET stage = ?, status = ?, error_message = ?,
                updated_at = ?, completed_at = COALESCE(?, completed_at)
            WHERE id = ? {self._company_filter()}
            """,
            (stage, status, error_message, now, completed_at, run_id) + self._company_params(), commit=True,
		)

    def set_processed_files(
        self,
        run_id: int,
        processed_file_path: str,
        processed_pdf_path: str,
        pages_count: int,
    ) -> None:
        now = _now_iso()
        self._execute(
            f"""
            UPDATE document_pipeline_runs
            SET processed_file_path = ?, processed_pdf_path = ?,
                pages_count = ?, updated_at = ?
            WHERE id = ? {self._company_filter()}
            """,
            (processed_file_path, processed_pdf_path, pages_count, now, run_id) + self._company_params(), commit=True,
		)

    def set_ocr_result(
        self,
        run_id: int,
        ocr_text: str,
        extracted_data: Dict[str, Any],
    ) -> None:
        now = _now_iso()
        self._execute(
            f"""
            UPDATE document_pipeline_runs
            SET ocr_text = ?, extracted_data_json = ?, updated_at = ?
            WHERE id = ? {self._company_filter()}
            """,
            (ocr_text, json.dumps(extracted_data, ensure_ascii=False, default=str), now, run_id) + self._company_params(), commit=True,
		)

    def set_match_result(
        self,
        run_id: int,
        matched_trip_id: Optional[int],
        match_confidence: float,
        match_signals: Dict[str, float],
    ) -> None:
        now = _now_iso()
        self._execute(
            f"""
            UPDATE document_pipeline_runs
            SET matched_trip_id = ?, match_confidence = ?,
                match_signals_json = ?, updated_at = ?
            WHERE id = ? {self._company_filter()}
            """,
            (
                matched_trip_id,
                float(match_confidence),
                json.dumps(match_signals, ensure_ascii=False, default=str),
                now,
                run_id,
            ) + self._company_params(), commit=True,
		)

    def set_document_id(self, run_id: int, document_id: int) -> None:
        now = _now_iso()
        self._execute(
            f"""
            UPDATE document_pipeline_runs
            SET document_id = ?, updated_at = ?
            WHERE id = ? {self._company_filter()}
            """,
            (document_id, now, run_id) + self._company_params(), commit=True,
		)

    def set_related_documents(self, run_id: int, doc_ids: List[int]) -> None:
        """Store the list of related document IDs for a pipeline run.
        These are document IDs linked to the same trip, discovered
        after matching/grouping completes.  Stored inside
        ``match_signals_json`` so no schema migration is needed.
        """
        now = _now_iso()
        row = self._fetchone(
            "SELECT match_signals_json FROM document_pipeline_runs "
            "WHERE id = ? " + self._company_filter(),
            (run_id,) + self._company_params(),
        )
        signals = {}
        if row:
            try:
                signals = json.loads(row["match_signals_json"] or "{}")
            except (ValueError, TypeError):
                signals = {}
        signals["related_document_ids"] = doc_ids
        self._execute(
            f"""
            UPDATE document_pipeline_runs
            SET match_signals_json = ?, updated_at = ?
            WHERE id = ? {self._company_filter()}
            """,
            (json.dumps(signals, ensure_ascii=False), now, run_id) + self._company_params(), commit=True,
		)

    def get_run_by_id(self, run_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM document_pipeline_runs WHERE id = ? " + self._company_filter(),
            (run_id,) + self._company_params(),
        )

    def get_run_by_uuid(self, run_uuid: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM document_pipeline_runs WHERE run_uuid = ? " + self._company_filter(),
            (run_uuid,) + self._company_params(),
        )

    def get_run_by_hash(self, source_file_hash: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM document_pipeline_runs WHERE source_file_hash = ? "
            + self._company_filter() + " "
            "ORDER BY id DESC LIMIT 1",
            (source_file_hash,) + self._company_params(),
        )

    def list_runs(
        self,
        status: Optional[str] = None,
        trip_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM document_pipeline_runs WHERE 1=1 " + self._company_filter()
        params: List[Any] = list(self._company_params())
        if status:
            query += " AND status = ?"
            params.append(status)
        if trip_id is not None:
            query += " AND matched_trip_id = ?"
            params.append(trip_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self._fetchall(query, tuple(params))

    def list_active_runs(self) -> List[Dict[str, Any]]:
        """Return runs in any non-terminal state (used for crash recovery)."""
        return self._fetchall(
            "SELECT * FROM document_pipeline_runs "
            "WHERE status NOT IN ('complete', 'failed') "
            + self._company_filter(),
            self._company_params(),
        )

    def delete_run(self, run_id: int) -> None:
        self._execute(
            "DELETE FROM document_pipeline_runs WHERE id = ? " + self._company_filter(),
            (run_id,) + self._company_params(), commit=True,
		)

    def recover_stuck_runs(self) -> int:
        """Mark non-terminal runs as failed and clear stale data.

        Returns the number of recovered rows.  Stale half-applied
        state (extraction without a trip match, trip match without
        a document link, etc.) is intentionally preserved so the
        operator can inspect the run history; only the terminal
        status is set to ``failed`` so the UI stops treating the
        run as in-flight.

        Runs with ``status = 'processed'`` (Simple-mode runs awaiting
        user action) are **not** recovered — they stay visible so the
        user can pick a trip or create a standalone package after
        restarting the app.
        """
        now = _now_iso()
        try:
            count = self._execute_with_count(
                f"""
                UPDATE document_pipeline_runs
                SET status = 'failed',
                    error_message = 'Recovered from crash — process did not complete',
                    updated_at = ?, completed_at = ?
                WHERE status NOT IN ('complete', 'failed', 'processed')
                {self._company_filter()}
                """,
                (now, now) + self._company_params(), commit=True,
		)
            return count
        except Exception:
            logger.exception("recover_stuck_runs failed")
            try:
                self.rollback_transaction()
            except Exception:
                pass
            raise

    def get_extracted_data(self, run_id: int) -> Dict[str, Any]:
        """Convenience: parse the extracted_data_json column into a dict."""
        run = self.get_run_by_id(run_id)
        if not run:
            return {}
        raw = run.get("extracted_data_json") or "{}"
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return {}

    def get_match_signals(self, run_id: int) -> Dict[str, float]:
        """Convenience: parse the match_signals_json column into a dict."""
        run = self.get_run_by_id(run_id)
        if not run:
            return {}
        raw = run.get("match_signals_json") or "{}"
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {
                    k: float(v) for k, v in data.items()
                    if isinstance(v, (int, float, str))
                    and not isinstance(v, (list, dict))
                }
        except (ValueError, TypeError):
            pass
        return {}

    def get_related_document_ids(self, run_id: int) -> List[int]:
        """Return the list of related document IDs stored alongside
        match signals, or an empty list if not set."""
        run = self.get_run_by_id(run_id)
        if not run:
            return []
        raw = run.get("match_signals_json") or "{}"
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                ids = data.get("related_document_ids", [])
                if isinstance(ids, list):
                    result = []
                    for x in ids:
                        try:
                            result.append(int(x))
                        except (TypeError, ValueError):
                            continue
                    return result
        except (ValueError, TypeError):
            pass
        return []

    def get_runs_by_trip_id(self, trip_id: int) -> List[Dict[str, Any]]:
        """Return all pipeline runs that matched the given trip.

        Retrieves every run whose ``matched_trip_id`` equals *trip_id*,
        ordered by creation date descending.  Unlike ``list_runs`` this
        method has no ``limit`` so callers can find **all** related runs
        regardless of status (useful for retroactively injecting a newly
        discovered related document).
        """
        return self._fetchall(
            "SELECT * FROM document_pipeline_runs "
            "WHERE matched_trip_id = ? "
            + self._company_filter() + " "
            "ORDER BY id DESC",
            (trip_id,) + self._company_params(),
        )

    def append_related_document(self, run_id: int, doc_id: int) -> None:
        """Atomically append a document ID to ``related_document_ids``.

        Used when a Document Center document is linked to a trip *after*
        the pipeline run completed — the new document should appear
        alongside the existing ones in the customer package.

        Thread-safety note: the read-modify-write runs inside
        ``BEGIN IMMEDIATE`` so concurrent callers for the same run_id
        cannot lose updates.
        """
        now = _now_iso()
        try:
            self.begin_transaction()
            row = self._fetchone(
                "SELECT match_signals_json "
                "FROM document_pipeline_runs WHERE id = ? "
                + self._company_filter(),
                (run_id,) + self._company_params(),
            )
            signals: Dict[str, Any] = {}
            if row:
                try:
                    signals = json.loads(row["match_signals_json"] or "{}")
                except (ValueError, TypeError):
                    signals = {}
            ids = signals.get("related_document_ids", [])
            if not isinstance(ids, list):
                ids = []
            cleaned = []
            for x in ids:
                try:
                    cleaned.append(int(x))
                except (TypeError, ValueError):
                    continue
            if doc_id in cleaned:
                self.commit_transaction()
                return
            cleaned.append(doc_id)
            signals["related_document_ids"] = cleaned
            self._execute(
                f"""
                UPDATE document_pipeline_runs
                SET match_signals_json = ?, updated_at = ?
                WHERE id = ? {self._company_filter()}
                """,
                (json.dumps(signals, ensure_ascii=False), now, run_id) + self._company_params(),
                commit=False,
            )
            self.commit_transaction()
        except Exception:
            logger.exception(
                "append_related_document failed for run %d, doc %d",
                run_id, doc_id,
            )
            try:
                self.rollback_transaction()
            except Exception:
                pass
            raise

    # ── Customer packages ────────────────────────────────────────────

    def create_package(
        self,
        trip_id: Optional[int] = None,
        package_uuid: Optional[str] = None,
    ) -> int:
        package_uuid = package_uuid or uuid.uuid4().hex
        now = _now_iso()
        data = {
            "trip_id": trip_id,
            "package_uuid": package_uuid,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }
        self._validate_columns(data, extra_allowed={"company_id"}, columns=self.COLUMNS_PACKAGE)
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO document_package ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
		)

    def update_package(
        self,
        package_id: int,
        status: Optional[str] = None,
        recipient_email: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        email_message_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        fields = {k: v for k, v in locals().items()
                  if k != "self" and k != "package_id" and v is not None}
        self._validate_columns(fields, extra_allowed={"company_id"}, columns=self.COLUMNS_PACKAGE)
        sets: List[str] = []
        params: List[Any] = list(self._company_params())
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if recipient_email is not None:
            sets.append("recipient_email = ?")
            params.append(recipient_email)
        if subject is not None:
            sets.append("subject = ?")
            params.append(subject)
        if body is not None:
            sets.append("body = ?")
            params.append(body)
        if email_message_id is not None:
            sets.append("email_message_id = ?")
            params.append(email_message_id)
        if error_message is not None:
            sets.append("error_message = ?")
            params.append(error_message)
        if status == "sent" and email_message_id is not None:
            sets.append("sent_at = ?")
            params.append(_now_iso())
        if not sets:
            return
        sets.append("updated_at = ?")
        params.append(_now_iso())
        params.append(package_id)
        self._execute(
            f"UPDATE document_package SET {', '.join(sets)} WHERE id = ? {self._company_filter()}",
            tuple(params), commit=True,
		)

    def add_package_item(
        self,
        package_id: int,
        document_id: int,
        sort_order: int = 0,
    ) -> None:
        data = {
            "package_id": package_id,
            "document_id": document_id,
            "sort_order": sort_order,
        }
        self._validate_columns(data, extra_allowed={"company_id"}, columns=self.COLUMNS_PACKAGE_ITEMS)
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        self._execute(
            f"INSERT OR IGNORE INTO document_package_items ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
		)

    def add_package_items_batch(
        self,
        package_id: int,
        document_ids: list,
    ) -> None:
        if not document_ids:
            return
        try:
            self.begin_transaction()
            company_id = self._user_company_id if self._scoped else None
            if company_id is not None:
                self.db.conn.executemany(
                    "INSERT OR IGNORE INTO document_package_items "
                    "(package_id, document_id, sort_order, company_id) VALUES (?, ?, ?, ?)",
                    [(package_id, did, i, company_id) for i, did in enumerate(document_ids)],
                )
            else:
                self.db.conn.executemany(
                    "INSERT OR IGNORE INTO document_package_items "
                    "(package_id, document_id, sort_order) VALUES (?, ?, ?)",
                    [(package_id, did, i) for i, did in enumerate(document_ids)],
                )
            self.commit_transaction()
        except Exception:
            try:
                self.rollback_transaction()
            except Exception:
                pass
            raise

    def remove_package_item(self, package_id: int, document_id: int) -> None:
        self._execute(
            "DELETE FROM document_package_items "
            "WHERE package_id = ? AND document_id = ? "
            + self._company_filter(),
            (package_id, document_id) + self._company_params(), commit=True,
		)

    def replace_package_items(
        self,
        package_id: int,
        document_ids: List[int],
    ) -> None:
        """Replace all package items atomically with the given ordered list.

        Uses a single ``executemany`` for the INSERTs (much faster than
        individual ``execute`` calls) inside a ``BEGIN…COMMIT`` so the
        DELETE is not visible before the INSERTs.
        """
        try:
            self.begin_transaction()
            self._execute(
                "DELETE FROM document_package_items WHERE package_id = ? "
                + self._company_filter(),
                (package_id,) + self._company_params(),
                commit=False,
            )
            rows = []
            for idx, doc_id in enumerate(document_ids):
                try:
                    rows.append((package_id, int(doc_id), idx))
                except (TypeError, ValueError):
                    continue
            if rows:
                self.db.conn.executemany(
                    "INSERT INTO document_package_items (package_id, document_id, sort_order) "
                    "VALUES (?, ?, ?)",
                    rows,
                )
            self.commit_transaction()
        except Exception:
            logger.exception("Failed to replace package items for package %s", package_id)
            try:
                self.rollback_transaction()
            except Exception:
                pass
            raise

    def get_package_by_id(self, package_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM document_package WHERE id = ? " + self._company_filter(),
            (package_id,) + self._company_params(),
        )

    def get_package_by_uuid(self, package_uuid: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM document_package WHERE package_uuid = ? "
            + self._company_filter(),
            (package_uuid,) + self._company_params(),
        )

    def get_package_items(self, package_id: int) -> List[Dict[str, Any]]:
        """Return package items joined with their document rows, ordered by sort_order."""
        return self._fetchall(
            f"""
            SELECT
                pi.id            AS item_id,
                pi.sort_order    AS sort_order,
                d.id             AS document_id,
                d.doc_number     AS doc_number,
                d.title          AS title,
                d.file_path      AS file_path,
                d.file_name      AS file_name,
                d.file_size      AS file_size,
                d.mime_type      AS mime_type,
                d.category       AS category,
                d.cmr_number     AS cmr_number,
                d.is_signed      AS is_signed
            FROM document_package_items pi
            JOIN documents d ON d.id = pi.document_id
            WHERE pi.package_id = ? {self._company_filter('pi')}
            ORDER BY pi.sort_order ASC, pi.id ASC
            """,
            (package_id,) + self._company_params(),
        )

    def list_packages(
        self,
        trip_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM document_package WHERE 1=1 " + self._company_filter()
        params: List[Any] = list(self._company_params())
        if trip_id is not None:
            query += " AND trip_id = ?"
            params.append(trip_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self._fetchall(query, tuple(params))
