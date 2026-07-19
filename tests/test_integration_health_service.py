"""Comprehensive unit tests for IntegrationHealthService.

Tests cover health-checks for every registered integration (graphhopper,
nominatim, currency_api, fuel_price, timocom), caching behaviour, error
detection, latency measurement, and all specified edge cases.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.integration_health_service import (
    IntegrationHealthService,
    IntegrationStatus,
    _status_to_dict,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def service() -> IntegrationHealthService:
    """Return an IntegrationHealthService with a mock DB."""
    db = MagicMock()
    svc = IntegrationHealthService(db)
    # Clear the cache between tests
    svc._status_cache = {}
    return svc


@pytest.fixture
def healthy_status() -> IntegrationStatus:
    return IntegrationStatus(
        name="GraphHopper Routing",
        connected=True,
        last_check=datetime(2025, 1, 1, 12, 0, 0),
        last_success=datetime(2025, 1, 1, 12, 0, 0),
        last_error=None,
        latency_ms=45.2,
    )


@pytest.fixture
def degraded_status() -> IntegrationStatus:
    return IntegrationStatus(
        name="GraphHopper Routing",
        connected=True,
        last_check=datetime(2025, 1, 1, 12, 0, 0),
        last_success=datetime(2025, 1, 1, 11, 55, 0),
        last_error=None,
        latency_ms=1200.0,
    )


@pytest.fixture
def down_status() -> IntegrationStatus:
    return IntegrationStatus(
        name="GraphHopper Routing",
        connected=False,
        last_check=datetime(2025, 1, 1, 12, 0, 0),
        last_success=None,
        last_error="Connection refused",
        latency_ms=None,
    )


# ─────────────────────────────────────────────────────────────────────
# _status_to_dict
# ─────────────────────────────────────────────────────────────────────


class TestStatusToDict:
    def test_healthy_status(self, healthy_status: IntegrationStatus):
        d = _status_to_dict(healthy_status)
        assert d["name"] == "GraphHopper Routing"
        assert d["connected"] is True
        assert d["latency_ms"] == 45.2
        assert d["last_error"] is None

    def test_down_status(self, down_status: IntegrationStatus):
        d = _status_to_dict(down_status)
        assert d["connected"] is False
        assert d["last_error"] == "Connection refused"
        assert d["latency_ms"] is None
        assert d["last_success"] is None

    def test_last_check_isoformat(self, healthy_status: IntegrationStatus):
        d = _status_to_dict(healthy_status)
        assert d["last_check"] == "2025-01-01T12:00:00"

    def test_none_last_check(self):
        status = IntegrationStatus(name="Test", connected=False)
        d = _status_to_dict(status)
        assert d["last_check"] is None


# ─────────────────────────────────────────────────────────────────────
# Unknown integration
# ─────────────────────────────────────────────────────────────────────


class TestUnknownIntegration:
    def test_get_status_unknown(self, service: IntegrationHealthService):
        result = service.get_status("nonexistent_integration")
        assert result["connected"] is False
        assert "Unknown integration" in result.get("error", "")

    def test_check_now_unknown(self, service: IntegrationHealthService):
        result = service.check_now("nonexistent_integration")
        assert result["connected"] is False
        assert "Unknown integration" in result.get("error", "")

    def test_unknown_does_not_cache(self, service: IntegrationHealthService):
        service.check_now("ghost")
        assert "ghost" not in service._status_cache


# ─────────────────────────────────────────────────────────────────────
# GraphHopper health check
# ─────────────────────────────────────────────────────────────────────


class TestGraphhopperCheck:
    def test_healthy(self, service: IntegrationHealthService):
        with patch.dict("os.environ", {
            "OPERION_GRAPHHOPPER_URL": "https://graphhopper.test",
            "OPERION_GRAPHHOPPER_API_KEY": "test-key-123",
        }), patch("requests.get") as mock_get, \
             patch("time.time", side_effect=[1000.0, 1000.045]):
            mock_get.return_value.status_code = 200
            service._get_setting = MagicMock(return_value="1")

            result = service.check_now("graphhopper")
            assert result["connected"] is True
            assert result["latency_ms"] == 45.0
            assert result["name"] == "GraphHopper Routing"

    def test_unhealthy_response(self, service: IntegrationHealthService):
        with patch.dict("os.environ", {
            "OPERION_GRAPHHOPPER_URL": "https://graphhopper.test",
            "OPERION_GRAPHHOPPER_API_KEY": "test-key-123",
        }), patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 503
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("graphhopper")
            assert result["connected"] is False
            assert "HTTP 503" in result.get("last_error", "")

    def test_no_api_key_reports_not_configured(self, service: IntegrationHealthService):
        with patch.dict("os.environ", {}, clear=True):
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("graphhopper")
            assert result["connected"] is False
            assert "API key not configured" in result.get("last_error", "")

    def test_timeout(self, service: IntegrationHealthService):
        with patch.dict("os.environ", {
            "OPERION_GRAPHHOPPER_URL": "https://graphhopper.test",
            "OPERION_GRAPHHOPPER_API_KEY": "key",
        }), patch("requests.get") as mock_get:
            import requests
            mock_get.side_effect = requests.ConnectionError("Connection timeout")
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("graphhopper")
            assert result["connected"] is False
            assert "timeout" in result.get("last_error", "").lower()

    def test_disabled_in_settings(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="0")
        result = service.check_now("graphhopper")
        assert result["connected"] is False
        assert "disabled in settings" in result.get("last_error", "").lower()


# ─────────────────────────────────────────────────────────────────────
# Nominatim health check
# ─────────────────────────────────────────────────────────────────────


class TestNominatimCheck:
    def test_healthy(self, service: IntegrationHealthService):
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("nominatim")
            assert result["connected"] is True
            assert result["name"] == "Nominatim Geocoding"

    def test_unhealthy(self, service: IntegrationHealthService):
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 500
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("nominatim")
            assert result["connected"] is False

    def test_connection_error(self, service: IntegrationHealthService):
        with patch("requests.get") as mock_get:
            import requests
            mock_get.side_effect = requests.ConnectionError("DNS failure")
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("nominatim")
            assert result["connected"] is False
            assert "DNS failure" in result.get("last_error", "")

    def test_latency_recorded(self, service: IntegrationHealthService):
        with patch("requests.get") as mock_get, \
             patch("time.time", side_effect=[2000.0, 2000.123]):
            mock_get.return_value.status_code = 200
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("nominatim")
            assert result["latency_ms"] == 123.0
            assert isinstance(result["latency_ms"], (int, float))


# ─────────────────────────────────────────────────────────────────────
# Currency API health check
# ─────────────────────────────────────────────────────────────────────


class TestCurrencyApiCheck:
    def test_healthy(self, service: IntegrationHealthService):
        with patch(
            "services.currency_service.CurrencyService"
        ) as MockCur:
            mock_svc = MockCur.return_value
            mock_svc.is_available.return_value = True
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("currency_api")
            assert result["connected"] is True
            assert result["name"] == "Exchange Rate API"

    def test_unhealthy(self, service: IntegrationHealthService):
        with patch(
            "services.currency_service.CurrencyService"
        ) as MockCur:
            mock_svc = MockCur.return_value
            mock_svc.is_available.return_value = False
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("currency_api")
            assert result["connected"] is False
            assert "unavailable" in result.get("last_error", "").lower()

    def test_exception(self, service: IntegrationHealthService):
        with patch(
            "services.currency_service.CurrencyService"
        ) as MockCur:
            MockCur.side_effect = RuntimeError("ImportError")
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("currency_api")
            assert result["connected"] is False


# ─────────────────────────────────────────────────────────────────────
# Fuel Price health check
# ─────────────────────────────────────────────────────────────────────


class TestFuelPriceCheck:
    def test_healthy(self, service: IntegrationHealthService):
        with patch(
            "services.fuel_price_service.FuelPriceService"
        ) as MockFuel:
            mock_svc = MockFuel.return_value
            mock_svc.is_available.return_value = True
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("fuel_price")
            assert result["connected"] is True
            assert result["name"] == "Fuel Price Scraper"

    def test_unhealthy(self, service: IntegrationHealthService):
        with patch(
            "services.fuel_price_service.FuelPriceService"
        ) as MockFuel:
            mock_svc = MockFuel.return_value
            mock_svc.is_available.return_value = False
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("fuel_price")
            assert result["connected"] is False
            assert "unavailable" in result.get("last_error", "").lower()

    def test_exception(self, service: IntegrationHealthService):
        with patch(
            "services.fuel_price_service.FuelPriceService"
        ) as MockFuel:
            MockFuel.side_effect = RuntimeError("Broken")
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("fuel_price")
            assert result["connected"] is False


# ─────────────────────────────────────────────────────────────────────
# TIMOCOM health check
# ─────────────────────────────────────────────────────────────────────


class TestTimocomCheck:
    def test_healthy(self, service: IntegrationHealthService):
        with patch.dict("os.environ", {
            "TIMOCOM_API_URL": "https://timocom.test",
            "TIMOCOM_API_KEY": "tc-key",
        }), patch(
            "services.http_client.ExternalHttpClient"
        ) as MockClient:
            mock_client = MockClient.return_value
            mock_client.get.return_value.status_code = 200
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("timocom")
            assert result["connected"] is True
            assert result["name"] == "TIMOCOM Freight Exchange"

    def test_unhealthy_response(self, service: IntegrationHealthService):
        with patch.dict("os.environ", {
            "TIMOCOM_API_URL": "https://timocom.test",
            "TIMOCOM_API_KEY": "tc-key",
        }), patch(
            "services.http_client.ExternalHttpClient"
        ) as MockClient:
            mock_client = MockClient.return_value
            mock_client.get.return_value.status_code = 403
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("timocom")
            assert result["connected"] is False
            assert "HTTP" in result.get("last_error", "")

    def test_not_configured(self, service: IntegrationHealthService):
        with patch.dict("os.environ", {}, clear=True):
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("timocom")
            assert result["connected"] is False
            assert "not configured" in result.get("last_error", "").lower()

    def test_exception(self, service: IntegrationHealthService):
        with patch.dict("os.environ", {
            "TIMOCOM_API_URL": "https://timocom.test",
            "TIMOCOM_API_KEY": "tc-key",
        }), patch(
            "services.http_client.ExternalHttpClient"
        ) as MockClient:
            MockClient.side_effect = RuntimeError("Client init fail")
            service._get_setting = MagicMock(return_value="1")
            result = service.check_now("timocom")
            assert result["connected"] is False


# ─────────────────────────────────────────────────────────────────────
# get_all_statuses
# ─────────────────────────────────────────────────────────────────────


class TestGetAllStatuses:
    def test_returns_all_integrations(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="1")
        # Make every check return connected
        with patch.object(service, "_check_integration") as mock_check:
            mock_check.return_value = IntegrationStatus(
                name="Any", connected=True, last_check=datetime.now(),
            )
            result = service.get_all_statuses()
            assert "integrations" in result
            assert len(result["integrations"]) == 5

    def test_counts_healthy(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="1")
        with patch.object(service, "_check_integration") as mock_check:
            def _fake_check(name: str, info: dict):
                connected = name != "nominatim"  # one "down"
                return IntegrationStatus(
                    name=info["display_name"],
                    connected=connected,
                    last_check=datetime.now(),
                )
            mock_check.side_effect = _fake_check
            result = service.get_all_statuses()
            assert result["healthy_count"] == 4
            assert result["total_count"] == 5

    def test_includes_integration_names(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="1")
        with patch.object(service, "_check_integration") as mock_check:
            mock_check.return_value = IntegrationStatus(
                name="Any", connected=True, last_check=datetime.now(),
            )
            result = service.get_all_statuses()
            keys = set(result["integrations"].keys())
            assert keys == {
                "graphhopper", "nominatim", "currency_api",
                "fuel_price", "timocom",
            }


# ─────────────────────────────────────────────────────────────────────
# Caching behaviour
# ─────────────────────────────────────────────────────────────────────


class TestCaching:
    def test_get_status_uses_cache(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="1")
        with patch.object(service, "_check_integration") as mock_check:
            mock_check.return_value = IntegrationStatus(
                name="Test", connected=True, last_check=datetime.now(),
            )
            # First call populates cache
            service.get_status("graphhopper")
            # Second call should use cache, not _check_integration
            service.get_status("graphhopper")
            assert mock_check.call_count == 1

    def test_cache_expired_rechecks(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="1")
        with patch.object(service, "_check_integration") as mock_check:
            mock_check.return_value = IntegrationStatus(
                name="Test", connected=True,
                last_check=datetime.now() - timedelta(hours=1),
            )
            service.get_status("graphhopper")  # caches
            service.get_status("graphhopper")  # expired -> recheck
            assert mock_check.call_count == 2

    def test_check_now_bypasses_cache(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="1")
        with patch.object(service, "_check_integration") as mock_check:
            mock_check.return_value = IntegrationStatus(
                name="Test", connected=True, last_check=datetime.now(),
            )
            service.check_now("graphhopper")
            service.check_now("graphhopper")
            # check_now always calls _check_integration
            assert mock_check.call_count == 2

    def test_cache_updates_after_check_now(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="1")
        with patch.object(service, "_check_integration") as mock_check:
            mock_check.return_value = IntegrationStatus(
                name="Test", connected=True, last_check=datetime.now(),
            )
            service.check_now("graphhopper")
            assert "graphhopper" in service._status_cache

    def test_cache_ttl_not_expired(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="1")
        cached_status = IntegrationStatus(
            name="Cached",
            connected=True,
            last_check=datetime.now() - timedelta(minutes=2),  # 2 min < 5 min TTL
        )
        service._status_cache["graphhopper"] = cached_status

        with patch.object(service, "_check_integration") as mock_check:
            result = service.get_status("graphhopper")
            assert result["name"] == "Cached"
            mock_check.assert_not_called()


# ─────────────────────────────────────────────────────────────────────
# _get_setting
# ─────────────────────────────────────────────────────────────────────


class TestGetSetting:
    def test_returns_value_from_db(self, service: IntegrationHealthService):
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get.return_value = "some_value"
            result = service._get_setting("test.key", "default")
            assert result == "some_value"

    def test_returns_default_when_empty(self, service: IntegrationHealthService):
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get.return_value = ""
            result = service._get_setting("test.key", "fallback")
            assert result == "fallback"

    def test_returns_default_on_exception(self, service: IntegrationHealthService):
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            MockRepo.side_effect = RuntimeError("DB error")
            result = service._get_setting("test.key", "default_val")
            assert result == "default_val"


# ─────────────────────────────────────────────────────────────────────
# _check_integration – generic error handling
# ─────────────────────────────────────────────────────────────────────


class TestCheckIntegrationGeneric:
    def test_unhandled_exception_caught(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="1")
        with patch.object(service, "_check_graphhopper") as mock_check:
            mock_check.side_effect = ValueError("Unexpected!")
            result = service._check_integration("graphhopper", {
                "display_name": "GraphHopper Routing",
                "config_key_base": "graphhopper",
            })
            assert result.connected is False
            assert result.last_error is not None
            assert "Unexpected" in result.last_error

    def test_disabled_integration(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="0")
        status = service._check_integration("graphhopper", {
            "display_name": "GraphHopper Routing",
            "config_key_base": "graphhopper",
        })
        assert status.connected is False
        assert status.last_error is not None and "disabled" in status.last_error.lower()

    def test_success_updates_last_success(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="1")
        with patch.object(service, "_check_graphhopper") as mock_check:
            mock_check.return_value = IntegrationStatus(
                name="GraphHopper Routing", connected=True,
                last_check=datetime.now(),
            )
            status = service._check_integration("graphhopper", {
                "display_name": "GraphHopper Routing",
                "config_key_base": "graphhopper",
            })
            assert status.last_success is not None


# ─────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_latency_rounding(self, service: IntegrationHealthService):
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            service._get_setting = MagicMock(return_value="1")
            with patch("time.time", side_effect=[1000.0, 1000.12345]):
                result = service.check_now("nominatim")
                # 123.45 ms rounded to 1 decimal = 123.5
                assert result["latency_ms"] == 123.5

    def test_error_truncated_to_200_chars(self, service: IntegrationHealthService):
        service._get_setting = MagicMock(return_value="1")
        with patch.object(service, "_check_graphhopper") as mock_check:
            mock_check.side_effect = Exception("x" * 500)
            result = service._check_integration("graphhopper", {
                "display_name": "GraphHopper Routing",
                "config_key_base": "graphhopper",
            })
            assert result.last_error is not None and len(result.last_error) == 200

    def test_all_integrations_have_display_name(self):
        from services.integration_health_service import IntegrationHealthService
        for name, info in IntegrationHealthService._REGISTERED_INTEGRATIONS.items():
            assert "display_name" in info, f"{name} missing display_name"
            assert "config_key_base" in info, f"{name} missing config_key_base"
