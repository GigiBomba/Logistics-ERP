"""Trans.eu Domain (Phase 3) — orders, negotiation, dock scheduler, providers.

Creates the 9 Trans.eu domain tables (TransEU_Architecture.md §5.1/§9.13;
TransEU_KnowledgeBase.md §6.8/§6.9/§7.2-§7.7):

    freight_orders, negotiation_offers, dock_warehouses, dock_time_windows,
    dock_announcements, provider_contracts, provider_partners,
    provider_vehicles, trans_eu_vehicle_offers

These are NEW tables — the Phase-1 Trans.eu tables (trans_eu_user_tokens,
trans_eu_freight_offers, trans_eu_webhook_events, trans_eu_webhook_events_failed
— revision a9b0c1d2e3f5) and freight_negotiations are deliberately NOT
re-created here.  JSON columns are JSONB (they store the raw Trans.eu KB
object shapes); SQLite mirrors these as TEXT (database/schema.py).

Idempotent-guarded: database/schema_pg.sql pre-creates all 9 tables (CREATE
TABLE IF NOT EXISTS) BEFORE Alembic runs on the deployment path
(DatabaseManager._init_pg_schema_locked → _init_pg_schema →
_run_alembic_upgrade).  An unconditional ``op.create_table`` would abort the
whole chain on a fresh PostgreSQL database.  On such databases this migration
is a no-op (mirrors i1a2b3c4d5e6); on pure-Alembic databases it creates the
tables.

Revision ID: p1q2r3s4t5u7
Revises: o8g9b0c2e5f6
Create Date: 2026-09-19
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p1q2r3s4t5u7"
down_revision: Union[str, Sequence[str], None] = "o8g9b0c2e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Tables ────────────────────────────────────────────────────────────────

FREIGHT_ORDERS = (
    "freight_orders",
    [
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trans_eu_order_id", sa.String(), nullable=False),
        sa.Column("trans_eu_freight_id", sa.Integer(), nullable=False),
        sa.Column("order_number", sa.String(), nullable=False, server_default=""),
        sa.Column("status", sa.String(), nullable=False, server_default="created"),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("payment_type", sa.String(), nullable=False, server_default=""),
        sa.Column("execution_data", postgresql.JSONB(), nullable=True),
        sa.Column("linked_trip_id", sa.BigInteger(), sa.ForeignKey("trips.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "trans_eu_order_id"),
    ],
    [
        ("idx_freight_orders_company", ["company_id"]),
        ("idx_freight_orders_freight_id", ["company_id", "trans_eu_freight_id"]),
        ("idx_freight_orders_trip", ["linked_trip_id"]),
    ],
)

NEGOTIATION_OFFERS = (
    "negotiation_offers",
    [
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trans_eu_freight_id", sa.Integer(), nullable=False),
        sa.Column("offer_id", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False, server_default="inbound"),
        sa.Column("status", sa.String(), nullable=False, server_default="negotiation"),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("counterparty_name", sa.String(), nullable=False, server_default=""),
        sa.Column("counterparty_id", sa.String(), nullable=False, server_default=""),
        sa.Column("author", sa.String(), nullable=False, server_default=""),
        sa.Column("parent_offer_id", sa.UUID(), sa.ForeignKey("negotiation_offers.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "offer_id"),
    ],
    [
        ("idx_negotiation_offers_freight", ["company_id", "trans_eu_freight_id"]),
    ],
)

DOCK_WAREHOUSES = (
    "dock_warehouses",
    [
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trans_eu_warehouse_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False, server_default=""),
        sa.Column("address", postgresql.JSONB(), nullable=True),
        sa.Column("ramps", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "trans_eu_warehouse_id"),
    ],
    [
        ("idx_dock_warehouses_company", ["company_id"]),
    ],
)

DOCK_TIME_WINDOWS = (
    "dock_time_windows",
    [
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trans_eu_window_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("start_time", sa.String(), nullable=True),
        sa.Column("end_time", sa.String(), nullable=True),
        sa.Column("range_type", sa.String(), nullable=False, server_default=""),
        sa.Column("external_number", sa.String(), nullable=False, server_default=""),
        sa.Column("carrier_id", sa.Integer(), nullable=True),
        sa.Column("purchase_order", postgresql.JSONB(), nullable=True),
        sa.Column("route", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "trans_eu_window_id"),
    ],
    [
        ("idx_dock_time_windows_warehouse", ["company_id", "warehouse_id"]),
    ],
)

DOCK_ANNOUNCEMENTS = (
    "dock_announcements",
    [
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trans_eu_announcement_id", sa.Integer(), nullable=False),
        sa.Column("reference_number", sa.String(), nullable=False, server_default=""),
        sa.Column("status", sa.String(), nullable=False, server_default="CONFIRMED"),
        sa.Column("stage", sa.String(), nullable=False, server_default="Vehicle_Arrived"),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("operation_type", sa.String(), nullable=False, server_default=""),
        sa.Column("operation_time", sa.String(), nullable=False, server_default=""),
        sa.Column("carrier_id", sa.Integer(), nullable=True),
        sa.Column("carrier_name", sa.String(), nullable=False, server_default=""),
        sa.Column("shipper_id", sa.Integer(), nullable=True),
        sa.Column("driver", postgresql.JSONB(), nullable=True),
        sa.Column("vehicle", postgresql.JSONB(), nullable=True),
        sa.Column("ramp_id", sa.Integer(), nullable=True),
        sa.Column("warehouse_id", sa.Integer(), nullable=True),
        sa.Column("route", postgresql.JSONB(), nullable=True),
        sa.Column("notes", postgresql.JSONB(), nullable=True),
        sa.Column("external_reference_number", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "trans_eu_announcement_id"),
    ],
    [
        ("idx_dock_announcements_company", ["company_id"]),
        ("idx_dock_announcements_status", ["company_id", "status"]),
    ],
)

PROVIDER_CONTRACTS = (
    "provider_contracts",
    [
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trans_eu_contract_id", sa.String(), nullable=False),
        sa.Column("contract_type", sa.String(), nullable=False, server_default="fixed"),
        sa.Column("carrier_id", sa.Integer(), nullable=True),
        sa.Column("carrier_name", sa.String(), nullable=False, server_default=""),
        sa.Column("order_terms", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="registered"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "trans_eu_contract_id"),
    ],
    [
        ("idx_provider_contracts_company", ["company_id"]),
    ],
)

PROVIDER_PARTNERS = (
    "provider_partners",
    [
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trans_eu_partner_id", sa.Integer(), nullable=False),
        sa.Column("legal_name", sa.String(), nullable=False, server_default=""),
        sa.Column("vat_id", sa.String(), nullable=False, server_default=""),
        sa.Column("cooperation_status", sa.String(), nullable=False, server_default="active"),
        sa.Column("groups", postgresql.JSONB(), nullable=True),
        sa.Column("trans_eu_employee_ids", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "trans_eu_partner_id"),
    ],
    [
        ("idx_provider_partners_company", ["company_id"]),
    ],
)

PROVIDER_VEHICLES = (
    "provider_vehicles",
    [
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trans_eu_vehicle_id", sa.Integer(), nullable=False),
        sa.Column("plate_number", sa.String(), nullable=False, server_default=""),
        sa.Column("vehicle_manufacturer", sa.String(), nullable=False, server_default=""),
        sa.Column("chassis_number", sa.String(), nullable=False, server_default=""),
        sa.Column("registration_country", sa.String(), nullable=False, server_default=""),
        sa.Column("vin", sa.String(), nullable=False, server_default=""),
        sa.Column("truck_trailer_plates", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "trans_eu_vehicle_id"),
    ],
    [
        ("idx_provider_vehicles_company", ["company_id"]),
    ],
)

TRANS_EU_VEHICLE_OFFERS = (
    "trans_eu_vehicle_offers",
    [
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trans_eu_offer_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=True),
        sa.Column("offer_type", sa.String(), nullable=False, server_default=""),
        sa.Column("available_from", sa.Date(), nullable=True),
        sa.Column("available_to", sa.Date(), nullable=True),
        sa.Column("origin", postgresql.JSONB(), nullable=True),
        sa.Column("destination", postgresql.JSONB(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("loading_country", sa.String(), nullable=False, server_default=""),
        sa.Column("unloading_country", sa.String(), nullable=False, server_default=""),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "trans_eu_offer_id"),
    ],
    [
        ("idx_trans_eu_vehicle_offers_company", ["company_id"]),
    ],
)

_ALL_TABLES = [
    FREIGHT_ORDERS,
    NEGOTIATION_OFFERS,
    DOCK_WAREHOUSES,
    DOCK_TIME_WINDOWS,
    DOCK_ANNOUNCEMENTS,
    PROVIDER_CONTRACTS,
    PROVIDER_PARTNERS,
    PROVIDER_VEHICLES,
    TRANS_EU_VEHICLE_OFFERS,
]


# ── Helpers ────────────────────────────────────────────────────────────────


def _table_exists(table: str) -> bool:
    """True when *table* already exists in the database.

    ``database/schema_pg.sql`` pre-creates all 9 tables (CREATE TABLE IF NOT
    EXISTS) BEFORE Alembic runs on the deployment path
    (``DatabaseManager._init_pg_schema_locked`` → ``_init_pg_schema`` →
    ``_run_alembic_upgrade``).  An unconditional ``op.create_table`` here
    would abort the whole chain on a fresh PostgreSQL database — PostgreSQL's
    transactional DDL then rolls back every earlier migration and
    ``alembic_version`` never gets stamped.  On such databases this migration
    must be a no-op; on pure-Alembic databases it creates the tables.  This
    mirrors the idempotent guard in i1a2b3c4d5e6.
    """
    from sqlalchemy import inspect

    conn = op.get_bind()
    try:
        return table in inspect(conn).get_table_names()
    except Exception:
        return False


# ── Migration ──────────────────────────────────────────────────────────────


def upgrade() -> None:
    # See _table_exists: schema_pg.sql pre-creates these tables on the
    # deployment path, so skip (the indexes below already exist there too).
    if _table_exists("freight_orders"):
        return

    for table_name, columns, indexes in _ALL_TABLES:
        op.create_table(table_name, *columns)
        for index_name, index_columns in indexes:
            op.create_index(index_name, table_name, index_columns)


def downgrade() -> None:
    for table_name, _columns, indexes in reversed(_ALL_TABLES):
        for index_name, _index_columns in indexes:
            op.drop_index(index_name, table_name=table_name)
        op.drop_table(table_name)