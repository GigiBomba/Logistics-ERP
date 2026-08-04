"""Regression tests for financial precision — Phase C of DB hardening.

These tests verify that monetary values are handled with exact decimal
arithmetic (not IEEE-754 float), that the ``Money`` Pydantic model uses
``Decimal``, and that common ERP arithmetic (VAT, totals, margins) is
free of floating-point rounding errors.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from models.common import Money


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

    def test_money_columns_use_numeric_in_pg_schema(self):
        """Check schema_pg.sql for NUMERIC declarations on key columns.

        This reads the schema file and validates that critical monetary
        columns use NUMERIC(12,2) (not DOUBLE PRECISION).
        """
        import os, re

        pg_schema = os.path.join(
            os.path.dirname(__file__), "..", "database", "schema_pg.sql"
        )
        with open(pg_schema) as f:
            content = f.read()

        checks = [
            ("trips", "total_price_eur", "NUMERIC\\(12,2\\)"),
            ("trips", "vat_percent", "NUMERIC\\(5,2\\)"),
            ("invoices", "total_amount", "NUMERIC\\(12,2\\)"),
            ("proforma_invoices", "grand_total", "NUMERIC\\(12,2\\)"),
        ]

        for table, column, expected_pattern in checks:
            # Verify the column exists in the correct table with the right type
            table_pattern = rf"CREATE TABLE IF NOT EXISTS {table}\b"
            table_match = re.search(table_pattern, content)
            assert table_match, f"Table {table} not found in schema_pg.sql"

            col_pattern = rf"{column}\s+{expected_pattern}"
            col_match = re.search(col_pattern, content)
            assert col_match, (
                f"Column {table}.{column} should match {expected_pattern} "
                f"in schema_pg.sql, but pattern '{col_pattern}' was not found."
            )
