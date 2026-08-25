"""Offline-first sync endpoints (Phase 2 — push).

The desktop app captures local SQLite writes into a ``sync_outbox`` (Phase 1)
and pushes them here.  This module implements:

* ``POST /api/v1/sync/push`` — apply a batch of outbox items exactly-once.
  ``sync_server_map`` maps a desktop ``(company_id, entity_type, local_id)``
  to the server row id, so a replayed INSERT (retry after a network drop)
  updates the mapped row instead of creating a duplicate.
* ``GET /api/v1/sync/pull`` — minimal Phase 3 stub: company-scoped rows for
  an entity with ``id > after_id``, ordered by id, including soft-deleted
  rows (``deleted_at`` set).

Writes go through the backend repositories (``backend/repositories/*``) —
NOT the services layer, which would re-fire EventBus events, audit logs and
the server-side ops engine (double-processing).  Entities whose repository
API is positional-only (documents, receipts, maintenance records/schedules)
and entities without a repository (expenses) are written with direct
``db.execute`` against the repository's column whitelist (the same
``COLUMNS`` pattern the repositories use for injection-safe writes).

``company_id`` always comes from the JWT (``current_user``) — never from the
payload.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.repositories.client_repository import ClientRepository
from backend.repositories.document_repository import DocumentRepository
from backend.repositories.driver_repository import DriverRepository
from backend.repositories.fleet_repository import FleetRepository
from backend.repositories.invoice_repository import InvoiceRepository
from backend.repositories.receipt_repository import ReceiptRepository
from backend.repositories.trip_repository import TripRepository
from database.time_utils import utc_now_iso

router = APIRouter(prefix="/sync", tags=["sync"])

# ── Shared contract (must match the desktop Phase 1 lane exactly) ────────
# Phase B: all 25 entity types in the v1 push scope.  Anything else gets
# status "error" with "unsupported entity type" (the desktop keeps those
# items queued).
SUPPORTED_ENTITY_TYPES = {
    "trip",
    "client",
    "driver",
    "truck",
    "maintenance_record",
    "maintenance_schedule",
    "document",
    "invoice",
    "receipt",
    "expense",
    # Phase B (entity completeness): the 15 previously unsupported entities
    "proforma_invoice",
    "contract",
    "client_contact",
    "client_tag",
    "driver_truck_assignment",
    "tacho_import",
    "tacho_driver_activity",
    "tacho_vehicle_data",
    "successive_carrier",
    "trip_status_history",
    "document_link",
    "document_version",
    "sent_email",
    "email_log",
    "invoice_reminder",
    # Phase D (sync completeness): route history — fingerprint-deduped
    # (derived data; sync is best-effort convergence).
    "route_history",
}

# Tables that support soft-delete (have a ``deleted_at`` column).  Phase B
# added ``deleted_at`` to expenses, so its DELETE soft-deletes too.
_SOFT_DELETE_TABLES = {
    "trips",
    "clients",
    "drivers",
    "trucks",
    "maintenance_records",
    "maintenance_schedules",
    "documents",
    "invoices",
    "receipts",
    "contracts",
    "proforma_invoices",
    "expenses",
    "route_history_v2",
}

# Expenses has no backend repository — column whitelist mirrors the
# repository COLUMNS pattern (see database/schema.py TABLE_EXPENSES).
EXPENSE_COLUMNS = [
    "id", "truck_id", "date", "category", "description", "amount",
    "company_id", "created_at", "updated_at", "deleted_at",
]

# ── Phase B: column whitelists for the 15 newly synced entities ──────────
# All lack a dict-based backend repository (or their repo API is
# positional-only), so they are written with direct SQL against these
# whitelists — the same pattern as EXPENSE_COLUMNS / maintenance.
# Column lists mirror the actual table schemas in database/schema.py.
PROFORMA_COLUMNS = [
    "id", "proforma_number", "issue_date", "valid_until", "client_name",
    "client_address", "client_vat", "client_phone", "client_email",
    "description", "notes", "line_items_json", "subtotal", "discount_type",
    "discount_value", "discount_amount", "tax_rate", "tax_amount",
    "grand_total", "currency", "mode", "status", "logo_path",
    "signature_path", "stamp_path", "company_color", "created_at",
    "updated_at", "company_id", "deleted_at",
]
CONTRACT_COLUMNS = [
    "id", "document_id", "client_id", "contract_type", "start_date",
    "end_date", "value_eur", "payment_terms", "auto_renewal",
    "renewal_notice_days", "status", "notes", "created_at", "updated_at",
    "company_id", "deleted_at",
]
CLIENT_CONTACT_COLUMNS = [
    "id", "client_id", "contact_type", "full_name", "title", "phone",
    "email", "is_primary", "notes", "created_at", "updated_at", "company_id",
]
CLIENT_TAG_COLUMNS = [
    "id", "client_id", "tag", "updated_at", "company_id",
]
DRIVER_TRUCK_ASSIGNMENT_COLUMNS = [
    "id", "driver_id", "truck_id", "assigned_at", "active", "updated_at",
    "company_id",
]
TACHO_IMPORT_COLUMNS = [
    "id", "imported_at", "file_name", "file_type", "file_hash", "truck_id",
    "driver_id", "parse_status", "raw_json", "notes", "updated_at",
    "company_id",
]
TACHO_DRIVER_ACTIVITY_COLUMNS = [
    "id", "import_id", "driver_id", "activity_date", "driving_minutes",
    "work_minutes", "rest_minutes", "avail_minutes", "distance_km",
    "violations", "country_codes", "updated_at", "company_id",
]
TACHO_VEHICLE_DATA_COLUMNS = [
    "id", "import_id", "truck_id", "vu_serial_number", "calibration_date",
    "calibration_expiry", "odometer_km", "k_factor", "w_factor",
    "speed_violations", "recorded_from", "recorded_to", "updated_at",
    "company_id",
]
SUCCESSIVE_CARRIER_COLUMNS = [
    "id", "trip_id", "company_id", "sequence_order", "carrier_name",
    "carrier_address", "carrier_country", "vehicle_plate", "trailer_plate",
    "driver_name", "from_location", "to_location", "updated_at",
]
TRIP_STATUS_HISTORY_COLUMNS = [
    "id", "trip_id", "old_status", "new_status", "trigger", "created_at",
    "updated_at", "company_id",
]
DOCUMENT_LINK_COLUMNS = [
    "id", "document_id", "linked_entity_type", "linked_entity_id",
    "relation_type", "created_at", "updated_at", "company_id",
]
DOCUMENT_VERSION_COLUMNS = [
    "id", "document_id", "version_number", "file_path", "file_size",
    "file_hash", "comment", "uploaded_by", "created_at", "updated_at",
    "company_id",
]
SENT_EMAIL_COLUMNS = [
    "id", "document_id", "recipient", "status", "sent_at", "created_at",
    "updated_at", "company_id",
]
EMAIL_LOG_COLUMNS = [
    "id", "trip_id", "recipient", "subject", "timestamp", "status",
    "error_msg", "updated_at", "company_id",
]
INVOICE_REMINDER_COLUMNS = [
    "id", "invoice_id", "trip_id", "reminder_type", "days_offset", "sent_at",
    "recipient_email", "status", "updated_at", "company_id",
]
# Phase D (sync completeness): route_history_v2.  ``geometry_compressed`` is
# an opaque zlib BLOB (BYTEA on PG) that cannot travel through the JSON sync
# payload — it is EXCLUDED here so push never writes it and pull never
# serializes it (the derived geometry can be recomputed locally from
# stops_json / fingerprint; sync is best-effort convergence).
ROUTE_HISTORY_COLUMNS = [
    "id", "route_fingerprint", "metadata_version", "created_at",
    "last_calculated_at", "calculation_count", "stops_json",
    "geometry_encoding", "total_distance_km", "duration_min",
    "truck_id", "truck_label", "truck_json", "profile",
    "excluded_countries_json", "toll_estimates_json", "fuel_estimates_json",
    "profit_estimates_json", "countries_traversed_json",
    "route_summary_json", "archived_at", "is_committed",
    "company_id", "updated_at", "deleted_at",
]
ROUTE_HISTORY_EXCLUDE_COLUMNS = ["geometry_compressed"]

# Per-entity config: table name, backend repository (None → direct SQL),
# column whitelist, and whether create/update take ``company_id`` as a
# keyword argument (driver/fleet) instead of a data-dict column.
_ENTITY_CONFIG: Dict[str, Dict[str, Any]] = {
    "trip": {
        "table": "trips",
        "repo": TripRepository,
        "columns": TripRepository.COLUMNS,
        "company_id_param": False,
    },
    "client": {
        "table": "clients",
        "repo": ClientRepository,
        "columns": ClientRepository.COLUMNS,
        "company_id_param": False,
    },
    "driver": {
        "table": "drivers",
        "repo": DriverRepository,
        "columns": DriverRepository.COLUMNS,
        "company_id_param": True,
    },
    "truck": {
        "table": "trucks",
        "repo": FleetRepository,
        "columns": FleetRepository.COLUMNS,
        "company_id_param": True,
    },
    "maintenance_record": {
        "table": "maintenance_records",
        "repo": None,
        "columns": FleetRepository.COLUMNS_MAINT_RECORDS,
        "company_id_param": False,
    },
    "maintenance_schedule": {
        "table": "maintenance_schedules",
        "repo": None,
        "columns": FleetRepository.COLUMNS_MAINT_SCHEDULES,
        "company_id_param": False,
    },
    "document": {
        "table": "documents",
        "repo": None,
        "columns": DocumentRepository.COLUMNS,
        "company_id_param": False,
    },
    "invoice": {
        "table": "invoices",
        "repo": InvoiceRepository,
        "columns": InvoiceRepository.COLUMNS,
        "company_id_param": False,
    },
    "receipt": {
        "table": "receipts",
        "repo": None,
        "columns": ReceiptRepository.COLUMNS,
        "company_id_param": False,
    },
    "expense": {
        "table": "expenses",
        "repo": None,
        "columns": EXPENSE_COLUMNS,
        "company_id_param": False,
    },
    # ── Phase B: the 15 previously unsupported entities ──────────────
    # All use direct SQL with column whitelists — none of the backend
    # repositories expose a dict-based create+update for them.
    "proforma_invoice": {
        "table": "proforma_invoices",
        "repo": None,
        "columns": PROFORMA_COLUMNS,
        "company_id_param": False,
    },
    "contract": {
        "table": "contracts",
        "repo": None,
        "columns": CONTRACT_COLUMNS,
        "company_id_param": False,
    },
    "client_contact": {
        "table": "client_contacts",
        "repo": None,
        "columns": CLIENT_CONTACT_COLUMNS,
        "company_id_param": False,
    },
    "client_tag": {
        "table": "client_tags",
        "repo": None,
        "columns": CLIENT_TAG_COLUMNS,
        "company_id_param": False,
    },
    "driver_truck_assignment": {
        "table": "driver_truck_assignments",
        "repo": None,
        "columns": DRIVER_TRUCK_ASSIGNMENT_COLUMNS,
        "company_id_param": False,
    },
    "tacho_import": {
        "table": "tacho_imports",
        "repo": None,
        "columns": TACHO_IMPORT_COLUMNS,
        "company_id_param": False,
    },
    "tacho_driver_activity": {
        "table": "tacho_driver_activity",
        "repo": None,
        "columns": TACHO_DRIVER_ACTIVITY_COLUMNS,
        "company_id_param": False,
    },
    "tacho_vehicle_data": {
        "table": "tacho_vehicle_data",
        "repo": None,
        "columns": TACHO_VEHICLE_DATA_COLUMNS,
        "company_id_param": False,
    },
    "successive_carrier": {
        "table": "successive_carriers",
        "repo": None,
        "columns": SUCCESSIVE_CARRIER_COLUMNS,
        "company_id_param": False,
    },
    "trip_status_history": {
        "table": "trip_status_history",
        "repo": None,
        "columns": TRIP_STATUS_HISTORY_COLUMNS,
        "company_id_param": False,
    },
    "document_link": {
        "table": "document_links",
        "repo": None,
        "columns": DOCUMENT_LINK_COLUMNS,
        "company_id_param": False,
    },
    "document_version": {
        "table": "document_versions",
        "repo": None,
        "columns": DOCUMENT_VERSION_COLUMNS,
        "company_id_param": False,
    },
    "sent_email": {
        "table": "sent_emails",
        "repo": None,
        "columns": SENT_EMAIL_COLUMNS,
        "company_id_param": False,
        # D1: UNIQUE(document_id, recipient) is the dedup intent — a desktop
        # INSERT colliding with an existing row (from any device) is treated
        # as "already exists" and returns the existing row's id instead of
        # erroring and retrying forever.
        "unique_lookup": ("document_id", "recipient"),
    },
    "email_log": {
        "table": "email_logs",
        "repo": None,
        "columns": EMAIL_LOG_COLUMNS,
        "company_id_param": False,
    },
    "invoice_reminder": {
        "table": "invoice_reminders",
        "repo": None,
        "columns": INVOICE_REMINDER_COLUMNS,
        "company_id_param": False,
    },
    # Phase D (sync completeness): route history.  Direct SQL with a column
    # whitelist (no dict-based backend repo).  ``natural_key`` = route
    # fingerprint: a push INSERT whose fingerprint already exists on the
    # server updates that row instead of creating a duplicate — the same
    # route recalculated on another device must converge, not multiply.
    # ``exclude_columns`` keeps the geometry BLOB out of pull responses.
    "route_history": {
        "table": "route_history_v2",
        "repo": None,
        "columns": ROUTE_HISTORY_COLUMNS,
        "company_id_param": False,
        "natural_key": "route_fingerprint",
        "exclude_columns": ROUTE_HISTORY_EXCLUDE_COLUMNS,
    },
}


# ── Pydantic models ──────────────────────────────────────────────────────

class SyncPushItem(BaseModel):
    entity_type: str
    op: Literal["INSERT", "UPDATE", "DELETE"]
    local_id: int
    payload: Dict[str, Any] = Field(default_factory=dict)
    base_updated_at: Optional[str] = None


class SyncPushRequest(BaseModel):
    items: List[SyncPushItem]
    device_id: str


class SyncPushResult(BaseModel):
    local_id: int
    server_id: Optional[int] = None
    status: Literal["ok", "conflict", "error", "gone"]
    error: Optional[str] = None
    server_row: Optional[Dict[str, Any]] = None


class SyncPushResponse(BaseModel):
    results: List[SyncPushResult]


# ── Timestamp helpers ────────────────────────────────────────────────────

def _ts_to_compare(value: Any) -> str:
    """Normalize a server-side ``updated_at`` to a comparable canonical string.

    PostgreSQL returns ``TIMESTAMPTZ`` columns as ``datetime`` objects;
    SQLite returns the stored TEXT.  Both are normalized to the canonical
    ``YYYY-MM-DDTHH:MM:SSZ`` UTC form so string comparison is valid.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def _normalize_row(row: Optional[Dict[str, Any]], exclude: Optional[set] = None) -> Optional[Dict[str, Any]]:
    """Convert datetime values in a row dict to canonical UTC strings.

    ``exclude`` (Phase D): a set of columns to drop from the output — used to
    keep non-JSON-serializable values (e.g. route_history_v2's
    geometry_compressed BLOB) out of conflict ``server_row`` payloads.
    """
    if not row:
        return row
    out: Dict[str, Any] = {}
    for key, value in row.items():
        if exclude and key in exclude:
            continue
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            out[key] = value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            out[key] = value
    return out


# ── sync_server_map helpers ──────────────────────────────────────────────
# Phase A (multi-device): the map key is (company_id, device_id, entity_type,
# local_id) so each desktop has its own id-map namespace.  Two desktops with
# colliding local ids map to distinct server rows instead of overwriting each
# other.  device_id comes from the request body (a user may have multiple
# devices), never from the JWT.

def _lookup_mapping(db: DatabaseManager, company_id: int, device_id: str, entity_type: str, local_id: int) -> Optional[int]:
    """Return the mapped server_id for (company, device, entity, local_id), or None."""
    row = db.execute(
        "SELECT server_id FROM sync_server_map "
        "WHERE company_id = ? AND device_id = ? AND entity_type = ? AND local_id = ?",
        (company_id, device_id, entity_type, local_id),
    ).fetchone()
    return row["server_id"] if row else None


def _resolve_mapping(db: DatabaseManager, company_id: int, device_id: str, entity_type: str, local_id: int) -> Optional[int]:
    """Resolve the server_id for (company, device, entity, local_id).

    Falls back to a one-time adoption of the legacy single-device (V1)
    namespace (``device_id = ''``): the Phase A migration parks pre-existing
    maps under ``''``, and the upgraded desktop never sends ``''`` again, so
    without adoption it could never UPDATE/DELETE its pre-existing rows.  On
    adoption the legacy map row is re-pointed at the new device_id.

    Adoption assumes V1's single-device reality.  If a company truly ran two
    desktops pre-migration, the first toucher claims the legacy row
    (acceptable — the other device's INSERT for the same local_id gets its
    own fresh row).
    """
    row = _lookup_mapping(db, company_id, device_id, entity_type, local_id)
    if row is not None:
        return row
    legacy = _lookup_mapping(db, company_id, "", entity_type, local_id)
    if legacy is not None:
        try:
            db.execute(
                "UPDATE sync_server_map SET device_id = ? "
                "WHERE company_id = ? AND device_id = '' AND entity_type = ? AND local_id = ?",
                (device_id, company_id, entity_type, local_id),
            )
            db.commit()
        except Exception:
            # A concurrent device already re-created the row → its namespace
            # wins; the legacy row is gone, so fall through to the caller's
            # normal handling.
            pass
        return legacy
    return None


def _insert_mapping(db: DatabaseManager, company_id: int, device_id: str, entity_type: str, local_id: int, server_id: int, commit: bool = True) -> None:
    """Record the (company, device, entity, local_id) → server_id mapping.

    ``INSERT OR IGNORE`` (SQLite) / ``ON CONFLICT DO NOTHING`` (PostgreSQL)
    makes a concurrent duplicate mapping a no-op instead of a UNIQUE error.

    ``commit=False`` defers the commit to the caller — used when the caller
    owns the enclosing transaction (the atomic INSERT+mapping seam in
    ``_process_insert``) so row-create and mapping-insert commit together.
    """
    now = utc_now_iso()
    if getattr(db, "_engine", "sqlite") == "postgresql":
        db.execute(
            "INSERT INTO sync_server_map (company_id, device_id, entity_type, local_id, server_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (company_id, device_id, entity_type, local_id) DO NOTHING",
            (company_id, device_id, entity_type, local_id, server_id, now),
        )
    else:
        db.execute(
            "INSERT OR IGNORE INTO sync_server_map (company_id, device_id, entity_type, local_id, server_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (company_id, device_id, entity_type, local_id, server_id, now),
        )
    if commit:
        db.commit()


def _remap_mapping(db: DatabaseManager, company_id: int, device_id: str, entity_type: str, local_id: int, server_id: int) -> None:
    """Point an existing (company, device, entity, local_id) mapping at a new server_id.

    Used when the mapped server row was hard-deleted out-of-band and an
    INSERT-retry re-creates it (R6): ``_insert_mapping`` is INSERT OR IGNORE,
    so it cannot move an existing mapping — this UPDATE does.
    """
    db.execute(
        "UPDATE sync_server_map SET server_id = ? "
        "WHERE company_id = ? AND device_id = ? AND entity_type = ? AND local_id = ?",
        (server_id, company_id, device_id, entity_type, local_id),
    )
    db.commit()


# ── Row helpers (repository-backed where the API is dict-based) ──────────

def _get_row(db: DatabaseManager, config: Dict[str, Any], server_id: int, company_id: int) -> Optional[Dict[str, Any]]:
    row = db.execute(
        f"SELECT * FROM {config['table']} WHERE id = ? AND company_id = ?",
        (server_id, company_id),
    ).fetchone()
    return dict(row) if row else None


def _lookup_by_natural_key(db: DatabaseManager, config: Dict[str, Any], company_id: int, value: Any) -> Optional[Dict[str, Any]]:
    """Return the company's row matching the entity's natural key, or None.

    Phase D: route_history uses ``route_fingerprint`` as its natural key —
    the same derived route (same stops/profile/geometry inputs) recomputed on
    another device MUST converge to one server row, not multiply.  NOTE (S2):
    the ``UNIQUE(route_fingerprint)`` constraint is GLOBAL, not per company —
    the lookup is company-scoped, but a cross-company collision can still
    raise IntegrityError on INSERT (handled by the caller).
    """
    if value is None:
        return None
    col = config.get("natural_key")
    if not col:
        return None
    row = db.execute(
        f"SELECT * FROM {config['table']} WHERE {col} = ? AND company_id = ?",
        (value, company_id),
    ).fetchone()
    return dict(row) if row else None


def _create_row(db: DatabaseManager, config: Dict[str, Any], company_id: int, payload: Dict[str, Any]) -> int:
    """Create a server row for the entity.  Returns the new server id.

    Repository-backed entities use the repository on SQLite, where an open
    ``BEGIN IMMEDIATE`` transaction (see ``_begin_transaction``) makes the
    repo's internal commit a no-op so create+mapping stay atomic.  On
    PostgreSQL the repository's ``create()`` commits immediately (the
    ``in_transaction`` detection is SQLite-specific), so the new-row INSERT
    uses the direct-SQL path against the same whitelisted columns — which
    never commits — keeping create+mapping atomic under the caller's
    transaction boundary.
    """
    repo = config.get("repo")
    if repo is not None and getattr(db, "_engine", "sqlite") != "postgresql":
        return _create_row_repo(db, repo, config, company_id, payload)
    return _create_row_sql(
        db, config["table"], config["columns"], company_id, payload,
        unique_lookup=config.get("unique_lookup"),
    )


def _create_row_repo(db: DatabaseManager, repo_cls: Any, config: Dict[str, Any], company_id: int, payload: Dict[str, Any]) -> int:
    repo = repo_cls(db)
    now = utc_now_iso()
    data = dict(payload)
    data.pop("id", None)
    data.pop("deleted_at", None)
    data.pop("company_id", None)  # company_id comes from the JWT, never the payload
    data.setdefault("created_at", now)
    data.setdefault("updated_at", now)
    # Filter to the repository's column whitelist — the desktop payload may
    # carry columns the backend repo does not accept (e.g. updated_at).
    allowed = set(config["columns"])
    data = {k: v for k, v in data.items() if k in allowed}
    if config.get("company_id_param"):
        return repo.create(data, company_id=company_id)
    data["company_id"] = company_id
    return repo.create(data)


def _create_row_sql(
    db: DatabaseManager,
    table: str,
    columns: List[str],
    company_id: int,
    payload: Dict[str, Any],
    unique_lookup: Optional[tuple] = None,
) -> int:
    now = utc_now_iso()
    data = dict(payload)
    data.pop("id", None)
    data.pop("deleted_at", None)
    data.pop("company_id", None)
    data["company_id"] = company_id
    data.setdefault("created_at", now)
    data.setdefault("updated_at", now)
    if table == "documents":
        # R1 (security): file_path is meaningless across machines and
        # attacker-controlled via the sync payload — the binary endpoint
        # owns it.  Never persist a desktop path; use a NOT NULL placeholder.
        data.pop("file_path", None)
        data["file_path"] = ""
    cols = [c for c in data.keys() if c in columns]
    if not cols:
        raise ValueError("no valid columns in payload")
    col_list = ", ".join(cols)
    placeholders = ", ".join("?" for _ in cols)
    query = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    params = tuple(data[c] for c in cols)
    if getattr(db, "_engine", "sqlite") == "postgresql":
        # D1: a unique_lookup makes the INSERT idempotent — an existing row
        # (UNIQUE(document_id, recipient)) is NOT an error; we look it up below.
        suffix = " ON CONFLICT DO NOTHING RETURNING id" if unique_lookup else " RETURNING id"
        cur = db.execute(query + suffix, params)
        row = cur.fetchone()
        server_id = row["id"] if row else 0
    else:
        if unique_lookup:
            query = "INSERT OR IGNORE INTO " + query[len("INSERT INTO "):]
        cur = db.execute(query, params)
        server_id = cur.lastrowid
    if unique_lookup and (not server_id):
        # The row already exists (same unique key) → return its id so the
        # mapping is recorded against the existing row.
        (col_a, col_b) = unique_lookup
        existing = db.execute(
            f"SELECT id FROM {table} WHERE {col_a} = ? AND {col_b} = ?",
            (data.get(col_a), data.get(col_b)),
        ).fetchone()
        if existing is not None:
            server_id = existing["id"]
    # NOTE: no commit here — the caller (_process_insert) commits once after
    # the mapping insert so row-create + mapping-insert land in ONE
    # transaction (Phase 3b R4 transaction seam).
    return server_id


def _update_row(db: DatabaseManager, config: Dict[str, Any], server_id: int, company_id: int, payload: Dict[str, Any]) -> None:
    """Apply an UPDATE to the mapped server row (company-scoped)."""
    repo = config.get("repo")
    if repo is not None:
        _update_row_repo(db, repo, config, server_id, company_id, payload)
    else:
        _update_row_sql(db, config["table"], config["columns"], server_id, company_id, payload)


def _update_row_repo(db: DatabaseManager, repo_cls: Any, config: Dict[str, Any], server_id: int, company_id: int, payload: Dict[str, Any]) -> None:
    repo = repo_cls(db)
    now = utc_now_iso()
    data = dict(payload)
    data.pop("id", None)
    # deleted_at is handled by op=DELETE (Phase 4 lane converts
    # UPDATE-with-deleted_at → DELETE); never applied via UPDATE.
    data.pop("deleted_at", None)
    data.pop("company_id", None)
    data.pop("created_at", None)  # created_at is immutable after insert
    data["updated_at"] = now
    # Filter to the repository's column whitelist (see _create_row_repo).
    allowed = set(config["columns"])
    data = {k: v for k, v in data.items() if k in allowed}
    if config.get("company_id_param"):
        repo.update(server_id, data, company_id=company_id)
    else:
        repo.update(server_id, data)


def _update_row_sql(db: DatabaseManager, table: str, columns: List[str], server_id: int, company_id: int, payload: Dict[str, Any]) -> None:
    now = utc_now_iso()
    data = dict(payload)
    data.pop("id", None)
    # deleted_at is handled by op=DELETE (Phase 4 lane converts
    # UPDATE-with-deleted_at → DELETE); never applied via UPDATE.
    data.pop("deleted_at", None)
    data.pop("company_id", None)
    data.pop("created_at", None)
    data["updated_at"] = now
    if table == "documents":
        # R1 (security): never overwrite the server's stored file_path with a
        # desktop path from the sync payload — the binary endpoint owns it.
        data.pop("file_path", None)
    cols = [c for c in data.keys() if c in columns]
    if not cols:
        raise ValueError("no valid columns in payload")
    sets = ", ".join(f"{c} = ?" for c in cols)
    db.execute(
        f"UPDATE {table} SET {sets} WHERE id = ? AND company_id = ?",
        tuple(data[c] for c in cols) + (server_id, company_id),
    )
    db.commit()


def _soft_delete_row(db: DatabaseManager, config: Dict[str, Any], server_id: int, company_id: int) -> None:
    """Soft-delete the mapped server row (hard delete when no deleted_at).

    ``updated_at`` is stamped alongside ``deleted_at`` so a second device's
    UPDATE with a pre-delete ``base_updated_at`` fails the conflict check
    instead of silently writing into a deleted row (R7).
    """
    table = config["table"]
    if table not in _SOFT_DELETE_TABLES:
        db.execute(
            f"DELETE FROM {table} WHERE id = ? AND company_id = ?",
            (server_id, company_id),
        )
    else:
        now = utc_now_iso()
        db.execute(
            f"UPDATE {table} SET deleted_at = ?, updated_at = ? WHERE id = ? AND company_id = ?",
            (now, now, server_id, company_id),
        )
    db.commit()


# ── Per-item processing ──────────────────────────────────────────────────

def _begin_transaction(db: DatabaseManager) -> None:
    """Open an explicit transaction boundary for an atomic create+mapping.

    SQLite: ``BEGIN IMMEDIATE`` takes the write lock up front and makes
    ``db.conn.in_transaction`` True, so a repository ``create()`` (which
    auto-commits unless already in a transaction) defers its commit to the
    caller.  PostgreSQL: psycopg2 (``autocommit=False``) opens transactions
    implicitly — no explicit BEGIN (SQLite-only syntax would raise).
    """
    if getattr(db, "_engine", "sqlite") == "postgresql":
        return
    db.execute("BEGIN IMMEDIATE")


def _process_insert(db: DatabaseManager, company_id: int, device_id: str, item: SyncPushItem, config: Dict[str, Any]) -> SyncPushResult:
    mapping = _resolve_mapping(db, company_id, device_id, item.entity_type, item.local_id)
    if mapping is not None:
        # Retry after a network drop — the row already exists server-side.
        # Treat the INSERT as an UPDATE of the mapped row (exactly-once).
        # The conflict check is SKIPPED on this retry path: the desktop clock
        # may be stale vs the server clock, and this is the same logical op
        # (the row was created by this desktop), so a "stale base" conflict
        # would wedge the outbox forever.
        server_row = _get_row(db, config, mapping, company_id)
        if server_row is None:
            # The mapped server row was hard-deleted out-of-band (e.g. an
            # admin purge, or a non-soft-delete table like expenses).  Re-create
            # the row from the payload and re-map so the local row is NOT lost
            # (returning "gone" here would make the desktop lane DROP the
            # outbox row → permanent data loss for that local row).
            server_id = _create_row(db, config, company_id, item.payload)
            _remap_mapping(db, company_id, device_id, item.entity_type, item.local_id, server_id)
            return SyncPushResult(local_id=item.local_id, server_id=server_id, status="ok")
        return _process_update(
            db, company_id, device_id, item, config, server_id=mapping, check_conflict=False,
        )
    # Phase D: natural-key dedup — a push INSERT whose natural key already
    # exists on the server (e.g. the same route fingerprint synced by another
    # device) updates that row instead of creating a duplicate.  Applies the
    # payload as an UPDATE (conflict check skipped — same logical derived row)
    # and maps this desktop's local_id to the existing server row.
    natural_key_col = config.get("natural_key")
    if natural_key_col:
        existing = _lookup_by_natural_key(
            db, config, company_id, item.payload.get(natural_key_col),
        )
        if existing is not None:
            _update_row(db, config, existing["id"], company_id, item.payload)
            # A re-calculated route "revives" a previously soft-deleted row.
            if existing.get("deleted_at") and not item.payload.get("deleted_at"):
                db.execute(
                    f"UPDATE {config['table']} SET deleted_at = NULL WHERE id = ?",
                    (existing["id"],),
                )
                db.commit()
            _insert_mapping(db, company_id, device_id, item.entity_type, item.local_id, existing["id"])
            return SyncPushResult(local_id=item.local_id, server_id=existing["id"], status="ok")

        try:
            server_id = _create_row(db, config, company_id, item.payload)
        except Exception:
            # S2: the UNIQUE(route_fingerprint) constraint is GLOBAL, so an
            # INSERT can collide with ANOTHER company's identical (truck-less)
            # route.  Re-lookup within THIS company — if the row appeared
            # concurrently (another device), converge to it; otherwise the
            # collision belongs to another tenant and retrying forever is
            # pointless → return a terminal error so the lane drops the item.
            existing2 = _lookup_by_natural_key(
                db, config, company_id, item.payload.get(natural_key_col),
            )
            if existing2 is not None:
                _update_row(db, config, existing2["id"], company_id, item.payload)
                if existing2.get("deleted_at") and not item.payload.get("deleted_at"):
                    db.execute(
                        f"UPDATE {config['table']} SET deleted_at = NULL WHERE id = ?",
                        (existing2["id"],),
                    )
                    db.commit()
                _insert_mapping(db, company_id, device_id, item.entity_type, item.local_id, existing2["id"])
                return SyncPushResult(local_id=item.local_id, server_id=existing2["id"], status="ok")
            return SyncPushResult(
                local_id=item.local_id,
                status="error",
                error="natural key collision belongs to another company",
            )
        _insert_mapping(db, company_id, device_id, item.entity_type, item.local_id, server_id)
        return SyncPushResult(local_id=item.local_id, server_id=server_id, status="ok")

    # Transaction seam (Phase 3b R4): row-create + mapping-insert must land in
    # ONE transaction so a crash/failure between them cannot leave an orphan
    # server row (which the next INSERT-retry would duplicate).  BEGIN IMMEDIATE
    # (SQLite) makes the repository's internal commit a no-op (it defers to the
    # open transaction); PostgreSQL opens its transaction implicitly (no-op) and
    # the new-row INSERT uses the direct-SQL path (which never commits).  The
    # mapping insert is deferred (commit=False) and everything commits once.
    _begin_transaction(db)
    try:
        server_id = _create_row(db, config, company_id, item.payload)
        _insert_mapping(db, company_id, device_id, item.entity_type, item.local_id, server_id, commit=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return SyncPushResult(local_id=item.local_id, server_id=server_id, status="ok")

def _process_update(
    db: DatabaseManager,
    company_id: int,
    device_id: str,
    item: SyncPushItem,
    config: Dict[str, Any],
    server_id: Optional[int] = None,
    check_conflict: bool = True,
) -> SyncPushResult:
    if server_id is None:
        server_id = _resolve_mapping(db, company_id, device_id, item.entity_type, item.local_id)
        if server_id is None:
            return SyncPushResult(local_id=item.local_id, status="error", error="no mapping")
    server_row = _get_row(db, config, server_id, company_id)
    if server_row is None:
        # Mapped local_id whose server row is gone (e.g. expenses hard-deleted
        # by an earlier DELETE).  Status "gone" lets the desktop lane DROP the
        # outbox row instead of retrying forever.
        return SyncPushResult(
            local_id=item.local_id, server_id=server_id, status="gone",
            error="server row not found",
        )
    # Conflict detection: if the client's base_updated_at is provided and the
    # server row was modified AFTER it, the client is stale → conflict, do NOT
    # apply.  The current server row is returned so the client can rebase.
    # Skipped on the INSERT-retry path (check_conflict=False) — see
    # _process_insert.
    if check_conflict and item.base_updated_at is not None:
        server_updated = _ts_to_compare(server_row.get("updated_at"))
        if server_updated and server_updated > item.base_updated_at:
            return SyncPushResult(
                local_id=item.local_id,
                server_id=server_id,
                status="conflict",
                # B1: never serialize non-JSON columns (e.g. the route_history
                # geometry BLOB) into the conflict server_row — a UnicodeDecodeError
                # would 500 the whole push batch → permanent retry wedge.
                server_row=_normalize_row(
                    server_row, exclude=config.get("exclude_columns"),
                ),
            )
    _update_row(db, config, server_id, company_id, item.payload)
    return SyncPushResult(local_id=item.local_id, server_id=server_id, status="ok")


def _record_tombstone(db: DatabaseManager, company_id: int, entity_type: str, server_id: int) -> None:
    """Record a hard-delete tombstone (Phase D).

    Other devices that never pulled the row (no sync_id_map entry) cannot
    learn about the deletion via the entity pull — the row is gone or
    soft-deleted server-side and they have no mapping to update.  The
    desktop's ``entity=tombstone`` pull applies the tombstone (hard-delete
    local row + clear map).  The unique (company, entity, server_id) key
    makes a re-record idempotent; B3: tombstones are retained until a
    30-day janitor purges them (never consumed by a single pull).
    """
    if getattr(db, "_engine", "sqlite") == "postgresql":
        db.execute(
            "INSERT INTO sync_tombstones (company_id, entity_type, server_id, purged_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT (company_id, entity_type, server_id) "
            "DO UPDATE SET purged_at = EXCLUDED.purged_at",
            (company_id, entity_type, server_id, utc_now_iso()),
        )
    else:
        db.execute(
            "INSERT OR REPLACE INTO sync_tombstones "
            "(company_id, entity_type, server_id, purged_at) VALUES (?, ?, ?, ?)",
            (company_id, entity_type, server_id, utc_now_iso()),
        )
    db.commit()


def _process_delete(db: DatabaseManager, company_id: int, device_id: str, item: SyncPushItem, config: Dict[str, Any]) -> SyncPushResult:
    server_id = _resolve_mapping(db, company_id, device_id, item.entity_type, item.local_id)
    if server_id is None:
        # Nothing mapped → nothing to delete (idempotent).
        return SyncPushResult(local_id=item.local_id, status="ok")
    server_row = _get_row(db, config, server_id, company_id)
    if server_row is None:
        # Already gone (e.g. expenses hard-deleted earlier) → drop the outbox
        # row.  Re-record the tombstone for any device that missed it.
        _record_tombstone(db, company_id, item.entity_type, server_id)
        return SyncPushResult(local_id=item.local_id, server_id=server_id, status="gone")
    # Conflict detection: if the client's base_updated_at is provided and the
    # server row was modified AFTER it, the client is stale → conflict, do NOT
    # delete.  The current server row is returned so the client can rebase.
    if item.base_updated_at is not None:
        server_updated = _ts_to_compare(server_row.get("updated_at"))
        if server_updated and server_updated > item.base_updated_at:
            return SyncPushResult(
                local_id=item.local_id,
                server_id=server_id,
                status="conflict",
                # B1: exclude non-JSON columns from the conflict server_row
                # (see _process_update).
                server_row=_normalize_row(
                    server_row, exclude=config.get("exclude_columns"),
                ),
            )
    _soft_delete_row(db, config, server_id, company_id)
    # Phase D: after the delete lands (soft or hard), record the tombstone so
    # devices that never pulled the row still learn to drop their local copy.
    _record_tombstone(db, company_id, item.entity_type, server_id)
    return SyncPushResult(local_id=item.local_id, server_id=server_id, status="ok")


def _process_item(db: DatabaseManager, company_id: int, device_id: str, item: SyncPushItem) -> SyncPushResult:
    config = _ENTITY_CONFIG.get(item.entity_type)
    if config is None:
        return SyncPushResult(
            local_id=item.local_id, status="error", error="unsupported entity type",
        )
    try:
        if item.op == "INSERT":
            return _process_insert(db, company_id, device_id, item, config)
        if item.op == "UPDATE":
            return _process_update(db, company_id, device_id, item, config)
        if item.op == "DELETE":
            return _process_delete(db, company_id, device_id, item, config)
        return SyncPushResult(
            local_id=item.local_id, status="error", error=f"unsupported op: {item.op}",
        )
    except Exception as exc:  # one item's failure must not abort the batch
        return SyncPushResult(local_id=item.local_id, status="error", error=str(exc))


# ── Endpoints ────────────────────────────────────────────────────────────

@router.post("/push", response_model=SyncPushResponse)
def push(
    data: SyncPushRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> SyncPushResponse:
    """Apply a batch of outbox items exactly-once (company + device scoped).

    ``device_id`` comes from the request body (a user may have multiple
    devices), never from the JWT.
    """
    company_id = current_user.get("company_id", 0)
    device_id = data.device_id
    results = [_process_item(db, company_id, device_id, item) for item in data.items]
    return SyncPushResponse(results=results)


@router.get("/pull")
def pull(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
    entity: str = Query(..., description="Entity type to pull"),
    device_id: str = Query(..., description="Per-install device id"),
    after_id: int = Query(0, ge=0, description="Return rows with id > after_id"),
    limit: int = Query(500, ge=1, le=1000, description="Maximum rows to return"),
    since: Optional[str] = Query(
        None,
        description="Phase E delta watermark (canonical YYYY-MM-DDTHH:MM:SSZ). "
        "When provided, only rows with updated_at > since (or NULL updated_at — "
        "legacy rows that have not been stamped yet) are returned.  Omit for a "
        "full keyset refresh (backward compatible).",
    ),
    since_id: int = Query(
        0,
        ge=0,
        description="Phase E/R1 id tiebreak for the cursor second: rows with "
        "updated_at == since AND id > since_id are also included (a row stamped "
        "at EXACTLY the cursor second would otherwise be permanently missed by "
        "a strict > comparison).  Only meaningful when ``since`` is provided.",
    ),
) -> Dict[str, Any]:
    """Company-scoped rows for an entity.

    Returns rows with ``id > after_id`` ordered by id, limited, including
    soft-deleted rows (``deleted_at`` set — the soft-delete paths stamp
    ``updated_at`` alongside ``deleted_at``, so ``updated_at > since`` covers
    them).  The full soft-delete sweep is Phase 3's job; here deleted rows are
    simply included in the output.

    ``since`` (Phase E): delta pull.  Rows with ``updated_at > since`` are
    returned (canonical timestamps compare lexicographically).  NULL
    ``updated_at`` rows (written by pre-Phase-0 code, never touched since) are
    ALWAYS included so they are not silently dropped — they get stamped on the
    next write and self-heal.  ``cursor`` in the response = the max
    ``updated_at`` seen (the desktop stores it per-user as its delta cursor).

    ``device_id`` identifies the requesting device for id-map bookkeeping;
    the response is company-scoped (unchanged) — device_id does not filter
    server rows.

    Phase D: ``entity=tombstone`` returns the company's hard-delete
    tombstones.  Tombstones are NOT consumed on pull (B3, multi-device): the
    desktop apply is idempotent (missing local row = no-op, mapping cleared),
    so re-delivery is free — the deleting device must not eat its own
    tombstone before the other devices sync.  A 30-day retention janitor
    purges stale entries.  Tombstones are NEVER since-filtered — a device's
    delta cursor must not suppress hard-delete propagation.
    """
    company_id = current_user.get("company_id", 0)

    if entity == "tombstone":
        # B3: retention janitor — purge tombstones older than 30 days BEFORE
        # the read so a stale row is never returned again (re-delivery is
        # idempotent, so a device that syncs less often than the retention
        # window simply misses the tombstone — the next hard-delete op
        # re-records it).
        if getattr(db, "_engine", "sqlite") == "postgresql":
            db.execute(
                "DELETE FROM sync_tombstones WHERE purged_at::date < (now() - interval '30 days')::date",
            )
        else:
            db.execute(
                "DELETE FROM sync_tombstones WHERE date(purged_at) < date('now', '-30 days')",
            )
        db.commit()
        rows = db.execute(
            "SELECT entity_type, server_id FROM sync_tombstones "
            "WHERE company_id = ?",
            (company_id,),
        ).fetchall()
        records = [dict(r) for r in rows]
        return {"records": records, "next_after_id": 0, "has_more": False, "cursor": ""}

    config = _ENTITY_CONFIG.get(entity)
    if config is None:
        return {"records": [], "next_after_id": after_id, "has_more": False, "cursor": ""}
    use_since = bool(since)
    if use_since:
        # Phase E / R1: delta — rows newer than the watermark, PLUS the id
        # tiebreak for the cursor second.  Timestamps are seconds-precision,
        # so a strict ``updated_at > since`` permanently excludes a row stamped
        # at EXACTLY the cursor second; ``updated_at = since AND id > since_id``
        # re-fetches the not-yet-seen rows of that second.  Apply is
        # idempotent, so overlap with the previous page is harmless.  NULL
        # updated_at rows are always returned (self-healing).
        rows = db.execute(
            f"SELECT * FROM {config['table']} "
            f"WHERE company_id = ? AND id > ? "
            f"AND (updated_at IS NULL "
            f"    OR updated_at > ? "
            f"    OR (updated_at = ? AND id > ?)) "
            f"ORDER BY id ASC LIMIT ?",
            (company_id, after_id, since, since, since_id, limit),
        ).fetchall()
    else:
        rows = db.execute(
            f"SELECT * FROM {config['table']} WHERE company_id = ? AND id > ? ORDER BY id ASC LIMIT ?",
            (company_id, after_id, limit),
        ).fetchall()
    records = [_normalize_row(dict(r)) for r in rows]
    # Phase D: drop non-JSON-serializable columns from the payload (e.g. the
    # route_history_v2 geometry BLOB) so the response stays JSON-safe.
    exclude = config.get("exclude_columns")
    if exclude:
        records = [
            {k: v for k, v in rec.items() if k not in exclude}
            for rec in records
        ]
    next_after_id = max((r["id"] for r in records), default=after_id)
    has_more = len(records) >= limit
    # Phase E: delta watermark — max updated_at seen (or the incoming since
    # when nothing newer exists, so the client's cursor never goes backwards).
    cursor = since or ""
    for rec in records:
        ts = rec.get("updated_at")
        if ts and str(ts) > cursor:
            cursor = str(ts)
    return {
        "records": records,
        "next_after_id": next_after_id,
        "has_more": has_more,
        "cursor": cursor,
    }


# ── Phase D: sequence reconciliation ──────────────────────────────────────

class SequenceUpdateRequest(BaseModel):
    entity: Literal["invoice", "cmr"]
    year: int
    value: int


@router.post("/sequences")
def reconcile_sequences(
    data: SequenceUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Bump a company's document sequence counter to ``max(existing, value)``.

    Idempotent reconciliation: a LOWER value is a no-op (a stale desktop must
    never decrease the shared counter — that would risk duplicate document
    numbers).  ``company_id`` comes from the JWT.  The underlying counter
    tables are not company-keyed (legacy model — one counter per deployment);
    the max-merge makes cross-company interference safe (numbers only ever
    grow, so collisions are impossible).

    B5: the response ``value`` is the POST-MERGE counter (``max(existing,
    value)``) — the desktop applies it back so its LOCAL counter converges to
    the server max BEFORE the next allocation (otherwise a second device
    allocates numbers already handed out → UNIQUE invoice-number conflict).

    ``entity="invoice"`` bumps the DEFAULT invoice series
    (``inv_year_seq`` — the format used by both desktop and server by
    default); ``entity="cmr"`` bumps ``cmr_counter`` for the year.
    """
    company_id = current_user.get("company_id", 0)
    year = data.year
    value = int(data.value)
    is_pg = getattr(db, "_engine", "sqlite") == "postgresql"
    if data.entity == "invoice":
        # invoice_number_sequences is keyed (series, year) with no
        # company_id — use the DEFAULT invoice series (inv_year_seq).
        if is_pg:
            db.execute(
                "INSERT INTO invoice_number_sequences (series, year, last_number) "
                "VALUES ('inv_year_seq', ?, 0) "
                "ON CONFLICT (series, year) DO NOTHING",
                (year,),
            )
            db.execute(
                "UPDATE invoice_number_sequences SET last_number = "
                "GREATEST(last_number, ?) "
                "WHERE series = 'inv_year_seq' AND year = ?",
                (value, year),
            )
        else:
            db.execute(
                "INSERT OR IGNORE INTO invoice_number_sequences "
                "(series, year, last_number) VALUES ('inv_year_seq', ?, 0)",
                (year,),
            )
            db.execute(
                "UPDATE invoice_number_sequences SET last_number = MAX(last_number, ?) "
                "WHERE series = 'inv_year_seq' AND year = ?",
                (value, year),
            )
        row = db.execute(
            "SELECT last_number FROM invoice_number_sequences "
            "WHERE series = 'inv_year_seq' AND year = ?",
            (year,),
        ).fetchone()
        merged = int(row["last_number"]) if row else value
    else:
        if is_pg:
            db.execute(
                "INSERT INTO cmr_counter (year, sequence_number) VALUES (?, 0) "
                "ON CONFLICT (year) DO NOTHING",
                (year,),
            )
            db.execute(
                "UPDATE cmr_counter SET sequence_number = GREATEST(sequence_number, ?) "
                "WHERE year = ?",
                (value, year),
            )
        else:
            db.execute(
                "INSERT OR IGNORE INTO cmr_counter (year, sequence_number) VALUES (?, 0)",
                (year,),
            )
            db.execute(
                "UPDATE cmr_counter SET sequence_number = MAX(sequence_number, ?) WHERE year = ?",
                (value, year),
            )
        row = db.execute(
            "SELECT sequence_number FROM cmr_counter WHERE year = ?", (year,)
        ).fetchone()
        merged = int(row["sequence_number"]) if row else value
    db.commit()
    return {"status": "ok", "entity": data.entity, "year": year, "value": merged}