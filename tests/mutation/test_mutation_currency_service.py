from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from services.currency_service import CurrencyService

pytestmark = pytest.mark.mutation


class TestKillMutationCurrencyFormat:
    """Kill mutations in CurrencyService.format().

    format(amount, currency_code, decimals=2) -> str

    Prefix currencies (USD, GBP, BGN):  "$1,234.56"
    Suffix currencies (all others):     "1,234.56 €"
    """

    @pytest.fixture
    def service(self):
        return CurrencyService(exchange_service=MagicMock())

    # ── 1. BGN uses prefix format (лв) — "BGN" removed from prefix tuple ──
    def test_bgn_uses_prefix_format(self, service):
        """BGN must use prefix format: лв1,234.56.
        A mutation that removes 'BGN' from the prefix tuple will produce
        suffix format '1,234.56 лв'."""
        result = service.format(1234.56, "BGN")
        assert result.startswith("лв"), f"BGN must be prefix format, got {result!r}"
        assert "1,234.56" in result
        assert result == "лв1,234.56", (
            f"Expected 'лв1,234.56', got {result!r}"
        )

    # ── 2. USD uses prefix format ($) — "USD" removed ──
    def test_usd_uses_prefix_format(self, service):
        """USD must use prefix format: $1,234.56."""
        result = service.format(1234.56, "USD")
        assert result.startswith("$"), f"USD must be prefix format, got {result!r}"
        assert result == "$1,234.56"

    # ── 3. GBP uses prefix format (£) — "GBP" removed ──
    def test_gbp_uses_prefix_format(self, service):
        """GBP must use prefix format: £1,234.56."""
        result = service.format(1234.56, "GBP")
        assert result.startswith("£"), f"GBP must be prefix format, got {result!r}"
        assert result == "£1,234.56"

    # ── 4. EUR uses suffix format (€) ──
    def test_eur_uses_suffix_format(self, service):
        """EUR must use suffix format: 1,234.56 €."""
        result = service.format(1234.56, "EUR")
        assert result.endswith("€"), f"EUR must be suffix format, got {result!r}"
        assert result == "1,234.56 €"

    # ── 5. RON uses suffix format (lei) ──
    def test_ron_uses_suffix_format(self, service):
        """RON must use suffix format: 1,234.56 lei."""
        result = service.format(1234.56, "RON")
        assert result.endswith("lei"), f"RON must be suffix format, got {result!r}"
        assert result == "1,234.56 lei"

    # ── 6. CZK uses suffix format (Kč) ──
    def test_czk_uses_suffix_format(self, service):
        """CZK must use suffix format: 1,234.56 Kč."""
        result = service.format(1234.56, "CZK")
        assert result.endswith("Kč"), f"CZK must be suffix format, got {result!r}"
        assert result == "1,234.56 Kč"

    # ── 7. Thousand separators included ──
    def test_thousand_separators_included(self, service):
        """Large numbers must include thousand separators.
        A mutation that removes the comma from the format string will fail."""
        result = service.format(1234567.89, "EUR")
        assert "1,234,567.89" in result, (
            f"Expected thousand separators, got {result!r}"
        )

        result_usd = service.format(1234567.89, "USD")
        assert "1,234,567.89" in result_usd, (
            f"Expected thousand separators in USD, got {result_usd!r}"
        )

    # ── 8. Custom decimals parameter respected ──
    @pytest.mark.parametrize("decimals, expected_pattern", [
        (0, "42"),
        (3, "42.000"),
    ])
    def test_custom_decimals(self, service, decimals, expected_pattern):
        """The decimals parameter must be passed through to the format string."""
        result = service.format(42, "EUR", decimals=decimals)
        assert expected_pattern in result, (
            f"Expected {expected_pattern!r} in result, got {result!r}"
        )
