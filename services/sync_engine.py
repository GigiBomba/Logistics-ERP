"""Sync engine — the background push/pull loop (Phase 4a).

The engine runs on its own QThread (worker QObject + QTimer) so the
synchronous httpx ``ApiClient`` never blocks the UI thread.  Each cycle:

1. **Connectivity probe** — ``api_client.is_online()``; offline → status
   ``"offline"`` and the cycle ends (no network calls).
2. **Push phase** — drain the outbox in chunks, translate local FK ids to
   server ids (P1), convert UPDATE-with-``deleted_at`` to DELETE (R4),
   and handle per-item results (ok / conflict / error / gone).
3. **Pull phase** — pull server rows and upsert locally, skipping rows
   that have a pending outbox op (P2) so unpushed local edits are not
   clobbered and locally-deleted rows are not resurrected.
4. **Prune** — drop synced outbox rows older than the retention window.

Signals (emitted from the worker thread; Qt marshals them to the
receiver's thread — the UI thread in production):

* ``sync_started`` — a cycle began
* ``sync_finished(summary)`` — a cycle completed (counts + status)
* ``sync_error(message)`` — a cycle raised / a push item exceeded retries
* ``sync_status_changed(status)`` — ``"offline" | "syncing" | "idle" | "conflicts"``
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from database.time_utils import utc_now_iso
from services.device_identity import DeviceIdentity
from services.sync_conflict_service import SyncConflictService
from services.sync_pull_service import _DOCUMENT_REF_ENTITIES, _FK_REFERENCES

logger = logging.getLogger(__name__)

# Push batch size — keep each request small enough to respect the server's
# request-size limits.
_PUSH_CHUNK_SIZE = 100
# A push item is surfaced via ``sync_error`` (and left in the outbox) after
# this many failed attempts.
_MAX_PUSH_RETRIES = 5


def _chunks(seq: list, size: int):
    """Yield successive *size*-sized chunks of *seq*."""
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _file_sha256(file_path: str) -> str:
    """Return the sha256 hex digest of *file_path* (Phase C)."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class _SyncWorker(QObject):
    """Runs the sync cycle on the engine's background thread."""

    sync_started = Signal()
    sync_finished = Signal(dict)
    sync_error = Signal(str)
    sync_status_changed = Signal(str)
    _sync_requested = Signal()

    def __init__(self, db, api_client, outbox, pull, interval_seconds: int, device_id: str, user_id: int = 0, force_full_sync: bool = False) -> None:
        super().__init__()
        self._db = db
        self._api_client = api_client
        self._outbox = outbox
        self._pull = pull
        self._conflicts = SyncConflictService(db)
        self._device_id = device_id
        self._interval_seconds = max(1, interval_seconds)
        # Phase E (multi-user): per-user pull cursors.  Defaults to 0 — a
        # single-user desktop keeps one cursor namespace (today's behavior).
        self._user_id = user_id
        # Phase E: one-shot force-full-refresh flag (manual resync / tests).
        self._force_full_sync = force_full_sync
        # R4: thread-safe stop flag — set by ``SyncEngine.stop()``, checked at
        # phase boundaries so a long cycle aborts promptly on shutdown.
        self._stop_requested = threading.Event()
        self._timer = QTimer(self)
        self._timer.setInterval(self._interval_seconds * 1000)
        self._timer.timeout.connect(self.sync_once)
        self._sync_requested.connect(self.sync_once)

    # ── Thread lifecycle ──────────────────────────────────────────────

    @Slot()
    def _on_thread_started(self) -> None:
        """Start the periodic timer and run an immediate first cycle."""
        self._timer.start()
        self.sync_once()

    def set_user(self, user_id: int) -> None:
        """Switch the per-user cursor namespace (Phase E — multi-user).

        The switch ALSO schedules a one-shot full refresh (Phase F wiring):
        the engine may be mid-cycle when a login/user change lands (e.g. it
        started at user 0 and the login arrives after the pull phase), and a
        partial cursor written under the new user would silently swallow rows.
        Forcing a full refresh for the next cycle makes a user switch safe
        regardless of when it lands.
        """
        self._user_id = user_id
        self._pull.set_user(user_id)
        # Phase F: a user switch must never leave polluted partial cursors —
        # the next cycle re-pulls every entity from scratch for this user.
        self._force_full_sync = True
        logger.info(
            "sync engine worker now syncing as user_id=%s (per-user cursors); "
            "next cycle forced to a full refresh",
            user_id,
        )

    def force_full_sync(self) -> None:
        """Schedule the next cycle as a full keyset refresh (one-shot)."""
        self._force_full_sync = True

    # ── Public API ────────────────────────────────────────────────────

    @Slot()
    def sync_once(self) -> None:
        """Run one full sync cycle (push → pull → prune).

        Runs in whatever thread calls it: the engine thread when driven by
        the periodic timer, the caller's thread when invoked directly
        (tests / blocking manual refresh).
        """
        self.sync_started.emit()
        self.sync_status_changed.emit("syncing")
        summary: Dict[str, Any] = {
            "pushed": 0,
            "conflicts": 0,
            "errors": 0,
            "gone": 0,
            "pulled": 0,
            "binary_uploaded": 0,
            "binary_downloaded": 0,
            "settings_pushed": 0,
            "settings_pulled": 0,
            "sequences_reconciled": 0,
            "tombstones_applied": 0,
            "entities_delta": 0,
            "entities_full_refresh": 0,
            "status": "idle",
        }
        try:
            if self._abort_if_stopping(summary):
                return

            # R2: the real ApiClient caches ``is_online()`` forever — reset the
            # cached probe so EVERY cycle re-checks connectivity.  An app booted
            # offline must recover when the server comes back (offline-first).
            if hasattr(self._api_client, "_online"):
                self._api_client._online = None
            if not self._api_client.is_online():
                self.sync_status_changed.emit("offline")
                summary["status"] = "offline"
                self.sync_finished.emit(summary)
                return

            # Unauthenticated (logged out / no session): the server rejects
            # every sync request with 401 — skip the cycle quietly instead of
            # erroring every interval.  The engine resumes on the next login
            # (setup_sync's on_auth_changed wiring forces a full refresh).
            # Guarded with hasattr so test doubles without an auth slot are
            # unaffected.
            if hasattr(self._api_client, "_auth"):
                _auth = self._api_client._auth
                if _auth is None or _auth.token is None:
                    self.sync_status_changed.emit("offline")
                    summary["status"] = "offline"
                    self.sync_finished.emit(summary)
                    return

            if self._abort_if_stopping(summary):
                return

            pushed, conflicts, errors, gone = self._push_phase()
            summary.update(pushed=pushed, conflicts=conflicts, errors=errors, gone=gone)

            if self._abort_if_stopping(summary):
                return

            # Phase D: reconcile document counters AFTER each successful push
            # so the shared invoice/CMR sequences never diverge (max-merge —
            # a stale desktop can never decrease them).
            summary["sequences_reconciled"] = self._reconcile_sequences_phase()

            if self._abort_if_stopping(summary):
                return

            summary["pulled"] = self._pull_phase()
            summary["tombstones_applied"] = getattr(
                self._pull, "last_tombstone_count", 0,
            )
            # Phase E: how many entities pulled deltas vs full refresh.
            summary["entities_delta"] = getattr(self._pull, "last_delta_count", 0)
            summary["entities_full_refresh"] = getattr(
                self._pull, "last_full_refresh_count", 0,
            )

            if self._abort_if_stopping(summary):
                return

            # Phase C: document binaries — push local files up, pull missing
            # server files down (after the row pull so the id map is current).
            binary_uploaded, binary_downloaded = self._document_binary_phase()
            summary["binary_uploaded"] = binary_uploaded
            summary["binary_downloaded"] = binary_downloaded

            if self._abort_if_stopping(summary):
                return

            # Phase D: settings sync (company config + SMTP + preferences).
            settings_pushed, settings_pulled = self._settings_phase()
            summary["settings_pushed"] = settings_pushed
            summary["settings_pulled"] = settings_pulled

            if self._abort_if_stopping(summary):
                return

            self._outbox.prune(days=30)
            self.sync_status_changed.emit("idle")
            self.sync_finished.emit(summary)
        except Exception as exc:
            logger.exception("sync cycle failed")
            self.sync_error.emit(str(exc))
            self.sync_status_changed.emit("idle")
            summary["status"] = "error"
            self.sync_finished.emit(summary)

    def _abort_if_stopping(self, summary: Dict[str, Any]) -> bool:
        """Return True if a stop was requested — the cycle should abort cleanly.

        Emits ``sync_finished`` with status ``"stopped"`` so the UI gets a
        completion signal even on shutdown (R4).
        """
        if self._stop_requested.is_set():
            summary["status"] = "stopped"
            self.sync_status_changed.emit("idle")
            self.sync_finished.emit(summary)
            return True
        return False

    # ── Push phase ────────────────────────────────────────────────────

    def _push_phase(self) -> Tuple[int, int, int, int]:
        """Drain pending outbox rows to the server in chunks.

        Returns ``(pushed, conflicts, errors, gone)`` counts.
        """
        pushed = conflicts = errors = gone = 0
        pending = self._outbox.pending(limit=500)
        if not pending:
            return pushed, conflicts, errors, gone

        for chunk in _chunks(pending, _PUSH_CHUNK_SIZE):
            # R4: abort promptly when a stop was requested mid-cycle.
            if self._stop_requested.is_set():
                break
            items: List[Dict[str, Any]] = []
            rows: List[Dict[str, Any]] = []
            for row in chunk:
                item = self._build_push_item(row)
                if item is None:
                    # Row no longer exists locally (deleted before push) →
                    # nothing to send; drop the outbox row.
                    self._outbox.mark_synced(row["id"])
                    continue
                items.append(item)
                rows.append(row)
            if not items:
                continue

            resp = self._api_client.post(
                "/api/v1/sync/push",
                json={"items": items, "device_id": self._device_id},
            )
            results = (resp or {}).get("results") or []
            if len(results) != len(items):
                logger.warning(
                    "push: server returned %d results for %d items",
                    len(results), len(items),
                )
            for row, item, result in zip(rows, items, results):
                status = result.get("status")
                if status == "ok":
                    self._outbox.mark_synced(row["id"], result.get("server_id"))
                    if row["op"] == "INSERT" and result.get("server_id") is not None:
                        # P1: record the local→server id mapping so later
                        # pushes can translate FK references.
                        self._record_id_map(
                            row["entity_type"], row["local_id"], result["server_id"]
                        )
                    pushed += 1
                elif status == "conflict":
                    self._conflicts.record(
                        row["entity_type"],
                        row["local_id"],
                        server_id=result.get("server_id"),
                        local_payload=item["payload"],
                        server_payload=result.get("server_row"),
                    )
                    conflicts += 1
                    self.sync_status_changed.emit("conflicts")
                elif status == "error":
                    self._outbox.mark_retry(row["id"])
                    errors += 1
                    if row["retry_count"] + 1 > _MAX_PUSH_RETRIES:
                        # Surface it and leave the row in the outbox — the
                        # journal/UI can decide what to do with it.
                        self.sync_error.emit(
                            f"push failed after {_MAX_PUSH_RETRIES} retries: "
                            f"{row['entity_type']} local_id={row['local_id']} "
                            f"({result.get('error') or 'unknown error'})"
                        )
                elif status == "gone":
                    # P4: the mapped server row is gone → drop the outbox row
                    # and the stale id-map entry.
                    self._outbox.mark_synced(row["id"])
                    self._delete_id_map(row["entity_type"], row["local_id"])
                    gone += 1
                else:
                    logger.warning(
                        "push: unexpected status %r for %s/%s",
                        status, row["entity_type"], row["local_id"],
                    )
                    self._outbox.mark_retry(row["id"])
                    errors += 1
        return pushed, conflicts, errors, gone

    def _build_push_item(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build the push API item for one outbox row.

        Returns ``None`` when there is nothing to push (the local row no
        longer exists for an INSERT/UPDATE) — the caller drops the outbox row.
        """
        entity_type = row["entity_type"]
        local_id = row["local_id"]
        op = row["op"]

        if op == "DELETE":
            payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
            # base_updated_at = the version the client last saw (the row's
            # updated_at captured at delete time).
            base_updated_at = payload.get("updated_at")
            return {
                "entity_type": entity_type,
                "op": "DELETE",
                "local_id": local_id,
                "payload": payload,
                "base_updated_at": base_updated_at,
            }

        payload = self._outbox.resolve_payload(entity_type, local_id)
        if payload is None:
            return None

        # Phase D: binary BLOB columns (e.g. route_history_v2's
        # geometry_compressed) cannot travel through the JSON push payload.
        # Drop them here — the derived geometry is recomputed locally; sync
        # of derived data is best-effort convergence anyway.
        if any(isinstance(v, bytes) for v in payload.values()):
            payload = {
                k: v for k, v in payload.items() if not isinstance(v, bytes)
            }

        # R4: an UPDATE whose row is soft-deleted locally is a DELETE.
        if op == "UPDATE" and payload.get("deleted_at"):
            op = "DELETE"

        # S3: an UPDATE with no sync_id_map entry (e.g. the mapping was
        # cleared by a prior 'gone' result) would be rejected by the server
        # forever ("no mapping").  Send it as INSERT instead — the server's
        # R6 path re-creates the row and re-maps it, un-wedging the lane.
        if op == "UPDATE" and self._lookup_server_id(entity_type, local_id) is None:
            op = "INSERT"

        # P1: translate local FK ids → server ids before sending
        # (INSERT/UPDATE payloads are applied server-side).
        payload = self._translate_fks(entity_type, payload)

        base_updated_at = payload.get("updated_at") if op in ("UPDATE", "DELETE") else None
        return {
            "entity_type": entity_type,
            "op": op,
            "local_id": local_id,
            "payload": payload,
            "base_updated_at": base_updated_at,
        }

    def _translate_fks(self, entity_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Translate local FK ids to server ids via ``sync_id_map`` (P1).

        Unmapped references are left as-is — the parent row is pushed first
        (dependency order) or the server rejects the item (surfaced as an
        error/conflict in the journal).
        """
        data = dict(payload)
        for (ent, col), ref_entity in _FK_REFERENCES.items():
            if ent != entity_type:
                continue
            local_fk = data.get(col)
            if local_fk is None:
                continue
            server_id = self._lookup_server_id(ref_entity, local_fk)
            if server_id is not None:
                data[col] = server_id
        # P5: document.entity_id is polymorphic — translate only when the
        # row's entity_type is a v1 entity.
        if entity_type == "document":
            ref = data.get("entity_type")
            if ref in _DOCUMENT_REF_ENTITIES and data.get("entity_id") is not None:
                server_id = self._lookup_server_id(ref, data["entity_id"])
                if server_id is not None:
                    data["entity_id"] = server_id
        # C1: document_links.linked_entity_id is the same polymorphic pattern
        # (paired with linked_entity_type).
        if entity_type == "document_link":
            ref = data.get("linked_entity_type")
            if ref in _DOCUMENT_REF_ENTITIES and data.get("linked_entity_id") is not None:
                server_id = self._lookup_server_id(ref, data["linked_entity_id"])
                if server_id is not None:
                    data["linked_entity_id"] = server_id
        return data

    # ── Pull phase ────────────────────────────────────────────────────

    def _pull_phase(self) -> int:
        """Pull server rows and apply locally, skipping pending-outbox rows.

        P2: rows with a pending outbox op are skipped so unpushed local edits
        are not clobbered and locally-deleted rows are not resurrected.

        P3 (serialization against UI writes): the echo-suppression flag
        (``sync_meta.sync_in_progress``) is process-global, so a UI write
        that lands DURING the pull-apply window is silently not captured.
        Mitigation for v1: the engine runs in its own thread and the pull
        applies per-entity (short transactions), so the window is small.
        A global lock is deliberately NOT used — it would block the UI.
        """
        # Snapshot the pending set right before the pull so rows pushed in
        # this same cycle (now synced) are NOT skipped — only rows that are
        # still pending (push failed / conflicted) protect their local row.
        pending = self._outbox.pending(limit=500)
        skip_local_ids = {(r["entity_type"], r["local_id"]) for r in pending}
        # R4: pass the stop flag into the pull lane so its pagination loop
        # aborts between pages — a large company's pull must not outlive the
        # engine thread on shutdown.
        # Phase E: consume the one-shot force-full-refresh flag, then pull
        # with per-user cursors (delta) or full refresh accordingly.
        force = self._force_full_sync
        self._force_full_sync = False
        return self._pull.pull_all(
            skip_local_ids=skip_local_ids,
            should_stop=lambda: self._stop_requested.is_set(),
            device_id=self._device_id,
            user_id=self._user_id,
            force_full_sync=force,
        )

    # ── Document binary phase (Phase C) ───────────────────────────────

    def _document_binary_phase(self) -> Tuple[int, int]:
        """Push local document files up and pull missing server files down.

        Runs after the row push/pull so ``sync_id_map`` has server ids for
        document rows.  Per-document try/except keeps one bad file from
        aborting the cycle; the stop flag is checked between documents.

        Push dedup: a ``sync_meta`` key ``doc_binary_uploaded:<server_id>``
        records the last uploaded sha256 so unchanged files are not re-uploaded
        every cycle.  Pull dedup: a local file whose sha256 matches the server
        ``file_hash`` is skipped.
        """
        uploaded = 0
        downloaded = 0

        # ── Push binaries ──────────────────────────────────────────────
        rows = self._db.conn.execute(
            "SELECT d.id, d.file_path, d.file_hash, m.server_id "
            "FROM documents d "
            "JOIN sync_id_map m ON m.entity_type = 'document' AND m.local_id = d.id "
            "WHERE d.file_hash != '' AND d.file_path != ''"
        ).fetchall()
        for row in rows:
            if self._stop_requested.is_set():
                break
            local_path = row["file_path"]
            if not os.path.isfile(local_path):
                logger.debug("document binary push: local file missing %s", local_path)
                continue
            # R5 (data corruption): verify the ACTUAL on-disk file against the
            # row's recorded hash.  A mismatch means an external edit or a
            # wrong-file shadow (e.g. a pulled doc whose placeholder path
            # pointed at an unrelated local file of the same name) — never
            # silently replace the server binary.  Re-register the document to
            # refresh the row hash after an external edit.
            try:
                actual_hash = _file_sha256(local_path)
            except OSError:
                logger.debug("document binary push: unreadable file %s", local_path)
                continue
            if actual_hash != row["file_hash"]:
                logger.warning(
                    "document binary push: local file hash for doc %s disagrees "
                    "with row file_hash (%s != %s); skipping upload",
                    row["id"], actual_hash[:8], row["file_hash"][:8],
                )
                continue
            meta_key = f"doc_binary_uploaded:{row['server_id']}"
            if self._outbox.get_meta(meta_key) == row["file_hash"]:
                continue  # already uploaded with this content
            try:
                self._api_client.upload_document_file(
                    row["server_id"], local_path, skip_ocr=True,
                )
                self._outbox.set_meta(meta_key, row["file_hash"])
                uploaded += 1
            except Exception as exc:
                logger.warning(
                    "document binary upload failed for doc %s: %s", row["id"], exc,
                )

        # ── Pull binaries ──────────────────────────────────────────────
        # R3 (data loss): the file_path UPDATE below must NOT be captured by
        # the outbox trigger — otherwise the next push echoes the desktop's
        # local path to the server, where it is meaningless (404s for every
        # other device).  set_sync_in_progress suppresses the capture; the
        # flag always clears via try/finally.
        self._outbox.set_sync_in_progress(True)
        try:
            rows = self._db.conn.execute(
                "SELECT d.id, d.file_path, d.file_name, d.category, d.file_hash, "
                "       m.server_id "
                "FROM documents d "
                "JOIN sync_id_map m ON m.entity_type = 'document' AND m.local_id = d.id "
                "WHERE d.file_hash != ''"
            ).fetchall()
            for row in rows:
                if self._stop_requested.is_set():
                    break
                dest = self._documents_destination(row["category"], row["file_name"])
                if not dest:
                    continue
                # Already synced: the local row points at a matching file.
                local_path = row["file_path"] or ""
                if local_path and os.path.isfile(local_path):
                    try:
                        if _file_sha256(local_path) == row["file_hash"]:
                            continue
                    except OSError:
                        pass
                # The destination file already matches → just point the row at it.
                if os.path.isfile(dest):
                    try:
                        if _file_sha256(dest) == row["file_hash"]:
                            if dest != local_path:
                                self._db.conn.execute(
                                    "UPDATE documents SET file_path = ? WHERE id = ?",
                                    (dest, row["id"]),
                                )
                                self._db.conn.commit()
                            continue
                    except OSError:
                        pass
                try:
                    self._api_client.download_document_file(row["server_id"], dest)
                    self._db.conn.execute(
                        "UPDATE documents SET file_path = ? WHERE id = ?",
                        (dest, row["id"]),
                    )
                    self._db.conn.commit()
                    downloaded += 1
                except Exception as exc:
                    logger.warning(
                        "document binary download failed for doc %s: %s", row["id"], exc,
                    )
        finally:
            self._outbox.set_sync_in_progress(False)

        return uploaded, downloaded

    # ── Phase D: sequence reconciliation ──────────────────────────────

    def _reconcile_sequences_phase(self) -> int:
        """Push local invoice/CMR counter state to the server (max-merge).

        Runs after a successful push so the shared counters converge.  The
        server only ever bumps to ``max(existing, value)``, so a stale
        desktop cannot decrease the shared counter (no duplicate numbers).

        B5: the server returns the POST-MERGE value, and we apply it BACK to
        the local counter (``max(local, server)``) — otherwise a second
        device that already allocated higher numbers leaves this device's
        LOCAL counter stale, and the NEXT allocation on this device re-uses
        numbers the server already handed out → UNIQUE invoice-number
        conflict → permanent retry wedge.

        Skipped entirely when the ApiClient does not support the endpoint
        (older server / test doubles without the method).
        """
        if not hasattr(self._api_client, "reconcile_sequences"):
            return 0
        count = 0
        # CMR: cmr_counter (year → sequence_number).
        try:
            rows = self._db.conn.execute(
                "SELECT year, sequence_number FROM cmr_counter "
                "WHERE sequence_number > 0"
            ).fetchall()
            for row in rows:
                if self._stop_requested.is_set():
                    break
                try:
                    resp = self._api_client.reconcile_sequences(
                        "cmr", row["year"], int(row["sequence_number"]),
                    )
                    count += 1
                    merged = (resp or {}).get("value")
                    if merged is not None:
                        self._db.conn.execute(
                            "UPDATE cmr_counter SET sequence_number = "
                            "MAX(sequence_number, ?) WHERE year = ?",
                            (int(merged), row["year"]),
                        )
                        self._db.conn.commit()
                except Exception as exc:
                    logger.warning(
                        "sequence reconcile (cmr %s) failed: %s", row["year"], exc,
                    )
        except Exception as exc:
            logger.warning("sequence reconcile: cmr_counter read failed: %s", exc)
        # Invoice: the DEFAULT invoice series (inv_year_seq) — the same series
        # both desktop and server use by default.  Custom-series deployments
        # are out of scope for reconciliation (documented risk).
        try:
            from repositories.invoice_repository import DEFAULT_INVOICE_FORMAT_KEY

            rows = self._db.conn.execute(
                "SELECT year, last_number FROM invoice_number_sequences "
                "WHERE series = ? AND last_number > 0",
                (DEFAULT_INVOICE_FORMAT_KEY,),
            ).fetchall()
            for row in rows:
                if self._stop_requested.is_set():
                    break
                try:
                    resp = self._api_client.reconcile_sequences(
                        "invoice", row["year"], int(row["last_number"]),
                    )
                    count += 1
                    merged = (resp or {}).get("value")
                    if merged is not None:
                        self._db.conn.execute(
                            "UPDATE invoice_number_sequences SET last_number = "
                            "MAX(last_number, ?) WHERE series = ? AND year = ?",
                            (int(merged), DEFAULT_INVOICE_FORMAT_KEY, row["year"]),
                        )
                        self._db.conn.commit()
                except Exception as exc:
                    logger.warning(
                        "sequence reconcile (invoice %s) failed: %s", row["year"], exc,
                    )
        except Exception as exc:
            logger.warning("sequence reconcile: invoice read failed: %s", exc)
        return count

    # ── Phase D: settings sync ────────────────────────────────────────

    def _settings_phase(self) -> Tuple[int, int]:
        """Push local settings up and pull the server's settings down.

        Echo suppression: the ``settings`` table has NO outbox capture
        triggers (it is not in SYNCABLE_ENTITIES), so writing pulled values
        locally can never create an outbox row — inherently safe.

        Skipped entirely when the ApiClient does not support the settings
        endpoints (older server / test doubles without the methods).
        """
        if not (
            hasattr(self._api_client, "save_setting")
            and hasattr(self._api_client, "get_settings_bulk")
        ):
            return 0, 0
        from services.settings_sync_service import SettingsSyncService

        svc = SettingsSyncService(self._db, self._api_client)
        pushed = 0
        pulled = 0
        if not self._stop_requested.is_set():
            pushed = svc.push_settings()
        if not self._stop_requested.is_set():
            pulled = svc.pull_settings()
        return pushed, pulled

    @staticmethod
    def _documents_destination(category: str, file_name: str) -> str:
        """Desktop document storage convention: ``data/documents/{category}/{name}``."""
        from services.document.upload_service import DOCUMENTS_ROOT

        if not file_name:
            return ""
        safe = os.path.basename(file_name.replace("\\", "/"))
        return os.path.join(DOCUMENTS_ROOT, category or "other", safe)

    # ── sync_id_map helpers ───────────────────────────────────────────

    def _lookup_server_id(self, entity_type: str, local_id: int) -> Optional[int]:
        """Return the server id mapped to (entity_type, local_id), or None."""
        row = self._db.conn.execute(
            "SELECT server_id FROM sync_id_map WHERE entity_type = ? AND local_id = ?",
            (entity_type, local_id),
        ).fetchone()
        return row["server_id"] if row else None

    def _record_id_map(self, entity_type: str, local_id: int, server_id: int) -> None:
        """Record the (entity_type, local_id) ↔ server_id mapping."""
        self._db.conn.execute(
            "INSERT OR REPLACE INTO sync_id_map "
            "(entity_type, local_id, server_id, created_at) VALUES (?, ?, ?, ?)",
            (entity_type, local_id, server_id, utc_now_iso()),
        )
        self._db.conn.commit()

    def _delete_id_map(self, entity_type: str, local_id: int) -> None:
        """Delete the (entity_type, local_id) mapping (P4 — stale entry)."""
        self._db.conn.execute(
            "DELETE FROM sync_id_map WHERE entity_type = ? AND local_id = ?",
            (entity_type, local_id),
        )
        self._db.conn.commit()


class SyncEngine(QObject):
    """Background sync engine (QThread + worker QObject).

    Public signals (relayed from the worker):

    * ``sync_started``
    * ``sync_finished(summary: dict)``
    * ``sync_error(message: str)``
    * ``sync_status_changed(status: str)``
    """

    sync_started = Signal()
    sync_finished = Signal(dict)
    sync_error = Signal(str)
    sync_status_changed = Signal(str)

    def __init__(
        self,
        db,
        api_client,
        outbox,
        pull,
        interval_seconds: int = 60,
        device_id: str | None = None,
        user_id: int = 0,
        force_full_sync: bool = False,
    ) -> None:
        super().__init__()
        # Phase A: resolve the per-install device identity (stable across
        # restarts / engine instances sharing the same DB).  Injectable for
        # tests via ``device_id``.
        self._device_id = device_id or DeviceIdentity(db).get()
        # Phase E (multi-user): per-user pull cursors (defaults to the single-
        # user namespace 0).
        self._user_id = user_id
        self._force_full_sync = force_full_sync
        self._worker = _SyncWorker(
            db, api_client, outbox, pull, interval_seconds,
            device_id=self._device_id,
            user_id=self._user_id,
            force_full_sync=self._force_full_sync,
        )
        self._thread = QThread()
        self._thread.setObjectName("SyncEngineThread")
        # Relay worker signals to the engine's public signals.  In production
        # the worker lives on the engine thread → queued delivery to the UI
        # thread.  In tests the worker stays on the caller's thread → direct
        # (synchronous) delivery.
        self._worker.sync_started.connect(self.sync_started)
        self._worker.sync_finished.connect(self.sync_finished)
        self._worker.sync_error.connect(self.sync_error)
        self._worker.sync_status_changed.connect(self.sync_status_changed)
        self._thread.started.connect(self._worker._on_thread_started)

    def start(self) -> None:
        """Start the background thread + periodic timer."""
        if self._thread.isRunning():
            return
        # R4: clear any leftover stop flag from a previous stop() so a
        # restart runs normally.
        self._worker._stop_requested.clear()
        if self._worker.thread() is not self._thread:
            self._worker.moveToThread(self._thread)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background thread (waits for the current cycle to abort).

        R4: sets the worker's stop flag (the cycle aborts at the next phase
        boundary) then waits WITHOUT the old 5s ceiling — a cycle can
        legitimately run longer (httpx retries, paginated pull).  The stop
        flag makes the cycle exit promptly, so ``wait()`` returns quickly.
        """
        if not self._thread.isRunning():
            return
        self._worker._stop_requested.set()
        self._thread.quit()
        if not self._thread.wait(120000):
            logger.warning("sync engine thread did not stop within 120s")

    def sync_once(self) -> None:
        """Run one sync cycle synchronously in the calling thread.

        Used by tests and by callers that want a blocking cycle.  For a
        non-blocking cycle from the UI thread use :meth:`request_sync`.
        """
        self._worker.sync_once()

    def request_sync(self) -> None:
        """Request a sync cycle on the engine thread (non-blocking)."""
        if self._thread.isRunning():
            self._worker._sync_requested.emit()
        else:
            self.sync_once()

    def set_user(self, user_id: int) -> None:
        """Switch the per-user cursor namespace (Phase E — multi-user).

        Call on login / user switch / logout (user_id=0).  Per-user cursors
        live in the ``sync_cursors`` table keyed by user id: a new user has no
        cursors, so their first pull is a full refresh.  The worker ALSO
        schedules a one-shot full refresh for the next cycle so a user switch
        that lands mid-cycle can never leave polluted partial cursors.
        The outbox + id-map remain per-DEVICE — pending changes push under
        whoever is logged in, and the server stamps ``company_id`` from that
        user's JWT.

        NOTE (multi-company outbox): user B (different company) logging in
        while user A's rows are still pending pushes will push those rows
        under B's JWT → they land in B's company.  Accepted design for now —
        the outbox is drained as fast as the network allows; a company switch
        with a non-empty outbox should ideally flush/drain first.  Documented,
        not built (see Task 1 wiring comment in main.setup_sync).
        """
        self._user_id = user_id
        self._worker.set_user(user_id)

    def force_full_sync(self) -> None:
        """Schedule the NEXT cycle as a full keyset refresh for every entity.

        Phase E: ignores the stored per-user cursors once (manual resync /
        tests).  Cursors are re-stored from the fresh results.
        """
        self._worker.force_full_sync()