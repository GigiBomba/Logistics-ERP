"""Sync pull service — the desktop pull/upsert lane (Phase 3b).

Pulls company-scoped rows from the cloud API (``GET /api/v1/sync/pull``),
upserts them into the local SQLite tables, and maintains the bidirectional
``sync_id_map`` (local id ↔ server id) so:

* pushed rows can reference server ids (local→server translation happens in
  the push lane via ``sync_id_map``), and
* pulled rows can resolve server-side FK references to local ids
  (server→local translation happens here in ``_translate_fks``).

Echo suppression: the whole pull-apply runs with ``sync_in_progress`` set
(``SyncOutboxService.set_sync_in_progress``) so the outbox capture triggers
do not re-capture the rows this lane writes.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from database import schema as _schema
from database.time_utils import utc_now_iso
from services.sync_outbox_service import SyncOutboxService

logger = logging.getLogger(__name__)

# Reverse of ``SYNCABLE_ENTITIES`` (entity type → table name).  Built once
# at import; all values are distinct so the reverse lookup is unambiguous.
_ENTITY_TYPE_TO_TABLE = {v: k for k, v in _schema.SYNCABLE_ENTITIES.items()}

# Phase B pull scope — all 25 entities, in dependency order so parents are
# pulled before children (FK translation succeeds on the first pass):
# clients/drivers/trucks → maintenance → their children → trips → their
# children → receipts/invoices → expenses → documents → their children.
_PULL_ORDER = (
    "client", "driver", "truck",
    "maintenance_record", "maintenance_schedule",
    "client_contact", "client_tag",
    "driver_truck_assignment",
    "tacho_import",
    "tacho_driver_activity", "tacho_vehicle_data",
    "trip",
    "successive_carrier", "trip_status_history",
    "receipt", "invoice",
    "invoice_reminder",
    "expense",
    "document",
    "document_link", "document_version", "sent_email",
    "proforma_invoice", "contract",
    "email_log",
    # Phase D (sync completeness): route history — no FK parents, so it can
    # live at the end of the dependency order.
    "route_history",
)

# FK columns per entity type → the entity type they reference.  Server rows
# carry SERVER ids in these columns; before writing we translate each via
# ``sync_id_map`` (server_id → local_id).  Unmapped references are left NULL
# for this cycle — the next pull fixes them (self-healing).
_FK_REFERENCES: Dict[tuple, str] = {
    ("trip", "truck_id"): "truck",
    ("trip", "driver_id"): "driver",
    ("trip", "client_id"): "client",
    ("maintenance_record", "truck_id"): "truck",
    ("maintenance_schedule", "truck_id"): "truck",
    ("invoice", "trip_id"): "trip",
    ("invoice", "client_id"): "client",   # C1: invoices carry client_id both ways
    ("receipt", "related_trip_id"): "trip",
    ("receipt", "driver_id"): "driver",
    ("receipt", "vehicle_id"): "truck",
    ("receipt", "trailer_id"): "truck",
    ("receipt", "client_id"): "client",   # P5: receipt → client FK gap
    ("expense", "truck_id"): "truck",
    # Phase B: the 15 newly synced entities
    ("client_contact", "client_id"): "client",
    ("client_tag", "client_id"): "client",
    ("driver_truck_assignment", "driver_id"): "driver",
    ("driver_truck_assignment", "truck_id"): "truck",
    ("tacho_import", "truck_id"): "truck",
    ("tacho_import", "driver_id"): "driver",
    ("tacho_driver_activity", "import_id"): "tacho_import",
    ("tacho_driver_activity", "driver_id"): "driver",
    ("tacho_vehicle_data", "import_id"): "tacho_import",
    ("tacho_vehicle_data", "truck_id"): "truck",
    ("successive_carrier", "trip_id"): "trip",
    ("trip_status_history", "trip_id"): "trip",
    ("document_link", "document_id"): "document",
    ("document_version", "document_id"): "document",
    ("sent_email", "document_id"): "document",
    ("email_log", "trip_id"): "trip",
    ("invoice_reminder", "invoice_id"): "invoice",
    ("invoice_reminder", "trip_id"): "trip",
    ("contract", "client_id"): "client",
    ("contract", "document_id"): "document",
    # S1: route_history_v2.truck_id is a per-device local truck identifier
    # (a plate string or an integer id stored as text).  When it holds an
    # integer id, translate it like any other FK; plate strings simply don't
    # match a mapping and pass through untouched.
    ("route_history", "truck_id"): "truck",
}

# v1 entities a ``document.entity_id`` may reference (P5).  The document
# table's ``entity_id`` is polymorphic — the referenced entity type depends
# on the row's ``entity_type`` column.  We translate only when it is one of
# the v1 entities; anything else is left as-is.
_DOCUMENT_REF_ENTITIES = {"trip", "client", "driver", "truck"}


class SyncPullService:
    """Pull/upsert lane over the cloud sync API."""

    def __init__(self, db, api_client, page_size: int = 500, user_id: int = 0) -> None:
        self.db = db
        self.api_client = api_client
        self.page_size = page_size
        self._column_cache: Dict[str, set] = {}
        self._notnull_cache: Dict[str, set] = {}
        # Phase D: number of tombstones applied by the most recent pull_all /
        # pull_tombstones call (surfaced in the engine's sync summary).
        self.last_tombstone_count = 0
        # Phase E: per-user delta pull.  Cursors are keyed by ``user_id`` in
        # the sync_cursors table; ``set_user`` switches the namespace (a new
        # user has no cursors → first pull is a full refresh).  Defaults to 0
        # so single-user desktops keep one namespace (today's behavior).
        self.user_id = user_id
        self.last_delta_count = 0
        self.last_full_refresh_count = 0
        # Reason for the most recent _upsert_record False (P2 skip vs C2 skip) —
        # lets pull_entity decide whether the cursor may advance.
        self._last_skip_reason: Optional[str] = None

    def set_user(self, user_id: int) -> None:
        """Switch the cursor namespace to *user_id* (Phase E multi-user).

        Per-user cursors: a different user has no stored cursors → their first
        pull on this desktop is a full refresh.  The outbox + id-map remain
        per-DEVICE (unchanged) — pending changes push under whoever is logged
        in, and the server stamps company_id from that user's JWT.
        """
        self.user_id = user_id

    # ── Per-user delta cursors ─────────────────────────────────────────

    def _get_cursor(self, entity_type: str) -> Optional[tuple]:
        """Return the stored delta state ``(cursor, last_id)`` for (user,
        entity), or None.  ``last_id`` is the id tiebreak for the cursor
        second (R1) — the next delta resends ``since`` + ``after_id`` so a
        row stamped at exactly the cursor second is not permanently missed.
        """
        row = self.db.conn.execute(
            "SELECT cursor, last_id FROM sync_cursors "
            "WHERE user_id = ? AND entity_type = ?",
            (self.user_id, entity_type),
        ).fetchone()
        if row is None:
            return None
        return (row["cursor"], int(row["last_id"] or 0))

    def _set_cursor(self, entity_type: str, cursor: str, last_id: int = 0) -> None:
        """Store the delta state for (user, entity) — INSERT OR REPLACE."""
        try:
            from database.tenant_context import get_company_id
            cid = get_company_id() or 0
        except Exception:
            cid = 0
        self.db.conn.execute(
            "INSERT OR REPLACE INTO sync_cursors "
            "(user_id, company_id, entity_type, cursor, last_id, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (self.user_id, cid, entity_type, cursor, int(last_id or 0), utc_now_iso()),
        )
        self.db.conn.commit()

    # ── Public API ────────────────────────────────────────────────────

    def pull_all(
        self,
        skip_local_ids: Optional[set] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        device_id: Optional[str] = None,
        user_id: Optional[int] = None,
        force_full_sync: bool = False,
    ) -> int:
        """Pull every v1 entity type (dependency order) and apply locally.

        The whole pull-apply runs with ``sync_in_progress`` set so the
        outbox capture triggers do not echo the pulled writes.

        ``skip_local_ids`` (Phase 4a P2): a set of ``(entity_type,
        local_id)`` pairs whose outbox rows are still pending.  Rows mapped
        to those local ids are SKIPPED — the local row has unpushed edits
        (or is locally deleted) and applying the server row would clobber
        them or resurrect a deleted row.

        ``should_stop`` (Phase 4a R4): an optional callable returning True
        when the caller wants the pull to abort (e.g. engine shutdown).
        Checked between entities and between pages so a long paginated pull
        exits promptly.  ``None`` (default) disables the checks.

        ``device_id`` (Phase A): the per-install device id, sent as a query
        param on every pull request so the server can associate the pull
        with the device.

        ``user_id`` (Phase E): switch the cursor namespace to this user
        before pulling (per-user delta cursors).

        ``force_full_sync`` (Phase E): ignore the stored cursors and do a
        full keyset refresh for every entity this cycle (manual resync /
        tests).  Cursors are still re-stored from the fresh results.

        Returns the total number of records actually applied.
        """
        if user_id is not None:
            self.set_user(user_id)
        self.last_delta_count = 0
        self.last_full_refresh_count = 0
        outbox = SyncOutboxService(self.db)
        outbox.set_sync_in_progress(True)
        total = 0
        try:
            for entity_type in _PULL_ORDER:
                if should_stop is not None and should_stop():
                    break
                cursor_state = None if force_full_sync else self._get_cursor(entity_type)
                cursor = cursor_state[0] if cursor_state else None
                if cursor:
                    self.last_delta_count += 1
                else:
                    self.last_full_refresh_count += 1
                total += self.pull_entity(
                    entity_type,
                    skip_local_ids=skip_local_ids,
                    should_stop=should_stop,
                    device_id=device_id,
                    use_cursor=not force_full_sync,
                )
            # Phase D (tombstones): hard-delete propagation for rows that
            # devices never pulled.  Runs inside the echo-suppression window
            # so the local hard-deletes do not re-capture outbox rows.  Only
            # when the entity loop was NOT aborted by a stop request.
            if should_stop is None or not should_stop():
                total += self.pull_tombstones(
                    should_stop=should_stop, device_id=device_id,
                )
        finally:
            outbox.set_sync_in_progress(False)
        return total

    def apply_server_row(self, entity_type: str, server_row: Dict[str, Any]) -> bool:
        """Apply a single server row to the local DB (conflict resolution).

        Public wrapper around :meth:`_upsert_record` used by the conflict
        journal's "Take server" action.  Runs with echo suppression enabled
        (like the pull lane) so the apply does not re-capture outbox rows or
        restamp ``updated_at``.  Returns True if applied, False if skipped.
        """
        outbox = SyncOutboxService(self.db)
        outbox.set_sync_in_progress(True)
        try:
            return self._upsert_record(entity_type, server_row)
        finally:
            outbox.set_sync_in_progress(False)

    def pull_entity(
        self,
        entity_type: str,
        skip_local_ids: Optional[set] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        device_id: Optional[str] = None,
        since: Optional[str] = None,
        use_cursor: bool = True,
        store_cursor: bool = True,
    ) -> int:
        """Pull a single entity type (paginated) and apply locally.

        Used by the sync engine for incremental refresh.  Echo suppression
        is enabled for the duration of the apply.  Returns the number of
        records actually applied (skipped rows are not counted).

        ``should_stop`` (Phase 4a R4): an optional callable returning True
        when the caller wants the pull to abort.  Checked between pages so a
        long paginated pull exits promptly on shutdown.  ``None`` (default)
        disables the check.

        ``device_id`` (Phase A): the per-install device id, sent as a query
        param on every pull request.

        ``since`` / ``use_cursor`` / ``store_cursor`` (Phase E — delta pull):
        when ``since`` is None and ``use_cursor`` is True, the stored per-user
        cursor is used (first sync / no cursor → full keyset refresh).  The
        new cursor (max ``updated_at`` seen, server-provided when available)
        is stored per-user unless ``store_cursor`` is False.

        Cursor safety: if ANY record in the response raises during apply, the
        cursor is NOT advanced (the failed row would otherwise be lost until a
        manual resync — the next cycle re-pulls from the old watermark).  If
        the delta request itself fails, we fall back to a full refresh for
        this entity (schema change / clock skew) and re-store the cursor.
        """
        outbox = SyncOutboxService(self.db)
        outbox.set_sync_in_progress(True)
        count = 0
        had_failure = False
        stopped = False
        try:
            since_id = 0
            if since is None and use_cursor:
                cursor_state = self._get_cursor(entity_type)
                if cursor_state is not None:
                    # R1: resume from the stored watermark — ``since`` is the
                    # timestamp and ``last_id`` is the id tiebreak for that
                    # second.  The delta resends ``since_id`` so a row stamped
                    # at EXACTLY the cursor second (id > since_id) is not
                    # permanently missed.  ``after_id`` still scans from 0 —
                    # the timestamp filter is what selects the rows; skipping
                    # ids would miss updated rows with smaller ids.
                    since, since_id = cursor_state
            new_cursor = since or ""
            after_id = 0
            last_id = 0
            while True:
                # R4: abort between pages when a stop was requested (e.g.
                # engine shutdown) — a large company's pull can span many
                # pages and must not outlive the engine thread.
                if should_stop is not None and should_stop():
                    # R2: a mid-pagination abort must NOT persist the cursor —
                    # the un-pulled tail would be permanently stranded (the
                    # next cycle redoes a full refresh for this entity).
                    stopped = True
                    break
                params: Dict[str, Any] = {
                    "entity": entity_type,
                    "after_id": after_id,
                    "limit": self.page_size,
                    "device_id": device_id,
                }
                if since:
                    params["since"] = since
                    params["since_id"] = since_id
                try:
                    resp = self.api_client.get("/api/v1/sync/pull", params=params) or {}
                except Exception as exc:
                    if since:
                        # Phase E: delta pull failed (schema change, clock
                        # skew, transient error) → fall back to a full refresh
                        # for this entity; the cursor is re-derived from the
                        # fresh results.
                        logger.warning(
                            "pull: delta fetch failed for %s (%s) — "
                            "falling back to full refresh", entity_type, exc,
                        )
                        since = None
                        new_cursor = ""
                        since_id = 0
                        after_id = 0
                        continue
                    raise
                records = resp.get("records") or []
                # Phase E: advance the watermark to the max updated_at seen
                # (server-provided cursor preferred — avoids re-deriving).
                page_cursor = resp.get("cursor") or ""
                if page_cursor and page_cursor > new_cursor:
                    new_cursor = page_cursor
                for record in records:
                    # C2: one bad row must never abort the whole cycle — log
                    # and continue (the next cycle retries the row).
                    try:
                        ok = self._upsert_record(entity_type, record, skip_local_ids=skip_local_ids)
                        if ok:
                            count += 1
                        elif self._last_skip_reason in ("unmapped_fk", "no_columns"):
                            # C2-skip (unmapped NOT NULL FK / no writable
                            # columns): the row was NOT applied.  Do NOT
                            # advance the cursor — the next cycle self-heals
                            # when the parent arrives.  (P2 pending-outbox
                            # skips DO advance — the local row is
                            # authoritative until its own edits are pushed.)
                            had_failure = True
                    except Exception as exc:
                        had_failure = True
                        logger.warning(
                            "pull: record for %s server_id=%s failed, skipping: %s",
                            entity_type, record.get("id"), exc,
                        )
                    ts = record.get("updated_at")
                    if ts and str(ts) > new_cursor:
                        new_cursor = str(ts)
                next_after_id = resp.get("next_after_id", after_id)
                # R1: the id watermark for the cursor second = the last id
                # seen in this pull (the final pagination position).
                last_id = next_after_id
                has_more = bool(resp.get("has_more"))
                if not records or not has_more or next_after_id <= after_id:
                    break
                after_id = next_after_id
        finally:
            outbox.set_sync_in_progress(False)
        if store_cursor and new_cursor and not had_failure and not stopped:
            self._set_cursor(entity_type, new_cursor, last_id)
        return count

    # ── Tombstones (Phase D: hard-delete propagation) ─────────────────

    def pull_tombstones(
        self,
        should_stop: Optional[Callable[[], bool]] = None,
        device_id: Optional[str] = None,
    ) -> int:
        """Pull the server's hard-delete tombstones and apply them locally.

        Each tombstone says "server row (entity_type, server_id) is gone".
        We hard-delete the local row (when mapped), clear the ``sync_id_map``
        entry, and drop any pending outbox rows for that local row.  The
        server deletes the tombstones after returning them (one-shot), so a
        missed tombstone is simply re-recorded by the next hard-delete op.

        Echo suppression: the whole apply runs with ``sync_in_progress`` set
        (the caller's ``pull_all`` window, or this method's own — see
        :meth:`pull_tombstones_standalone`) so the outbox DELETE triggers do
        not re-capture the server-authoritative removal.
        """
        resp = self.api_client.get(
            "/api/v1/sync/pull",
            params={
                "entity": "tombstone",
                "limit": 1000,
                "device_id": device_id,
            },
        ) or {}
        records = resp.get("records") or []
        count = 0
        for t in records:
            if should_stop is not None and should_stop():
                break
            entity_type = t.get("entity_type")
            server_id = t.get("server_id")
            table = self._entity_table(entity_type)
            if table is None or server_id is None:
                logger.warning(
                    "tombstone: unknown entity %r server_id=%s, skipping",
                    entity_type, server_id,
                )
                continue
            mapping = self._lookup_mapping(entity_type, server_id)
            if mapping is None:
                # Never pulled → nothing to delete locally.
                continue
            try:
                # Server says this row is gone — hard-delete (the row's own
                # DELETE propagation via the entity pull would have soft-
                # deleted it; this is the final drop).
                self.db.conn.execute(
                    f"DELETE FROM {table} WHERE id = ?", (mapping,)
                )
                self.db.conn.execute(
                    "DELETE FROM sync_id_map WHERE entity_type = ? AND server_id = ?",
                    (entity_type, server_id),
                )
                # Drop stale pending outbox rows for this local row — a
                # DELETE/UPDATE that was queued before the server removed the
                # row would otherwise push into a void (or resurrect it).
                self.db.conn.execute(
                    "UPDATE sync_outbox SET synced_at = ? "
                    "WHERE entity_type = ? AND local_id = ? AND synced_at IS NULL",
                    (utc_now_iso(), entity_type, mapping),
                )
                self.db.conn.commit()
                count += 1
            except Exception as exc:
                logger.warning(
                    "tombstone apply failed for %s/%s: %s", entity_type, server_id, exc,
                )
        self.last_tombstone_count = count
        return count

    def pull_tombstones_standalone(
        self,
        should_stop: Optional[Callable[[], bool]] = None,
        device_id: Optional[str] = None,
    ) -> int:
        """Pull tombstones with their OWN echo-suppression window.

        :meth:`pull_all` already runs inside a suppression window and calls
        :meth:`pull_tombstones` directly; this wrapper exists for callers
        that pull tombstones outside ``pull_all``.
        """
        outbox = SyncOutboxService(self.db)
        outbox.set_sync_in_progress(True)
        try:
            return self.pull_tombstones(
                should_stop=should_stop, device_id=device_id,
            )
        finally:
            outbox.set_sync_in_progress(False)

    # ── Upsert ────────────────────────────────────────────────────────

    def _upsert_record(
        self,
        entity_type: str,
        server_row: Dict[str, Any],
        skip_local_ids: Optional[set] = None,
    ) -> bool:
        """Upsert one server row locally.  Returns True if applied, False if skipped."""
        self._last_skip_reason = None
        table = self._entity_table(entity_type)
        if table is None:
            logger.warning("pull: unknown entity_type %r, skipping", entity_type)
            self._last_skip_reason = "invalid"
            return False
        server_id = server_row.get("id")
        if server_id is None:
            self._last_skip_reason = "invalid"
            return False
        local_cols = self._local_columns(table)
        mapping = self._lookup_mapping(entity_type, server_id)
        # Phase D (route history): fingerprint-based natural-key adoption.
        # The same route recomputed on another device has the SAME
        # route_fingerprint — a local row with that fingerprint (never pulled,
        # or tracked under a now-stale server row) is the same logical route,
        # so we adopt it (update + map) instead of inserting a duplicate.
        # ``adopted`` marks a mapping that did not exist before — it must be
        # recorded once the row is applied.
        adopted = False
        if mapping is None and entity_type == "route_history":
            fp = server_row.get("route_fingerprint")
            if fp:
                local = self.db.conn.execute(
                    "SELECT id FROM route_history_v2 WHERE route_fingerprint = ?",
                    (fp,),
                ).fetchone()
                if local is not None:
                    mapping = local["id"]
                    adopted = True

        # P2: skip rows with a pending outbox op — the local row has unpushed
        # edits (or is locally deleted); applying the server row would clobber
        # them or resurrect a deleted row.
        if skip_local_ids and mapping is not None and (entity_type, mapping) in skip_local_ids:
            logger.debug(
                "pull: skipping %s local_id=%s (pending outbox op)",
                entity_type, mapping,
            )
            self._last_skip_reason = "pending_outbox"
            return False

        # Soft-delete propagation: a server row with deleted_at set means the
        # row was deleted on the server.  Soft-delete the local row instead of
        # upserting active data.  If the local row was never pulled there is
        # nothing to delete locally (and no local_id to record a mapping for) —
        # skip; the mapping is created when the row is first pulled as active.
        if server_row.get("deleted_at"):
            if mapping is not None:
                if "deleted_at" in local_cols:
                    # S4: stamp updated_at alongside deleted_at so a later
                    # stale UPDATE from another device conflicts instead of
                    # silently writing into a deleted row (mirrors the
                    # server's R7 behavior).  The stamping triggers are
                    # suppressed during pull-apply, so set it explicitly.
                    self.db.conn.execute(
                        f"UPDATE {table} SET deleted_at = ?, updated_at = ? WHERE id = ?",
                        (server_row["deleted_at"], utc_now_iso(), mapping),
                    )
                else:
                    # No deleted_at column (e.g. client_tags) → hard delete.
                    self.db.conn.execute(
                        f"DELETE FROM {table} WHERE id = ?", (mapping,)
                    )
                if adopted:
                    self._record_mapping(entity_type, mapping, server_id)
                self.db.conn.commit()
            return True

        data = self._translate_fks(entity_type, server_row)

        # C2: a NOT NULL FK column that comes back unmapped (parent not pulled
        # yet — e.g. a conflicted or absent parent) would raise IntegrityError
        # on write and, uncaught, abort the whole pull cycle.  Skip the row;
        # the next cycle self-heals when the parent is pulled.
        required_fk_cols = {col for (ent, col) in _FK_REFERENCES if ent == entity_type}
        if entity_type == "document":
            required_fk_cols.add("entity_id")       # polymorphic (nullable)
        if entity_type == "document_link":
            required_fk_cols.add("linked_entity_id")  # polymorphic (NOT NULL)
        notnull = self._notnull_columns(table)
        for col in required_fk_cols:
            if (
                col in notnull
                and server_row.get(col) is not None
                and data.get(col) is None
            ):
                logger.debug(
                    "pull: skipping %s server_id=%s — NOT NULL FK %s unmapped",
                    entity_type, server_id, col,
                )
                self._last_skip_reason = "unmapped_fk"
                return False

        # Column filtering: only write columns that exist locally; never
        # overwrite the local id or company_id (company scope is local).
        data = {
            k: v for k, v in data.items()
            if k in local_cols and k not in ("id", "company_id")
        }
        # Phase C: never persist the server's file_path locally — it is
        # meaningless on this desktop and would shadow a same-named local file
        # with wrong content (R5).  The document-binary pull downloads to the
        # desktop convention and sets file_path; brand-new pulled rows start
        # with an empty NOT NULL placeholder.
        if entity_type == "document":
            data.pop("file_path", None)
            if mapping is None:
                data["file_path"] = ""
        # R3 (optional): never write a NULL updated_at over a local stamp —
        # the pulled row may be older than the local row's last write; a NULL
        # would clobber the local conflict-detection timestamp.  The server
        # keeps its NULL until the backfill script stamps it.
        if data.get("updated_at") is None:
            data.pop("updated_at", None)
        if not data:
            logger.warning(
                "pull: no writable columns for %s server_id=%s, skipping",
                entity_type, server_id,
            )
            self._last_skip_reason = "no_columns"
            return False

        if mapping is not None:
            affected = self._update_local(table, mapping, data)
            if affected == 0:
                # Local row was hard-deleted but the mapping survived → the
                # server row is authoritative; re-insert and remap.
                # documents.file_path is NOT NULL — restore a placeholder
                # (empty; the binary pull fills it in).
                if entity_type == "document" and "file_path" not in data:
                    data["file_path"] = ""
                local_id = self._insert_local(table, data)
                self._record_mapping(entity_type, local_id, server_id)
            elif adopted:
                # Fingerprint adoption: the existing local row is now mapped
                # to this server row (route_history natural-key convergence).
                self._record_mapping(entity_type, mapping, server_id)
        else:
            local_id = self._insert_local(table, data)
            self._record_mapping(entity_type, local_id, server_id)
        return True

    # ── Helpers ───────────────────────────────────────────────────────

    def _entity_table(self, entity_type: str) -> Optional[str]:
        """Resolve a SINGULAR entity type (e.g. ``'trip'``) to its table name."""
        return _ENTITY_TYPE_TO_TABLE.get(entity_type)

    def _local_columns(self, table: str) -> set:
        """Return the set of columns that exist in the local table (cached)."""
        if table not in self._column_cache:
            try:
                cols = [
                    r[1]
                    for r in self.db.conn.execute(f"PRAGMA table_info({table})").fetchall()
                ]
            except Exception as e:
                logger.warning("pull: could not introspect %s: %s", table, e)
                cols = []
            self._column_cache[table] = set(cols)
        return self._column_cache[table]

    def _notnull_columns(self, table: str) -> set:
        """Return the set of NOT NULL columns in the local table (cached).

        C2: used to detect unmapped required FKs — a NOT NULL FK that the
        parent lookup failed to resolve would raise IntegrityError on write,
        so such rows are skipped (self-healing on the next cycle).
        """
        if table not in self._notnull_cache:
            try:
                cols = {
                    r[1]
                    for r in self.db.conn.execute(f"PRAGMA table_info({table})").fetchall()
                    if r[3]  # the notnull flag
                }
            except Exception as e:
                logger.warning("pull: could not introspect NOT NULL cols for %s: %s", table, e)
                cols = set()
            self._notnull_cache[table] = cols
        return self._notnull_cache[table]

    def _lookup_mapping(self, entity_type: str, server_id: int) -> Optional[int]:
        """Return the local id mapped to (entity_type, server_id), or None."""
        row = self.db.conn.execute(
            "SELECT local_id FROM sync_id_map "
            "WHERE entity_type = ? AND server_id = ?",
            (entity_type, server_id),
        ).fetchone()
        return row["local_id"] if row else None

    def _record_mapping(self, entity_type: str, local_id: int, server_id: int) -> None:
        """Record the (entity_type, local_id) ↔ server_id mapping.

        ``INSERT OR REPLACE`` so a remap (local row re-inserted after a hard
        delete) updates the existing (entity_type, server_id) row instead of
        being ignored.
        """
        self.db.conn.execute(
            "INSERT OR REPLACE INTO sync_id_map "
            "(entity_type, local_id, server_id, created_at) VALUES (?, ?, ?, ?)",
            (entity_type, local_id, server_id, utc_now_iso()),
        )
        self.db.conn.commit()

    def _translate_fks(self, entity_type: str, server_row: Dict[str, Any]) -> Dict[str, Any]:
        """Translate server-side FK ids to local ids via ``sync_id_map``.

        Unmapped references (parent not pulled yet) are left NULL — the next
        pull fixes them (self-healing).
        """
        data = dict(server_row)
        for (ent, col), ref_entity in _FK_REFERENCES.items():
            if ent != entity_type:
                continue
            server_fk = data.get(col)
            if server_fk is None:
                continue
            data[col] = self._lookup_mapping(ref_entity, server_fk)
        # P5: document.entity_id is polymorphic — the referenced entity type
        # depends on the row's entity_type column.  Translate only when it is
        # one of the v1 entities; otherwise leave the value as-is.
        if entity_type == "document":
            ref = data.get("entity_type")
            if ref in _DOCUMENT_REF_ENTITIES and data.get("entity_id") is not None:
                data["entity_id"] = self._lookup_mapping(ref, data["entity_id"])
        # C1: document_links.linked_entity_id is the same polymorphic pattern
        # (paired with linked_entity_type) — translate it for the reference set.
        if entity_type == "document_link":
            ref = data.get("linked_entity_type")
            if ref in _DOCUMENT_REF_ENTITIES and data.get("linked_entity_id") is not None:
                data["linked_entity_id"] = self._lookup_mapping(ref, data["linked_entity_id"])
        return data

    def _insert_local(self, table: str, data: Dict[str, Any]) -> int:
        cols = list(data.keys())
        col_list = ", ".join(cols)
        placeholders = ", ".join("?" for _ in cols)
        cur = self.db.conn.execute(
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
            tuple(data[c] for c in cols),
        )
        self.db.conn.commit()
        return cur.lastrowid

    def _update_local(self, table: str, local_id: int, data: Dict[str, Any]) -> int:
        if not data:
            return 0
        sets = ", ".join(f"{c} = ?" for c in data)
        cur = self.db.conn.execute(
            f"UPDATE {table} SET {sets} WHERE id = ?",
            tuple(data[c] for c in data) + (local_id,),
        )
        self.db.conn.commit()
        return cur.rowcount