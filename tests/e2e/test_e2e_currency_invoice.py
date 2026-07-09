"""E2E: Currency and invoice workflow — exchange rates, formatting, multi-currency.

Tests the ExchangeRateService singleton, CurrencyService formatting,
and multi-currency invoice generation with mocked external APIs.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from repositories.invoice_repository import InvoiceRepository
from services.currency_service import CurrencyService
from services.exchange_rate_service import ExchangeRateService
from services.invoicing.service import InvoiceService
from services.trip_service import TripService
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow

logging.disable(logging.CRITICAL)


# ── Helpers ───────────────────────────────────────────────────────────────

def _dt(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


def _reset_exchange_rate_singleton():
    """Reset the ExchangeRateService singleton between tests."""
    ExchangeRateService._instance = None
    # Also remove persisted cache to avoid cross-test contamination
    from services.exchange_rate_service import CACHE_FILE
    try:
        os.remove(CACHE_FILE)
    except (FileNotFoundError, OSError):
        pass


# ── Tests ─────────────────────────────────────────────────────────────────


class TestCurrencyInvoiceFlow:
    """Currency and invoice workflow: exchange rates, formatting, multi-currency."""

    def test_exchange_rate_service_returns_defaults(self, db):
        """Reset singleton, get_rate('RON'), verify default rate."""
        _reset_exchange_rate_singleton()
        svc = ExchangeRateService()

        rate = svc.get_rate("RON")
        assert rate == 4.97  # default RON rate

        rate_eur = svc.get_rate("EUR")
        assert rate_eur == 1.0

        # Unknown currency should return 1.0
        rate_unknown = svc.get_rate("XYZ")
        assert rate_unknown == 1.0

    def test_exchange_rate_service_converts_correctly(self, db):
        """Mock requests.get, refresh rates, verify convert() calculations."""
        _reset_exchange_rate_singleton()
        svc = ExchangeRateService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "RON": 5.0,
                "USD": 1.10,
                "GBP": 0.85,
            },
        }

        with patch("requests.get", return_value=mock_response):
            ok = svc.refresh(background=False)
            assert ok is True

        # Convert 100 EUR to RON
        result = svc.convert(100.0, "EUR", "RON")
        assert result == 500.0  # 100 * 5.0

        # Convert 100 USD to EUR
        result = svc.convert(100.0, "USD", "EUR")
        assert round(result, 2) == 90.91  # 100 / 1.10

        # Same currency should return unchanged
        result = svc.convert(200.0, "EUR", "EUR")
        assert result == 200.0

        # Convert 100 GBP to USD
        result = svc.convert(100.0, "GBP", "USD")
        assert round(result, 2) == 129.41  # (100 / 0.85) * 1.10

    def test_currency_service_formats_correctly(self, db):
        """format() with EUR (suffix €), USD (prefix $), GBP (prefix £), RON (suffix lei)."""
        cs = CurrencyService()

        # EUR: suffix €  (not in prefix list)
        formatted = cs.format(1234.5, "EUR")
        assert "1,234.50" in formatted
        assert "€" in formatted
        assert formatted.endswith("€") or "€" in formatted
        # EUR has suffix format
        assert formatted == "1,234.50 €"

        # USD: prefix $
        formatted = cs.format(999.99, "USD")
        assert formatted == "$999.99"

        # GBP: prefix £
        formatted = cs.format(500.0, "GBP")
        assert formatted == "£500.00"

        # RON: suffix lei
        formatted = cs.format(2500.0, "RON")
        assert formatted == "2,500.00 lei"

    def test_multi_currency_invoice_generation(self, db):
        """Create trip with currency, mock PDF, generate invoice, verify DB record."""
        trip_service = TripService(db)
        invoice_repo = InvoiceRepository(db)

        now = datetime.now().isoformat()
        trip_id = trip_service.add({
            "client_name": "Currency Client SRL",
            "truck_number": "TR-CUR-001",
            "driver_name": "Currency Driver",
            "start_date": _dt(-5),
            "end_date": _dt(-3),
            "distance_km": 1000.0,
            "total_price_eur": 5000.0,
            "rate_per_km": 5.0,
            "fuel_cost": 800.0,
            "toll_cost": 150.0,
            "salary_cost": 400.0,
            "extra_costs": 50.0,
            "net_profit": 3600.0,
            "currency": "RON",
            "status": "Delivered",
            "created_at": now,
            "cargo_description": "Currency test cargo",
            "package_count": 20,
            "gross_weight_kg": 10000.0,
        })
        assert trip_id > 0

        trip = trip_service.get_by_id(trip_id)
        assert trip["currency"] == "RON"

        # Mock PDF generation for InvoiceService
        with patch.object(InvoiceService, "generate",
                          return_value=os.path.join(tempfile.gettempdir(), f"INV-CUR-{trip_id}.pdf")):
            inv_svc = InvoiceService(db)
            # generate_and_record uses "INV-{year}-{trip_id:04d}" format
            inv_number = f"INV-{datetime.now().year}-{trip_id:04d}"

            inv_svc.generate_and_record(
                trip_data={
                    "id": trip_id,
                    "client_name": "Currency Client SRL",
                    "total_price_eur": 5000.0,
                    "distance_km": 1000.0,
                    "truck_number": "TR-CUR-001",
                    "currency": "RON",
                },
                mode="client",
            )

        # Verify invoice record in DB
        invoice = invoice_repo.get_by_trip_id(trip_id)
        assert invoice is not None
        assert invoice["total_amount"] == 5000.0
        assert invoice["status"] == "Unpaid"
        assert invoice["invoice_number"] == inv_number
        assert invoice["due_date"] is not None

    def test_exchange_rate_staleness_detection(self, db):
        """Set _last_updated to 2h ago, verify refresh_if_stale triggers refresh."""
        _reset_exchange_rate_singleton()
        svc = ExchangeRateService()

        # Manually set last_updated far in the past (CACHE_TTL_SECONDS = 3600 = 1h)
        svc._last_updated = time.time() - 7200  # 2 hours ago
        svc._last_fetch_ok = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "RON": 5.05,
                "USD": 1.12,
            },
        }

        with patch("requests.get", return_value=mock_response) as mock_get:
            result = svc.refresh_if_stale()
            assert result is True
            mock_get.assert_called_once()

        # Verify rates were updated
        rate_ron = svc.get_rate("RON")
        assert rate_ron == 5.05
