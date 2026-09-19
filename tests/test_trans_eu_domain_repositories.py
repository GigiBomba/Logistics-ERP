"""Tests for repositories.trans_eu_domain_repository — Trans.eu domain CRUD/upsert.

The 9 Trans.eu domain tables are created from the ``database/schema.py`` DDL
constants (the "schema-created tables" path — the same DDL mirrored in
database/schema_pg.sql and the Alembic migration p1q2r3s4t5u7).  Each test
exercises a per-repo round-trip against ``InMemoryDB`` (full application
schema, companies 0-100 seeded, FK enforcement ON).
"""

from __future__ import annotations

import json
import uuid

import pytest

from database import schema as S
from repositories.trans_eu_domain_repository import (
    DockAnnouncementRepository,
    DockTimeWindowRepository,
    DockWarehouseRepository,
    FreightOrderRepository,
    NegotiationOfferRepository,
    ProviderContractRepository,
    ProviderPartnerRepository,
    ProviderVehicleRepository,
    TransEuVehicleOfferRepository,
)
from tests.test_helpers import InMemoryDB

# ── Schema-created Trans.eu domain tables (SQLite DDL) ───────────────────

_TRANS_EU_DOMAIN_DDL = [
    S.TABLE_FREIGHT_ORDERS,
    S.INDEX_FREIGHT_ORDERS_COMPANY,
    S.INDEX_FREIGHT_ORDERS_FREIGHT_ID,
    S.INDEX_FREIGHT_ORDERS_TRIP,
    S.TABLE_NEGOTIATION_OFFERS,
    S.INDEX_NEGOTIATION_OFFERS_FREIGHT,
    S.TABLE_DOCK_WAREHOUSES,
    S.INDEX_DOCK_WAREHOUSES_COMPANY,
    S.TABLE_DOCK_TIME_WINDOWS,
    S.INDEX_DOCK_TIME_WINDOWS_WAREHOUSE,
    S.TABLE_DOCK_ANNOUNCEMENTS,
    S.INDEX_DOCK_ANNOUNCEMENTS_COMPANY,
    S.INDEX_DOCK_ANNOUNCEMENTS_STATUS,
    S.TABLE_PROVIDER_CONTRACTS,
    S.INDEX_PROVIDER_CONTRACTS_COMPANY,
    S.TABLE_PROVIDER_PARTNERS,
    S.INDEX_PROVIDER_PARTNERS_COMPANY,
    S.TABLE_PROVIDER_VEHICLES,
    S.INDEX_PROVIDER_VEHICLES_COMPANY,
    S.TABLE_TRANS_EU_VEHICLE_OFFERS,
    S.INDEX_TRANS_EU_VEHICLE_OFFERS_COMPANY,
]


@pytest.fixture
def db():
    d = InMemoryDB()
    for ddl in _TRANS_EU_DOMAIN_DDL:
        d.conn.execute(ddl)
    d.conn.commit()
    yield d
    d.close()


def _oid() -> str:
    """Fresh UUID string for a SQLite TEXT PRIMARY KEY."""
    return str(uuid.uuid4())


def _seed_trip(db, trip_id: int = 1) -> None:
    db.conn.execute(
        "INSERT INTO trips (id, status) VALUES (?, 'draft')",
        (trip_id,),
    )
    db.conn.commit()


# ═══════════════════════════════════════════════════════════════════════════
# FreightOrderRepository
# ═══════════════════════════════════════════════════════════════════════════


class TestFreightOrderRepository:
    def _create(self, db, repo, order_id: str, freight_id: int = 100, status: str = "created") -> None:
        repo.create({
            "id": _oid(),
            "company_id": 1,
            "trans_eu_order_id": order_id,
            "trans_eu_freight_id": freight_id,
            "order_number": f"ORD-{order_id}",
            "status": status,
            "price_amount": 1200.0,
            "price_currency": "EUR",
            "payment_type": "deferred",
            "execution_data": json.dumps({"loading": {"place": "Wroclaw"}, "unloading": {"place": "Berlin"}}),
        })

    def test_create_and_get_by_company(self, db):
        repo = FreightOrderRepository(db)
        self._create(db, repo, "ord-001")
        rows = repo.get_by_company(1)
        assert len(rows) == 1
        assert rows[0]["trans_eu_order_id"] == "ord-001"
        assert rows[0]["price_currency"] == "EUR"
        assert json.loads(rows[0]["execution_data"])["loading"]["place"] == "Wroclaw"

    def test_get_by_company_is_tenant_scoped(self, db):
        repo = FreightOrderRepository(db)
        self._create(db, repo, "ord-001")
        self._create(db, repo, "ord-002")
        assert len(repo.get_by_company(1)) == 2
        assert repo.get_by_company(2) == []

    def test_get_by_trans_eu_order_id(self, db):
        repo = FreightOrderRepository(db)
        self._create(db, repo, "ord-001")
        self._create(db, repo, "ord-002")
        row = repo.get_by_trans_eu_order_id(1, "ord-002")
        assert row is not None and row["trans_eu_order_id"] == "ord-002"
        assert repo.get_by_trans_eu_order_id(1, "missing") is None
        assert repo.get_by_trans_eu_order_id(2, "ord-001") is None

    def test_get_by_freight_id(self, db):
        repo = FreightOrderRepository(db)
        self._create(db, repo, "ord-001", freight_id=100)
        self._create(db, repo, "ord-002", freight_id=100)
        self._create(db, repo, "ord-003", freight_id=200)
        rows = repo.get_by_freight_id(1, 100)
        assert {r["trans_eu_order_id"] for r in rows} == {"ord-001", "ord-002"}
        assert repo.get_by_freight_id(1, 200)[0]["trans_eu_order_id"] == "ord-003"
        assert repo.get_by_freight_id(1, 999) == []

    def test_update_status(self, db):
        repo = FreightOrderRepository(db)
        self._create(db, repo, "ord-001")
        assert repo.update_status(1, "ord-001", "confirmed") == 1
        row = repo.get_by_trans_eu_order_id(1, "ord-001")
        assert row["status"] == "confirmed"
        assert repo.update_status(2, "ord-001", "cancelled") == 0
        assert repo.update_status(1, "missing", "cancelled") == 0

    def test_link_trip_and_get_unlinked_by_company(self, db):
        repo = FreightOrderRepository(db)
        _seed_trip(db)
        self._create(db, repo, "ord-001")
        self._create(db, repo, "ord-002")
        assert repo.link_trip(1, "ord-001", 1) == 1
        linked = repo.get_by_trans_eu_order_id(1, "ord-001")
        assert linked["linked_trip_id"] == 1
        unlinked = repo.get_unlinked_by_company(1)
        assert [r["trans_eu_order_id"] for r in unlinked] == ["ord-002"]
        assert repo.link_trip(2, "ord-001", 1) == 0


# ═══════════════════════════════════════════════════════════════════════════
# NegotiationOfferRepository
# ═══════════════════════════════════════════════════════════════════════════


class TestNegotiationOfferRepository:
    def test_create_and_get_thread_by_freight(self, db):
        repo = NegotiationOfferRepository(db)
        first_id = _oid()
        repo.create({
            "id": first_id,
            "company_id": 1,
            "trans_eu_freight_id": 100,
            "offer_id": "offer-1",
            "direction": "inbound",
            "status": "negotiation",
            "price": 1000.0,
            "currency": "EUR",
            "counterparty_name": "Shipper GmbH",
            "counterparty_id": "sp-1",
            "author": "carrier-1",
            "created_at": "2026-09-19T08:00:00",
            "updated_at": "2026-09-19T08:00:00",
        })
        repo.create({
            "id": _oid(),
            "company_id": 1,
            "trans_eu_freight_id": 100,
            "offer_id": "offer-2",
            "direction": "outbound",
            "status": "acceptation",
            "price": 950.0,
            "currency": "EUR",
            "counterparty_name": "Shipper GmbH",
            "counterparty_id": "sp-1",
            "author": "carrier-1",
            "parent_offer_id": first_id,
            "created_at": "2026-09-19T08:05:00",
            "updated_at": "2026-09-19T08:05:00",
        })
        thread = repo.get_thread_by_freight(1, 100)
        assert [r["offer_id"] for r in thread] == ["offer-1", "offer-2"]
        assert thread[1]["parent_offer_id"] == first_id
        assert repo.get_thread_by_freight(1, 999) == []
        assert repo.get_thread_by_freight(2, 100) == []

    def test_get_latest_by_freight(self, db):
        repo = NegotiationOfferRepository(db)
        assert repo.get_latest_by_freight(1, 100) is None
        repo.create({
            "id": _oid(), "company_id": 1, "trans_eu_freight_id": 100,
            "offer_id": "offer-1", "direction": "inbound", "status": "negotiation",
            "price": 1000.0,
            "created_at": "2026-09-19T08:00:00", "updated_at": "2026-09-19T08:00:00",
        })
        repo.create({
            "id": _oid(), "company_id": 1, "trans_eu_freight_id": 100,
            "offer_id": "offer-2", "direction": "outbound", "status": "acceptation",
            "price": 950.0,
            "created_at": "2026-09-19T08:05:00", "updated_at": "2026-09-19T08:05:00",
        })
        latest = repo.get_latest_by_freight(1, 100)
        assert latest["offer_id"] == "offer-2"


# ═══════════════════════════════════════════════════════════════════════════
# DockWarehouseRepository
# ═══════════════════════════════════════════════════════════════════════════


class TestDockWarehouseRepository:
    def test_upsert_creates_then_updates(self, db):
        repo = DockWarehouseRepository(db)
        repo.upsert_by_trans_eu_id(1, {
            "trans_eu_warehouse_id": 1567,
            "name": "Magazyn Stali",
            "address": json.dumps({"country": "PL", "city": "Wroclaw"}),
            "ramps": json.dumps([{"id": 2006, "name": "Suwnica A 1", "ramp_type": "GANTRY"}]),
        })
        rows = repo.get_by_company(1)
        assert len(rows) == 1
        kept_id = rows[0]["id"]
        assert rows[0]["trans_eu_warehouse_id"] == 1567
        assert rows[0]["name"] == "Magazyn Stali"
        assert json.loads(rows[0]["ramps"])[0]["ramp_type"] == "GANTRY"

        # Same trans_eu id → single row, name replaced, id preserved.
        repo.upsert_by_trans_eu_id(1, {
            "trans_eu_warehouse_id": 1567,
            "name": "Magazyn Stali 2",
            "address": json.dumps({"country": "PL", "city": "Wroclaw"}),
            "ramps": json.dumps([]),
        })
        rows = repo.get_by_company(1)
        assert len(rows) == 1
        assert rows[0]["id"] == kept_id
        assert rows[0]["name"] == "Magazyn Stali 2"

    def test_get_by_company_is_tenant_scoped(self, db):
        repo = DockWarehouseRepository(db)
        repo.upsert_by_trans_eu_id(1, {"trans_eu_warehouse_id": 1, "name": "W1"})
        repo.upsert_by_trans_eu_id(2, {"trans_eu_warehouse_id": 1, "name": "W1-copy"})
        assert len(repo.get_by_company(1)) == 1
        assert len(repo.get_by_company(2)) == 1


# ═══════════════════════════════════════════════════════════════════════════
# DockTimeWindowRepository
# ═══════════════════════════════════════════════════════════════════════════


class TestDockTimeWindowRepository:
    def _data(self, window_id: int, warehouse_id: int) -> dict:
        return {
            "trans_eu_window_id": window_id,
            "warehouse_id": warehouse_id,
            "valid_from": "2025-09-08",
            "valid_to": "2025-09-08",
            "start_time": "12:00:00",
            "end_time": "18:00:00",
            "range_type": "CYCLE",
            "external_number": "1DX124DAW7871",
            "carrier_id": 956529,
            "purchase_order": json.dumps({"number": "PO-123", "loads": [{"name": "cargo", "weight": 501}]}),
            "route": json.dumps({"spots": [{"warehouse_id": 6596, "order": 1}]}),
        }

    def test_upsert_and_get_by_warehouse(self, db):
        repo = DockTimeWindowRepository(db)
        repo.upsert(1, self._data(1001, 1567))
        repo.upsert(1, self._data(1002, 1567))
        rows = repo.get_by_warehouse(1, 1567)
        assert len(rows) == 2
        assert {r["trans_eu_window_id"] for r in rows} == {1001, 1002}
        assert json.loads(rows[0]["purchase_order"])["number"] == "PO-123"
        assert repo.get_by_warehouse(1, 999) == []
        assert repo.get_by_warehouse(2, 1567) == []

    def test_upsert_replaces_same_window(self, db):
        repo = DockTimeWindowRepository(db)
        repo.upsert(1, self._data(1001, 1567))
        repo.upsert(1, {**self._data(1001, 1567), "external_number": "CHANGED"})
        rows = repo.get_by_warehouse(1, 1567)
        assert len(rows) == 1
        assert rows[0]["external_number"] == "CHANGED"


# ═══════════════════════════════════════════════════════════════════════════
# DockAnnouncementRepository
# ═══════════════════════════════════════════════════════════════════════════


class TestDockAnnouncementRepository:
    def _data(self, announcement_id: int) -> dict:
        return {
            "trans_eu_announcement_id": announcement_id,
            "reference_number": f"DS/16365BE/{announcement_id}",
            "status": "CONFIRMED",
            "stage": "Vehicle_Arrived",
            "date_from": "2023-07-14",
            "date_to": "2023-07-14",
            "operation_type": "unloading",
            "operation_time": "PT2H",
            "carrier_id": 1013865,
            "carrier_name": "Firma Testowa Przewoznik",
            "shipper_id": 1007386,
            "driver": json.dumps({"full_name": "Jan Kowalski", "phone_number": "+48888123456", "country": "PL"}),
            "vehicle": json.dumps({"truck_plate_number": "123string", "vehicle_manufacturer": "SCANIA"}),
            "ramp_id": 2006,
            "warehouse_id": 1567,
            "route": json.dumps({"spots": [{"order": 1}]}),
            "notes": json.dumps([{"id": 26504, "note": "notatka", "type": "SHIPPER"}]),
            "external_reference_number": "123test",
        }

    def test_upsert_and_get_by_company(self, db):
        repo = DockAnnouncementRepository(db)
        repo.upsert_by_trans_eu_id(1, self._data(38602))
        repo.upsert_by_trans_eu_id(1, self._data(38603))
        rows = repo.get_by_company(1)
        assert len(rows) == 2
        assert json.loads(rows[0]["driver"])["full_name"] == "Jan Kowalski"
        assert json.loads(rows[0]["notes"])[0]["type"] == "SHIPPER"
        assert repo.get_by_company(2) == []

    def test_upsert_updates_status(self, db):
        repo = DockAnnouncementRepository(db)
        repo.upsert_by_trans_eu_id(1, self._data(38602))
        repo.upsert_by_trans_eu_id(1, {**self._data(38602), "status": "IN_PROGRESS"})
        rows = repo.get_by_company(1)
        assert len(rows) == 1
        assert rows[0]["status"] == "IN_PROGRESS"


# ═══════════════════════════════════════════════════════════════════════════
# ProviderContractRepository
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderContractRepository:
    def _data(self, contract_id: str) -> dict:
        return {
            "trans_eu_contract_id": contract_id,
            "contract_type": "fixed",
            "carrier_id": 567321,
            "carrier_name": "EkoTransporter",
            "order_terms": json.dumps({
                "automatic_order_sending": True,
                "payment_period": {"value": 12},
                "monitoring": {"required": True},
                "additional_terms": "text",
            }),
            "status": "active",
        }

    def test_upsert_and_get_by_company(self, db):
        repo = ProviderContractRepository(db)
        repo.upsert_by_trans_eu_id(1, self._data("contract-1"))
        repo.upsert_by_trans_eu_id(1, self._data("contract-2"))
        rows = repo.get_by_company(1)
        assert len(rows) == 2
        assert json.loads(rows[0]["order_terms"])["payment_period"]["value"] == 12
        assert repo.get_by_company(2) == []

    def test_upsert_updates_existing(self, db):
        repo = ProviderContractRepository(db)
        repo.upsert_by_trans_eu_id(1, self._data("contract-1"))
        repo.upsert_by_trans_eu_id(1, {**self._data("contract-1"), "contract_type": "flexible"})
        rows = repo.get_by_company(1)
        assert len(rows) == 1
        assert rows[0]["contract_type"] == "flexible"


# ═══════════════════════════════════════════════════════════════════════════
# ProviderPartnerRepository
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderPartnerRepository:
    def _data(self, partner_id: int) -> dict:
        return {
            "trans_eu_partner_id": partner_id,
            "legal_name": "Firma Testowa",
            "vat_id": "PL1234567890",
            "cooperation_status": "active",
            "groups": json.dumps([{"id": 1, "name": "Grupa A"}]),
            "trans_eu_employee_ids": json.dumps(["1012334-1", "1012334-2"]),
        }

    def test_upsert_and_get_partner_for_company(self, db):
        repo = ProviderPartnerRepository(db)
        assert repo.get_partner_for_company(1, 956529) is None
        repo.upsert_by_trans_eu_id(1, self._data(956529))
        row = repo.get_partner_for_company(1, 956529)
        assert row is not None and row["legal_name"] == "Firma Testowa"
        assert json.loads(row["trans_eu_employee_ids"]) == ["1012334-1", "1012334-2"]
        assert repo.get_partner_for_company(2, 956529) is None

    def test_upsert_updates_existing(self, db):
        repo = ProviderPartnerRepository(db)
        repo.upsert_by_trans_eu_id(1, self._data(956529))
        repo.upsert_by_trans_eu_id(1, {**self._data(956529), "cooperation_status": "blocked"})
        row = repo.get_partner_for_company(1, 956529)
        assert row["cooperation_status"] == "blocked"


# ═══════════════════════════════════════════════════════════════════════════
# ProviderVehicleRepository
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderVehicleRepository:
    def _data(self, vehicle_id: int) -> dict:
        return {
            "trans_eu_vehicle_id": vehicle_id,
            "plate_number": f"DTR{vehicle_id}",
            "vehicle_manufacturer": "SCANIA",
            "chassis_number": f"CH-{vehicle_id}",
            "registration_country": "PL",
            "vin": f"VIN-{vehicle_id}",
            "truck_trailer_plates": json.dumps(["DTR1", "TRAILER1"]),
        }

    def test_upsert_and_get_by_company(self, db):
        repo = ProviderVehicleRepository(db)
        repo.upsert_by_trans_eu_id(1, self._data(100))
        repo.upsert_by_trans_eu_id(1, self._data(101))
        rows = repo.get_by_company(1)
        assert len(rows) == 2
        assert json.loads(rows[0]["truck_trailer_plates"]) == ["DTR1", "TRAILER1"]
        assert repo.get_by_company(2) == []

    def test_upsert_updates_existing(self, db):
        repo = ProviderVehicleRepository(db)
        repo.upsert_by_trans_eu_id(1, self._data(100))
        repo.upsert_by_trans_eu_id(1, {**self._data(100), "plate_number": "NEW123"})
        rows = repo.get_by_company(1)
        assert len(rows) == 1
        assert rows[0]["plate_number"] == "NEW123"


# ═══════════════════════════════════════════════════════════════════════════
# TransEuVehicleOfferRepository
# ═══════════════════════════════════════════════════════════════════════════


class TestTransEuVehicleOfferRepository:
    def _data(self, offer_id: int) -> dict:
        return {
            "trans_eu_offer_id": offer_id,
            "vehicle_id": 100,
            "offer_type": "truck",
            "available_from": "2026-01-01",
            "available_to": "2026-02-01",
            "origin": json.dumps({"country": "PL", "locality": "Wroclaw"}),
            "destination": json.dumps({"country": "DE", "locality": "Berlin"}),
            "price": 1800.0,
            "currency": "EUR",
            "loading_country": "PL",
            "unloading_country": "DE",
            "status": "active",
        }

    def test_upsert_and_get_by_company(self, db):
        repo = TransEuVehicleOfferRepository(db)
        repo.upsert(1, self._data(5001))
        repo.upsert(1, self._data(5002))
        rows = repo.get_by_company(1)
        assert len(rows) == 2
        assert json.loads(rows[0]["origin"])["locality"] == "Wroclaw"
        assert repo.get_by_company(2) == []

    def test_upsert_updates_existing(self, db):
        repo = TransEuVehicleOfferRepository(db)
        repo.upsert(1, self._data(5001))
        repo.upsert(1, {**self._data(5001), "status": "archived"})
        rows = repo.get_by_company(1)
        assert len(rows) == 1
        assert rows[0]["status"] == "archived"