"""Regression tests for financial precision — Phase C of DB hardening.

These tests verify that monetary values are handled with exact decimal
arithmetic (not IEEE-754 float), that the ``Money`` Pydantic model uses
``Decimal``, and that common ERP arithmetic (VAT, totals, margins) is
free of floating-point rounding errors.

Additionally, the schema-text assertions are driven by the actual
Alembic column inventories (``MONETARY_COLUMNS`` from
f7b8c9d0e1f8_financial_precision_numeric_types and ``FIXUP_COLUMNS``
from n7f8a9b0c1d4_financial_precision_followup) so that every migrated
column is checked against database/schema_pg.sql, and the model layer is
asserted to carry ``Decimal`` (never float) on its money fields.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from models.common import Money
from models.invoice_models import InvoiceLineItem, InvoiceResult
from models.proforma_models import ProformaResult
from models.receipt_models import ReceiptResult
from models.trip_models import TripCreate


# ══════════════════════════════════════════════════════════════════════
# Migration column inventory (imported from the Alembic revisions)
# ══════════════════════════════════════════════════════════════════════

_ALEMBIC_VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"


def _load_migration_module(filename: str):
    """Load an Alembic revision module by file path.

    ``alembic/versions`` has no ``__init__.py`` and the installed
    ``alembic`` package shadows the local directory, so a plain import
    would not resolve — load by absolute path instead.
    """
    module_path = _ALEMBIC_VERSIONS_DIR / filename
    spec = importlib.util.spec_from_file_location(
        f"_fp_migration_{filename[:-3].replace('-', '_')}", module_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None, f"No loader for migration {filename}"
    spec.loader.exec_module(module)
    return module


# f7b8c9d0e1f8 — financial_precision_numeric_types (MONETARY_COLUMNS)
# n7f8a9b0c1d4 — financial_precision_followup (FIXUP_COLUMNS)
_MIGRATION_F7B8 = _load_migration_module(
    "f7b8c9d0e1f8_financial_precision_numeric_types.py"
)
_MIGRATION_N7F8 = _load_migration_module(
    "n7f8a9b0c1d4_financial_precision_followup.py"
)

MONETARY_COLUMNS: list[tuple[str, str, str]] = _MIGRATION_F7B8.MONETARY_COLUMNS
FIXUP_COLUMNS: list[tuple[str, str, str]] = _MIGRATION_N7F8.FIXUP_COLUMNS


def _union_columns(*column_lists) -> dict[tuple[str, str], str]:
    """Merge column inventories, keyed by (table, column).

    Raises AssertionError if the same column is given two different
    target types (that would make the union ambiguous).
    """
    merged: dict[tuple[str, str], str] = {}
    for columns in column_lists:
        for table, column, target_type in columns:
            key = (table, column)
            prev = merged.get(key)
            if prev is not None and prev != target_type:
                raise AssertionError(
                    f"Conflicting target types for {table}.{column}: "
                    f"'{prev}' vs '{target_type}'"
                )
            merged[key] = target_type
    return merged


# Every column touched by the two financial-precision migrations, with the
# type each revision is expected to leave behind.  ``invoices.exchange_rate``
# resolves to NUMERIC(8,6) (the fixup's target) — the 8,6 special case.
MIGRATED_COLUMNS: dict[tuple[str, str], str] = _union_columns(
    MONETARY_COLUMNS, FIXUP_COLUMNS
)

MIGRATED_COLUMNS_CASES = [
    pytest.param(table, column, target_type, id=f"{table}.{column}")
    for (table, column), target_type in sorted(MIGRATED_COLUMNS.items())
]


# ══════════════════════════════════════════════════════════════════════
# Schema helpers
# ══════════════════════════════════════════════════════════════════════


def _pg_schema_content() -> str:
    pg_schema = Path(__file__).resolve().parent.parent / "database" / "schema_pg.sql"
    return pg_schema.read_text(encoding="utf-8")


def _table_block(content: str, table: str) -> str:
    """Return the ``CREATE TABLE IF NOT EXISTS <table> (...)`` block.

    Scoping the search to the table block prevents false positives from
    same-named columns in other tables (e.g. ``amount`` in both receipts
    and expenses, ``fuel_cost`` in trips and route_history).
    """
    marker = f"CREATE TABLE IF NOT EXISTS {table} ("
    start = content.find(marker)
    assert start != -1, f"Table {table} not found in schema_pg.sql"
    end = content.find("\n);", start)
    assert end != -1, (
        f"Closing ');' for table {table} not found in schema_pg.sql"
    )
    return content[start:end]


# ══════════════════════════════════════════════════════════════════════
# Money model
# ══════════════════════════════════════════════════════════════════════


class TestMoneyModel:
    """The ``Money`` value type must use ``Decimal`` for ``amount``."""

    def test_amount_is_decimal(self):
        m = Money(amount="12.34", currency="EUR")
        assert isinstance(m.amount, Decimal)
        assert m.amount == Decimal("12.34")

    def test_amount_from_float_is_not_preferred(self):
        """Constructing from float silently loses precision — prove it."""
        m = Money(amount=19.99, currency="EUR")
        assert isinstance(m.amount, Decimal)
        # Pydantic sanitises via str(), so Money stores exact Decimal('19.99').
        # But constructing Decimal(float) directly reveals the hidden float error:
        hidden_error = Decimal(19.99)
        assert hidden_error != Decimal("19.99"), (
            "float 19.99 becomes " + str(hidden_error) + " as Decimal, not 19.99"
        )
        assert m.amount == Decimal("19.99"), "Pydantic's str-based conversion is exact"

    def test_currency_defaults_to_eur(self):
        m = Money(amount="100.00")
        assert m.currency == "EUR"


# ══════════════════════════════════════════════════════════════════════
# Common arithmetic traps
# ══════════════════════════════════════════════════════════════════════


class TestDecimalArithmetic:
    """Classic float-rounding errors that Decimal eliminates."""

    @staticmethod
    def test_float_addition_error():
        """0.1 + 0.2 != 0.3 in IEEE-754 float."""
        # This is the canonical float failure
        assert float(0.1) + float(0.2) != 0.3

    def test_decimal_addition_is_exact(self):
        """0.1 + 0.2 == 0.3 in Decimal."""
        result = Decimal("0.1") + Decimal("0.2")
        assert result == Decimal("0.3")

    def test_vat_calculation(self):
        """VAT at 19% on 100.00 EUR must be exactly 19.00 EUR."""
        net = Decimal("100.00")
        vat_rate = Decimal("0.19")
        vat = (net * vat_rate).quantize(Decimal("0.01"))
        assert vat == Decimal("19.00")
        gross = net + vat
        assert gross == Decimal("119.00")

    def test_vat_at_9_percent(self):
        """Reduced VAT 9% on 250.00 EUR."""
        net = Decimal("250.00")
        vat = (net * Decimal("0.09")).quantize(Decimal("0.01"))
        assert vat == Decimal("22.50")
        assert net + vat == Decimal("272.50")

    def test_margin_calculation(self):
        """Profit margin with 3 decimal places must round correctly."""
        revenue = Decimal("1500.00")
        cost = Decimal("1234.56")
        profit = revenue - cost
        margin = (profit / revenue * 100).quantize(Decimal("0.01"))
        assert profit == Decimal("265.44")
        assert margin == Decimal("17.70")  # 17.696% rounds to 17.70%

    def test_many_small_amounts(self):
        """Summing 1000 micro-transactions must not drift."""
        amounts = [Decimal("0.01") for _ in range(1000)]
        total = sum(amounts, Decimal("0"))
        assert total == Decimal("10.00")

    def test_currency_conversion(self):
        """1000.00 EUR at rate 1.0835 → 1083.50 USD (exact)."""
        eur = Decimal("1000.00")
        rate = Decimal("1.0835")
        usd = (eur * rate).quantize(Decimal("0.01"))
        assert usd == Decimal("1083.50")

    def test_vat_on_rounding_edge(self):
        """0.01 EUR at 24% VAT."""
        net = Decimal("0.01")
        vat = (net * Decimal("0.24")).quantize(Decimal("0.01"))
        assert vat == Decimal("0.00")  # 0.0024 rounds to 0.00 (banker's rounding)
        # Alternatively: 0.01 * 0.24 = 0.0024, truncated to 0.00
        # This is correct: VAT on 1 cent at 24% rounds to 0
        assert net + vat == Decimal("0.01")


# ══════════════════════════════════════════════════════════════════════
# Schema correctness (NUMERIC type assertions)
# ══════════════════════════════════════════════════════════════════════


class TestSchemaMonetaryColumns:
    """Verify that the schema definitions use appropriate numeric types.

    These are static assertions derived from the schema files.
    """

    @pytest.mark.parametrize(
        "table,column,target_type",
        MIGRATED_COLUMNS_CASES,
    )
    def test_migrated_column_has_numeric_type_in_pg_schema(
        self, table: str, column: str, target_type: str
    ):
        """Every column migrated by f7b8c9d0e1f8 / n7f8a9b0c1d4 must be
        declared with its target ``NUMERIC(...)`` type in
        database/schema_pg.sql — never DOUBLE PRECISION."""
        import re

        content = _pg_schema_content()
        block = _table_block(content, table)
        col_pattern = rf"{re.escape(column)}\s+{re.escape(target_type)}"
        assert re.search(col_pattern, block), (
            f"Migrated column {table}.{column} should be declared "
            f"{target_type} in schema_pg.sql, but pattern '{col_pattern}' "
            f"was not found inside the {table} table block."
        )

    def test_money_columns_use_numeric_in_pg_schema(self):
        """Explicit spot-checks of the critical monetary columns.

        Reads the schema file and validates that each listed column uses
        the NUMERIC(...) type (not DOUBLE PRECISION), scoped to its own
        table block so a same-named column elsewhere cannot satisfy the
        assertion by accident.
        """
        import re

        content = _pg_schema_content()

        checks = [
            # ── trips ──────────────────────────────────────────────
            ("trips", "total_price_eur", "NUMERIC(12,2)"),
            ("trips", "vat_percent", "NUMERIC(5,2)"),
            ("trips", "net_profit", "NUMERIC(12,2)"),
            ("trips", "fuel_cost", "NUMERIC(12,2)"),
            # ── invoices ───────────────────────────────────────────
            ("invoices", "total_amount", "NUMERIC(12,2)"),
            ("invoices", "subtotal_net", "NUMERIC(12,2)"),
            ("invoices", "total_vat", "NUMERIC(12,2)"),
            ("invoices", "total_gross", "NUMERIC(12,2)"),
            ("invoices", "amount_paid", "NUMERIC(12,2)"),
            ("invoices", "amount_remaining", "NUMERIC(12,2)"),
            ("invoices", "exchange_rate", "NUMERIC(8,6)"),  # 8,6 by design
            # ── receipts ───────────────────────────────────────────
            ("receipts", "amount", "NUMERIC(12,2)"),
            ("receipts", "vat_rate", "NUMERIC(5,2)"),
            ("receipts", "vat_amount", "NUMERIC(12,2)"),
            ("receipts", "total", "NUMERIC(12,2)"),
            ("receipts", "mileage", "NUMERIC(12,2)"),
            ("receipts", "fuel", "NUMERIC(12,2)"),
            ("receipts", "accommodation", "NUMERIC(12,2)"),
            ("receipts", "meals", "NUMERIC(12,2)"),
            ("receipts", "parking", "NUMERIC(12,2)"),
            ("receipts", "tolls", "NUMERIC(12,2)"),
            ("receipts", "other_expense", "NUMERIC(12,2)"),
            # ── proforma invoices ──────────────────────────────────
            ("proforma_invoices", "grand_total", "NUMERIC(12,2)"),
            # ── other tables ───────────────────────────────────────
            ("contracts", "value_eur", "NUMERIC(12,2)"),
            ("expenses", "amount", "NUMERIC(12,2)"),
            ("freight_negotiations", "amount_eur", "NUMERIC(12,2)"),
            ("trucks", "monthly_rate", "NUMERIC(12,2)"),
            ("drivers", "monthly_salary", "NUMERIC(12,2)"),
            ("clients", "credit_limit_eur", "NUMERIC(12,2)"),
            ("clients", "default_rate_per_km", "NUMERIC(12,6)"),
            ("truck_health_scores", "compliance_pct", "NUMERIC(5,2)"),
            ("document_pipeline_runs", "match_confidence", "NUMERIC(5,4)"),
        ]

        for table, column, target_type in checks:
            block = _table_block(content, table)
            col_pattern = rf"{re.escape(column)}\s+{re.escape(target_type)}"
            assert re.search(col_pattern, block), (
                f"Column {table}.{column} should match {target_type} "
                f"in schema_pg.sql, but pattern '{col_pattern}' was not "
                f"found inside the {table} table block."
            )


# ══════════════════════════════════════════════════════════════════════
# Model-layer precision (Pydantic models carry Decimal, not float)
# ══════════════════════════════════════════════════════════════════════


class TestModelLayerPrecision:
    """Money fields on the Pydantic models are ``Decimal`` instances and
    arithmetic performed through the model layer stays exact."""

    def test_invoice_result_money_fields_are_decimal(self):
        invoice = InvoiceResult(
            id=1,
            invoice_number="INV-2026-0001",
            client_id=1,
            client_name="Acme",
            invoice_date=date(2026, 1, 7),
            due_date=date(2026, 1, 21),
            currency="EUR",
            subtotal_net=Decimal("0.1"),
            total_vat=Decimal("0.02"),
            total_gross=Decimal("0.12"),
            amount_paid=Decimal("0.00"),
            amount_remaining=Decimal("0.12"),
            notes="",
        )
        for field in (
            "exchange_rate",
            "subtotal_net",
            "total_vat",
            "total_gross",
            "amount_paid",
            "amount_remaining",
        ):
            assert isinstance(getattr(invoice, field), Decimal), (
                f"InvoiceResult.{field} must be Decimal, got "
                f"{type(getattr(invoice, field)).__name__}"
            )
        # Exact decimal round-trip through the model: gross - vat == net.
        assert invoice.total_gross - invoice.total_vat == invoice.subtotal_net
        assert invoice.subtotal_net + invoice.total_vat == invoice.total_gross
        assert invoice.total_gross - invoice.amount_paid == invoice.amount_remaining

    def test_receipt_result_total_amount_is_decimal(self):
        receipt = ReceiptResult(
            id=1,
            receipt_number="REC-2026-0001",
            client_id=1,
            client_name="Acme",
            receipt_date=date(2026, 1, 7),
            currency="EUR",
            items=[],
            total_amount=Decimal("0.3"),
        )
        assert isinstance(receipt.total_amount, Decimal)
        assert receipt.total_amount == Decimal("0.3")

    def test_invoice_line_item_fields_are_decimal(self):
        line = InvoiceLineItem(
            description="Transport service",
            quantity=Decimal("3"),
            unit_price=Decimal("0.1"),
            vat_rate=Decimal("19.0"),
        )
        for field in (
            "quantity",
            "unit_price",
            "discount_percent",
            "discount_amount",
            "vat_rate",
        ):
            assert isinstance(getattr(line, field), Decimal), (
                f"InvoiceLineItem.{field} must be Decimal, got "
                f"{type(getattr(line, field)).__name__}"
            )
        # 0.1 * 3 == 0.3 exactly (float would give 0.30000000000000004).
        assert line.unit_price * line.quantity == Decimal("0.3")

    def test_trip_create_price_eur_is_decimal(self):
        trip = TripCreate(
            client_id=1,
            start_date=date(2026, 1, 7),
            price_eur=Decimal("12.34"),
        )
        assert isinstance(trip.price_eur, Decimal)
        assert trip.price_eur == Decimal("12.34")

    def test_proforma_result_total_amount_is_decimal(self):
        proforma = ProformaResult(
            id=1,
            proforma_number="PRO-2026-0001",
            client_id=1,
            client_name="Acme",
            issue_date=date(2026, 1, 7),
            valid_until=date(2026, 2, 7),
            currency="EUR",
            total_amount=Decimal("119.00"),
            status="Draft",
        )
        assert isinstance(proforma.total_amount, Decimal)
        assert proforma.total_amount == Decimal("119.00")

    def test_vat_round_trip_is_exact_in_model_layer(self):
        """0.1 + 0.2 style exactness, computed through the model layer.

        Two Decimal line items at 0.1 and 0.2 must sum to exactly 0.3;
        19% VAT on top and the round trip back (gross - vat) must both
        be exact — no IEEE-754 drift.
        """
        line_items = [
            InvoiceLineItem(
                description="a",
                unit_price=Decimal("0.1"),
                quantity=Decimal("1"),
            ),
            InvoiceLineItem(
                description="b",
                unit_price=Decimal("0.2"),
                quantity=Decimal("1"),
            ),
        ]
        net = sum((li.unit_price * li.quantity for li in line_items), Decimal("0"))
        assert net == Decimal("0.3"), f"0.1 + 0.2 must be exactly 0.3, got {net}"

        vat = (net * Decimal("19.0") / Decimal("100")).quantize(Decimal("0.01"))
        assert vat == Decimal("0.06"), f"19% VAT on 0.30 must be exactly 0.06, got {vat}"

        gross = net + vat
        assert gross == Decimal("0.36")
        # Round trip: recovering net from gross is lossless in Decimal.
        assert gross - vat == net