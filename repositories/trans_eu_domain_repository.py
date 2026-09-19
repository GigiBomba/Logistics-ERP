"""Trans.eu domain repositories — orders, negotiation, dock scheduler, providers.

Raw-SQL repository layer for the 9 Trans.eu domain tables
(TransEU_Architecture.md §5.1/§9.13; TransEU_KnowledgeBase.md §6.8/§6.9/
§7.2-§7.7).  Same house pattern as ``repositories/trans_eu_repository.py``:
no ORM, ``TABLE`` / ``COLUMNS`` constants, ``?`` placeholders (``_adapt_query``
maps them to ``%s`` on PostgreSQL).

Multi-tenant filtering is applied manually via ``company_id = ?`` in every
query.  JSON columns are stored as TEXT on SQLite / JSONB on PostgreSQL;
repositories pass the already-serialized JSON text (both engines accept a
valid JSON string for the column).

The ``_upsert`` helper is an explicit ``ON CONFLICT (company_id, <key>) DO
UPDATE`` so a re-run REPLACES the row instead of appending a duplicate.  On
SQLite this requires the unique index the schema.py ``UNIQUE (...)`` inline
constraints create; on PostgreSQL the matching constraints come from the
Alembic migration / schema_pg.sql.
# read-only
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


def _upsert(
    repo: BaseRepository,
    company_id: int,
    data: Dict[str, Any],
    key_col: str,
) -> None:
    """Insert-or-update a row keyed on ``(company_id, key_col)``.

    ``data`` holds the business columns (``company_id`` is supplied
    separately); ``id`` is generated in Python so the statement works on both
    SQLite (TEXT PRIMARY KEY, no server default) and PostgreSQL
    (``gen_random_uuid()``).  ``created_at`` is preserved on update;
    ``updated_at`` and every business column are overwritten with the
    ``excluded.*`` values.
    """
    repo._validate_columns(data, extra_allowed={"company_id"})
    data = dict(data)
    business_cols = [k for k in data if k != "company_id"]
    now = datetime.utcnow().isoformat()
    new_id = str(uuid.uuid4())
    cols = ", ".join(["id", "company_id"] + business_cols + ["created_at", "updated_at"])
    vals = ", ".join(["?"] * (2 + len(business_cols) + 2))
    set_cols = business_cols + ["updated_at"]
    sets = ", ".join(f"{c} = excluded.{c}" for c in set_cols)
    conflict = f"company_id, {key_col}"
    repo._execute(
        f"INSERT INTO {repo.TABLE} ({cols}) VALUES ({vals}) "
        f"ON CONFLICT ({conflict}) DO UPDATE SET {sets}",
        (new_id, company_id) + tuple(data[k] for k in business_cols) + (now, now),
        commit=True,
    )


class _DomainBase(BaseRepository):
    """Shared upsert helper for Trans.eu domain tables (UUID PK both engines)."""

    # Subclasses define KEY_COL: the natural Trans.eu id scoping the upsert.
    KEY_COL: str = ""

    def upsert_by_trans_eu_id(self, company_id: int, data: Dict[str, Any]) -> None:
        _upsert(self, company_id, data, self.KEY_COL)


# ═══════════════════════════════════════════════════════════════════════════
# Freight Orders
# ═══════════════════════════════════════════════════════════════════════════


class FreightOrderRepository(BaseRepository):
    TABLE = "freight_orders"
    COLUMNS = [
        "id", "company_id", "trans_eu_order_id", "trans_eu_freight_id",
        "order_number", "status", "price_amount", "price_currency",
        "payment_type", "execution_data", "linked_trip_id",
        "created_at", "updated_at",
    ]

    def get_by_company(self, company_id: int, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (company_id, limit, offset),
        )

    def get_by_trans_eu_order_id(self, company_id: int, trans_eu_order_id: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? AND trans_eu_order_id = ? LIMIT 1",
            (company_id, trans_eu_order_id),
        )

    def get_by_freight_id(self, company_id: int, trans_eu_freight_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? AND trans_eu_freight_id = ? "
            f"ORDER BY created_at DESC",
            (company_id, trans_eu_freight_id),
        )

    def create(self, data: Dict[str, Any]) -> int:
        """Insert an order row and return its row id.

        ``company_id`` must be supplied by the caller (the API resolves it
        from the JWT); the HTTP path does not populate the tenant contextvars.
        """
        self._validate_columns(data, extra_allowed={"company_id"})
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
        )

    def update_status(self, company_id: int, trans_eu_order_id: str, status: str) -> int:
        now = datetime.utcnow().isoformat()
        return self._execute_with_count(
            f"UPDATE {self.TABLE} SET status = ?, updated_at = ? "
            f"WHERE company_id = ? AND trans_eu_order_id = ?",
            (status, now, company_id, trans_eu_order_id), commit=True,
        )

    def link_trip(self, company_id: int, trans_eu_order_id: str, trip_id: int) -> int:
        now = datetime.utcnow().isoformat()
        return self._execute_with_count(
            f"UPDATE {self.TABLE} SET linked_trip_id = ?, updated_at = ? "
            f"WHERE company_id = ? AND trans_eu_order_id = ?",
            (trip_id, now, company_id, trans_eu_order_id), commit=True,
        )

    def get_unlinked_by_company(self, company_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? AND linked_trip_id IS NULL "
            f"ORDER BY created_at DESC",
            (company_id,),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Negotiation Offers
# ═══════════════════════════════════════════════════════════════════════════


class NegotiationOfferRepository(BaseRepository):
    TABLE = "negotiation_offers"
    COLUMNS = [
        "id", "company_id", "trans_eu_freight_id", "offer_id", "direction",
        "status", "price", "currency", "counterparty_name", "counterparty_id",
        "author", "parent_offer_id", "created_at", "updated_at",
    ]

    def get_thread_by_freight(self, company_id: int, trans_eu_freight_id: int) -> List[Dict[str, Any]]:
        """Return the full negotiation thread (oldest → newest)."""
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            f"WHERE company_id = ? AND trans_eu_freight_id = ? "
            f"ORDER BY created_at, id",
            (company_id, trans_eu_freight_id),
        )

    def create(self, data: Dict[str, Any]) -> int:
        """Insert a negotiation offer row and return its row id."""
        self._validate_columns(data, extra_allowed={"company_id"})
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
        )

    def get_latest_by_freight(self, company_id: int, trans_eu_freight_id: int) -> Optional[Dict[str, Any]]:
        """Return the most recent offer of a thread (None when empty)."""
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} "
            f"WHERE company_id = ? AND trans_eu_freight_id = ? "
            f"ORDER BY created_at DESC, id DESC LIMIT 1",
            (company_id, trans_eu_freight_id),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Dock Scheduler
# ═══════════════════════════════════════════════════════════════════════════


class DockWarehouseRepository(_DomainBase):
    TABLE = "dock_warehouses"
    KEY_COL = "trans_eu_warehouse_id"
    COLUMNS = [
        "id", "company_id", "trans_eu_warehouse_id", "name", "address",
        "ramps", "created_at", "updated_at",
    ]

    def get_by_company(self, company_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? ORDER BY name, id",
            (company_id,),
        )


class DockTimeWindowRepository(_DomainBase):
    TABLE = "dock_time_windows"
    KEY_COL = "trans_eu_window_id"
    COLUMNS = [
        "id", "company_id", "trans_eu_window_id", "warehouse_id",
        "valid_from", "valid_to", "start_time", "end_time", "range_type",
        "external_number", "carrier_id", "purchase_order", "route",
        "created_at", "updated_at",
    ]

    def get_by_warehouse(self, company_id: int, warehouse_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? AND warehouse_id = ? "
            f"ORDER BY valid_from, id",
            (company_id, warehouse_id),
        )

    def upsert(self, company_id: int, data: Dict[str, Any]) -> None:
        _upsert(self, company_id, data, self.KEY_COL)


class DockAnnouncementRepository(_DomainBase):
    TABLE = "dock_announcements"
    KEY_COL = "trans_eu_announcement_id"
    COLUMNS = [
        "id", "company_id", "trans_eu_announcement_id", "reference_number",
        "status", "stage", "date_from", "date_to", "operation_type",
        "operation_time", "carrier_id", "carrier_name", "shipper_id",
        "driver", "vehicle", "ramp_id", "warehouse_id", "route", "notes",
        "external_reference_number", "created_at", "updated_at",
    ]

    def get_by_company(self, company_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? ORDER BY created_at DESC",
            (company_id,),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Providers: contracts / partners / vehicles
# ═══════════════════════════════════════════════════════════════════════════


class ProviderContractRepository(_DomainBase):
    TABLE = "provider_contracts"
    KEY_COL = "trans_eu_contract_id"
    COLUMNS = [
        "id", "company_id", "trans_eu_contract_id", "contract_type",
        "carrier_id", "carrier_name", "order_terms", "status",
        "created_at", "updated_at",
    ]

    def get_by_company(self, company_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? ORDER BY created_at DESC",
            (company_id,),
        )


class ProviderPartnerRepository(_DomainBase):
    TABLE = "provider_partners"
    KEY_COL = "trans_eu_partner_id"
    COLUMNS = [
        "id", "company_id", "trans_eu_partner_id", "legal_name", "vat_id",
        "cooperation_status", "groups", "trans_eu_employee_ids",
        "created_at", "updated_at",
    ]

    def get_partner_for_company(self, company_id: int, trans_eu_partner_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? AND trans_eu_partner_id = ? LIMIT 1",
            (company_id, trans_eu_partner_id),
        )


class ProviderVehicleRepository(_DomainBase):
    TABLE = "provider_vehicles"
    KEY_COL = "trans_eu_vehicle_id"
    COLUMNS = [
        "id", "company_id", "trans_eu_vehicle_id", "plate_number",
        "vehicle_manufacturer", "chassis_number", "registration_country",
        "vin", "truck_trailer_plates", "created_at", "updated_at",
    ]

    def get_by_company(self, company_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? ORDER BY plate_number, id",
            (company_id,),
        )


class TransEuVehicleOfferRepository(_DomainBase):
    TABLE = "trans_eu_vehicle_offers"
    KEY_COL = "trans_eu_offer_id"
    COLUMNS = [
        "id", "company_id", "trans_eu_offer_id", "vehicle_id", "offer_type",
        "available_from", "available_to", "origin", "destination", "price",
        "currency", "loading_country", "unloading_country", "status",
        "created_at", "updated_at",
    ]

    def get_by_company(self, company_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? ORDER BY created_at DESC",
            (company_id,),
        )

    def upsert(self, company_id: int, data: Dict[str, Any]) -> None:
        _upsert(self, company_id, data, self.KEY_COL)