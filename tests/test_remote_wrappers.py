"""Tests for all remote service wrappers:
   - RemoteAnalyticsService
   - RemoteTachoService
   - RemoteMaintenanceService
   - RemoteInvoiceService
   - RemoteDriverService
   - RemoteRouteHistoryService
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from client.remote_analytics import RemoteAnalyticsService
from client.remote_tacho import RemoteTachoService
from client.remote_maintenance import RemoteMaintenanceService
from client.remote_invoice_service import RemoteInvoiceService
from client.remote_driver_service import RemoteDriverService
from client.remote_route_history import RemoteRouteHistoryService


def _make_clean_params_work(mock_api):
    """Wire _clean_params on the mock so it behaves like the real
    ``ApiClient._clean_params`` static method (strips None and empty
    strings).  Methods like ``get_data`` and ``get_client_payment_timeline``
    call ``self._api._clean_params(...)`` internally and we want the
    assertion on the exact dict rather than a MagicMock proxy.
    """
    mock_api._clean_params.side_effect = (
        lambda **kw: {k: v for k, v in kw.items() if v is not None and v != ""}
    )


# ── RemoteAnalyticsService ──────────────────────────────────────────

class TestRemoteAnalyticsService:
    @pytest.fixture
    def api(self):
        api = MagicMock()
        _make_clean_params_work(api)
        return api

    @pytest.fixture
    def service(self, api):
        return RemoteAnalyticsService(api)

    # ── get_data ────────────────────────────────────────────────────

    def test_get_data_calls_correct_endpoint(self, service, api):
        api.get_analytics_overview.return_value = {"revenue": 1000}
        result = service.get_data(from_date="2024-01-01", to_date="2024-12-31")
        assert result == {"revenue": 1000}
        api.get_analytics_overview.assert_called_once_with()

    def test_get_data_omits_empty_dates(self, service, api):
        api.get_analytics_overview.return_value = {}
        service.get_data()
        api.get_analytics_overview.assert_called_once_with()

    def test_get_data_passes_date_defaults(self, service, api):
        api.get_analytics_overview.return_value = {}
        service.get_data(from_date="", to_date="")
        api.get_analytics_overview.assert_called_once_with()

    def test_get_data_raises_on_api_error(self, service, api):
        api.get_analytics_overview.side_effect = RuntimeError("API unreachable")
        with pytest.raises(RuntimeError, match="API unreachable"):
            service.get_data(from_date="2024-01-01", to_date="2024-12-31")

    # ── get_financial ───────────────────────────────────────────────

    def test_get_financial_calls_api_method(self, service, api):
        api.get_analytics_financial.return_value = {"profit": 500}
        result = service.get_financial(from_date="2024-01", to_date="2024-12")
        assert result == {"profit": 500}
        api.get_analytics_financial.assert_called_once_with(
            from_date="2024-01", to_date="2024-12",
        )

    # ── get_revenue_by_client ───────────────────────────────────────

    def test_get_revenue_by_client_calls_api_method(self, service, api):
        api.get_analytics_revenue_by_client.return_value = {"clients": []}
        result = service.get_revenue_by_client(
            from_date="2024-01-01", to_date="2024-12-31",
        )
        assert result == {"clients": []}
        api.get_analytics_revenue_by_client.assert_called_once_with(
            from_date="2024-01-01", to_date="2024-12-31",
        )

    def test_get_revenue_by_client_empty_dates(self, service, api):
        api.get_analytics_revenue_by_client.return_value = {}
        service.get_revenue_by_client()
        api.get_analytics_revenue_by_client.assert_called_once_with(
            from_date="", to_date="",
        )

    # ── get_revenue_by_country ──────────────────────────────────────

    def test_get_revenue_by_country_calls_api_method(self, service, api):
        api.get_analytics_financial_by_country.return_value = {"by_country": {}}
        result = service.get_revenue_by_country()
        assert result == {"by_country": {}}
        api.get_analytics_financial_by_country.assert_called_once_with(
            from_date="", to_date="",
        )

    # ── get_route_profitability ─────────────────────────────────────

    def test_get_route_profitability_calls_api_method(self, service, api):
        api.get_analytics_route_profitability.return_value = {"routes": []}
        result = service.get_route_profitability()
        api.get_analytics_route_profitability.assert_called_once()

    # ── get_client_analytics ────────────────────────────────────────

    def test_get_client_analytics_calls_api_method(self, service, api):
        api.get_analytics_client.return_value = {"total": 10}
        result = service.get_client_analytics()
        assert result == {"total": 10}
        api.get_analytics_client.assert_called_once_with(from_date="", to_date="")

    # ── get_fleet ──────────────────────────────────────────────────

    def test_get_fleet_calls_api_method(self, service, api):
        api.get_analytics_fleet.return_value = {"trucks": 5}
        result = service.get_fleet()
        assert result == {"trucks": 5}
        api.get_analytics_fleet.assert_called_once_with(from_date="", to_date="")

    # ── get_maintenance_alerts ─────────────────────────────────────

    def test_get_maintenance_alerts_calls_api_method(self, service, api):
        api.get_analytics_maintenance_alerts.return_value = {"alerts": []}
        result = service.get_maintenance_alerts()
        assert result == {"alerts": []}
        api.get_analytics_maintenance_alerts.assert_called_once()

    # ── get_driver ─────────────────────────────────────────────────

    def test_get_driver_calls_api_method(self, service, api):
        api.get_analytics_driver.return_value = {"drivers": []}
        result = service.get_driver(from_date="2024-01", to_date="2024-12")
        assert result == {"drivers": []}
        api.get_analytics_driver.assert_called_once_with(
            from_date="2024-01", to_date="2024-12",
        )

    # ── get_document ───────────────────────────────────────────────

    def test_get_document_calls_api_method(self, service, api):
        api.get_analytics_document.return_value = {"docs": 42}
        result = service.get_document()
        assert result == {"docs": 42}
        api.get_analytics_document.assert_called_once()

    # ── get_monthly_financial ──────────────────────────────────────

    def test_get_monthly_financial_calls_api_method(self, service, api):
        api.get_analytics_financial_monthly.return_value = {}
        service.get_monthly_financial(months=12)
        api.get_analytics_financial_monthly.assert_called_once_with(
            months=12, from_date="", to_date="",
        )

    # ── get_client_growth ──────────────────────────────────────────

    def test_get_client_growth_calls_api_method(self, service, api):
        api.get_analytics_client_growth.return_value = {"growth": []}
        result = service.get_client_growth(months=6)
        assert result == {"growth": []}
        api.get_analytics_client_growth.assert_called_once_with(
            months=6, from_date="", to_date="",
        )

    # ── get_truck_utilization ──────────────────────────────────────

    def test_get_truck_utilization_calls_correct_endpoint(self, service, api):
        api.get_analytics_fleet_utilization.return_value = {"utilization": 0.75}
        result = service.get_truck_utilization()
        assert result == {"utilization": 0.75}
        api.get_analytics_fleet_utilization.assert_called_once()

    def test_get_truck_utilization_not_calling_age_endpoint(self, service, api):
        """Verify get_truck_utilization does NOT call the age-distribution endpoint."""
        api.get_analytics_fleet_utilization.return_value = {}
        service.get_truck_utilization()
        api.get_analytics_fleet_utilization.assert_called_once()
        api._get.assert_not_called()

    # ── get_document_upload_trend ──────────────────────────────────

    def test_get_document_upload_trend_calls_api_method(self, service, api):
        api.get_analytics_document_upload_trend.return_value = {}
        service.get_document_upload_trend(months=6)
        api.get_analytics_document_upload_trend.assert_called_once_with(months=6)

    # ── get_driver_tacho_violations ────────────────────────────────

    def test_get_driver_tacho_violations_calls_api_method(self, service, api):
        api.get_analytics_driver_violations.return_value = {}
        result = service.get_driver_tacho_violations()
        api.get_analytics_driver_violations.assert_called_once()

    # ── get_profit_per_km_by_country ───────────────────────────────

    def test_get_profit_per_km_by_country_calls_api_method(self, service, api):
        api.get_analytics_route_by_country.return_value = {}
        result = service.get_profit_per_km_by_country()
        api.get_analytics_route_by_country.assert_called_once()

    # ── get_revenue_concentration ──────────────────────────────────

    def test_get_revenue_concentration_calls_api_method(self, service, api):
        api.get_analytics_client_concentration.return_value = {}
        result = service.get_revenue_concentration()
        api.get_analytics_client_concentration.assert_called_once()

    # ── get_driver_profit_per_km ──────────────────────────────────

    def test_get_driver_profit_per_km_calls_api_method(self, service, api):
        api.get_analytics_driver_profit_per_km.return_value = {}
        result = service.get_driver_profit_per_km()
        api.get_analytics_driver_profit_per_km.assert_called_once()

    # ── get_trip_status_distribution ──────────────────────────────

    def test_get_trip_status_distribution_calls_api_method(self, service, api):
        api.get_analytics_financial_trip_status.return_value = {}
        result = service.get_trip_status_distribution(
            from_date="2024-01", to_date="2024-12",
        )
        api.get_analytics_financial_trip_status.assert_called_once_with(
            from_date="2024-01", to_date="2024-12",
        )

    # ── get_cost_breakdown ─────────────────────────────────────────

    def test_get_cost_breakdown_calls_api_method(self, service, api):
        api.get_analytics_financial_cost_breakdown.return_value = {}
        service.get_cost_breakdown(months=6)
        api.get_analytics_financial_cost_breakdown.assert_called_once_with(
            months=6, from_date="", to_date="",
        )

    # ── get_monthly_trip_volume ────────────────────────────────────

    def test_get_monthly_trip_volume_calls_api_method(self, service, api):
        api.get_analytics_financial_trip_volume.return_value = {}
        service.get_monthly_trip_volume(months=3)
        api.get_analytics_financial_trip_volume.assert_called_once_with(
            months=3, from_date="", to_date="",
        )

    # ── get_profit_vs_distance ─────────────────────────────────────

    def test_get_profit_vs_distance_calls_api_method(self, service, api):
        api.get_analytics_route_profit_vs_distance.return_value = {}
        service.get_profit_vs_distance(limit=50)
        api.get_analytics_route_profit_vs_distance.assert_called_once_with(limit=50)

    # ── get_truck_age_distribution ─────────────────────────────────

    def test_get_truck_age_distribution_calls_correct_endpoint(self, service, api):
        api._get.return_value = {"distribution": []}
        result = service.get_truck_age_distribution()
        assert result == {"distribution": []}
        api._get.assert_called_once_with("/api/v1/analytics/fleet/utilization")

    def test_get_truck_age_distribution_not_utilization_endpoint(self, service, api):
        """Verify age distribution calls the utilization endpoint."""
        api._get.return_value = {}
        service.get_truck_age_distribution()
        api._get.assert_called_once_with("/api/v1/analytics/fleet/utilization")

    # ── get_driver_efficiency_trend ──────────────────────────────

    def test_get_driver_efficiency_trend_calls_api_method(self, service, api):
        api.get_analytics_driver_monthly_activity.return_value = {}
        service.get_driver_efficiency_trend(months=6)
        api.get_analytics_driver_monthly_activity.assert_called_once_with(months=6)

    # ── get_client_retention ─────────────────────────────────────

    def test_get_client_retention_calls_api_method(self, service, api):
        api.get_analytics_client_retention.return_value = {}
        result = service.get_client_retention()
        api.get_analytics_client_retention.assert_called_once()

    # ── get_revenue_quarterly ────────────────────────────────────

    def test_get_revenue_quarterly_calls_api_method(self, service, api):
        api.get_analytics_financial_quarterly.return_value = {}
        service.get_revenue_quarterly(quarters=4)
        api.get_analytics_financial_quarterly.assert_called_once_with(
            quarters=4, from_date="", to_date="",
        )

    # ── get_invoice_aging ────────────────────────────────────────

    def test_get_invoice_aging_calls_api_method(self, service, api):
        api.get_analytics_financial_invoice_aging.return_value = {}
        result = service.get_invoice_aging()
        api.get_analytics_financial_invoice_aging.assert_called_once()

    # ── get_client_payment_timeline ──────────────────────────────

    def test_get_client_payment_timeline_calls_correct_endpoint(self, service, api):
        api.get_analytics_revenue_by_client.return_value = {"timeline": []}
        result = service.get_client_payment_timeline(
            from_date="2024-01-01", to_date="2024-12-31",
        )
        assert result == {"timeline": []}
        api.get_analytics_revenue_by_client.assert_called_once_with(
            from_date="2024-01-01", to_date="2024-12-31",
        )

    def test_get_client_payment_timeline_omits_empty_dates(self, service, api):
        api.get_analytics_revenue_by_client.return_value = {}
        service.get_client_payment_timeline()
        api.get_analytics_revenue_by_client.assert_called_once_with(
            from_date="", to_date="",
        )

    # ── get_driver_monthly_activity ──────────────────────────────

    def test_get_driver_monthly_activity_calls_api_method(self, service, api):
        api.get_analytics_driver_monthly_activity.return_value = {}
        service.get_driver_monthly_activity(months=3)
        api.get_analytics_driver_monthly_activity.assert_called_once_with(
            months=3, from_date="", to_date="",
        )

    # ── get_driver_comparison ──────────────────────────────────

    def test_get_driver_comparison_calls_api_method(self, service, api):
        api.get_analytics_driver_comparison.return_value = {}
        service.get_driver_comparison(from_date="2024-01", to_date="2024-12")
        api.get_analytics_driver_comparison.assert_called_once_with(
            from_date="2024-01", to_date="2024-12",
        )

    # ── invalidate ───────────────────────────────────────────────

    def test_invalidate_calls_api_method(self, service, api):
        api.invalidate_analytics_cache.return_value = {}
        service.invalidate()
        api.invalidate_analytics_cache.assert_called_once()

    # ── Error handling (API returning 500) ────────────────────────

    def test_get_data_raises_on_500_via_api_get(self, service, api):
        """When get_analytics_overview raises, the service method propagates the exception."""
        api.get_analytics_overview.side_effect = RuntimeError("500 Internal Server Error")
        with pytest.raises(RuntimeError, match="500"):
            service.get_data(from_date="2024-01", to_date="2024-12")

    def test_get_truck_utilization_raises_on_500(self, service, api):
        api.get_analytics_fleet_utilization.side_effect = \
            RuntimeError("500 Internal Server Error")
        with pytest.raises(RuntimeError, match="500"):
            service.get_truck_utilization()

    def test_get_truck_age_distribution_raises_on_500(self, service, api):
        api._get.side_effect = RuntimeError("500 Internal Server Error")
        with pytest.raises(RuntimeError, match="500"):
            service.get_truck_age_distribution()

    def test_get_revenue_by_client_raises_on_500(self, service, api):
        api.get_analytics_revenue_by_client.side_effect = \
            RuntimeError("500 Internal Server Error")
        with pytest.raises(RuntimeError, match="500"):
            service.get_revenue_by_client()

    def test_get_client_payment_timeline_raises_on_500(self, service, api):
        api.get_analytics_revenue_by_client.side_effect = RuntimeError("500 Internal Server Error")
        with pytest.raises(RuntimeError, match="500"):
            service.get_client_payment_timeline()

    def test_get_financial_raises_on_500(self, service, api):
        api.get_analytics_financial.side_effect = \
            RuntimeError("500 Internal Server Error")
        with pytest.raises(RuntimeError, match="500"):
            service.get_financial()


# ── RemoteTachoService ──────────────────────────────────────────────

class TestRemoteTachoService:
    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteTachoService(api)

    # ── get_import_history ─────────────────────────────────────────

    def test_get_import_history_calls_correct_endpoint(self, service, api):
        api.get_tacho_import_history.return_value = {
            "items": [{"id": 1, "file": "driver1.ddd"}],
        }
        result = service.get_import_history(limit=20)
        assert result == [{"id": 1, "file": "driver1.ddd"}]
        api.get_tacho_import_history.assert_called_once_with(limit=20)

    def test_get_import_history_respects_limit_default(self, service, api):
        api.get_tacho_import_history.return_value = {"items": []}
        service.get_import_history()
        api.get_tacho_import_history.assert_called_once_with(limit=50)

    def test_get_import_history_returns_empty_when_no_items(self, service, api):
        api.get_tacho_import_history.return_value = {}
        result = service.get_import_history()
        assert result == []

    def test_get_import_history_returns_empty_when_none(self, service, api):
        api.get_tacho_import_history.return_value = None
        result = service.get_import_history()
        assert result == []

    # ── get_status ─────────────────────────────────────────────────

    def test_get_status_calls_correct_endpoint(self, service, api):
        api.get_tacho_status.return_value = {"status": "ok", "downloads_today": 3}
        result = service.get_status()
        assert result == {"status": "ok", "downloads_today": 3}
        api.get_tacho_status.assert_called_once()

    # ── import_ddd_file ────────────────────────────────────────────

    def test_import_ddd_file_uses_post_with_files(self, service, api, tmp_path):
        """Verify import_ddd_file calls _api._client.post() with
        the file opened in binary mode."""
        ddd_file = tmp_path / "driver1.ddd"
        ddd_file.write_bytes(b"\x00\x01\x02")
        api._base_url = ""
        api._client.post.return_value.json.return_value = {"success": True}

        result = service.import_ddd_file(str(ddd_file))

        assert result == {"success": True}
        api._client.post.assert_called_once()
        call_args, call_kwargs = api._client.post.call_args
        assert call_args[0] == "/api/v1/tacho/import"
        assert "files" in call_kwargs
        # Verify the file was opened for binary read
        files_dict = call_kwargs["files"]
        assert "file" in files_dict
        file_name, file_obj = files_dict["file"]
        assert file_name == "driver1.ddd"

    def test_import_ddd_file_not_using_client_post(self, service, api, tmp_path):
        """Verify import_ddd_file uses _api._client.post()."""
        ddd_file = tmp_path / "test.ddd"
        ddd_file.write_bytes(b"data")
        api._base_url = ""
        api._client.post.return_value.json.return_value = {}
        service.import_ddd_file(str(ddd_file))
        api._client.post.assert_called_once()

    def test_import_ddd_file_raises_when_file_missing(self, service, api):
        api._base_url = ""
        api._client.post.side_effect = FileNotFoundError("No such file")
        with pytest.raises(FileNotFoundError):
            service.import_ddd_file("/nonexistent/file.ddd")

    def test_import_ddd_file_raises_on_api_error(self, service, api, tmp_path):
        ddd_file = tmp_path / "error.ddd"
        ddd_file.write_bytes(b"data")
        api._base_url = ""
        api._client.post.side_effect = RuntimeError("API error")
        with pytest.raises(RuntimeError, match="API error"):
            service.import_ddd_file(str(ddd_file))


# ── RemoteMaintenanceService ────────────────────────────────────────

class TestRemoteMaintenanceService:
    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteMaintenanceService(api)

    # ── get_summary ────────────────────────────────────────────────

    def test_get_summary_calls_api_method(self, service, api):
        api.get_maintenance_summary.return_value = {"total_cost": 5000}
        result = service.get_summary()
        assert result == {"total_cost": 5000}
        api.get_maintenance_summary.assert_called_once()

    # ── get_cost_monthly ───────────────────────────────────────────

    def test_get_cost_monthly_calls_api_method(self, service, api):
        api.get_maintenance_cost_monthly.return_value = {"months": []}
        result = service.get_cost_monthly(date_from="2024-01")
        assert result == {"months": []}
        api.get_maintenance_cost_monthly.assert_called_once_with(date_from="2024-01")

    def test_get_cost_monthly_default_since(self, service, api):
        api.get_maintenance_cost_monthly.return_value = {}
        service.get_cost_monthly()
        api.get_maintenance_cost_monthly.assert_called_once_with(date_from="")

    # ── get_cost_by_truck_monthly ──────────────────────────────────

    def test_get_cost_by_truck_monthly_calls_api_method(self, service, api):
        api.get_maintenance_cost_by_truck_monthly.return_value = {"trucks": []}
        result = service.get_cost_by_truck_monthly(date_from="2024-06")
        assert result == {"trucks": []}
        api.get_maintenance_cost_by_truck_monthly.assert_called_once_with(
            date_from="2024-06",
        )

    def test_get_cost_by_truck_monthly_default_since(self, service, api):
        api.get_maintenance_cost_by_truck_monthly.return_value = {}
        service.get_cost_by_truck_monthly()
        api.get_maintenance_cost_by_truck_monthly.assert_called_once_with(date_from="")

    # ── get_truck_summary ──────────────────────────────────────────

    def test_get_truck_summary_calls_api_method(self, service, api):
        api.get_maintenance_truck_summary.return_value = {"trucks": []}
        result = service.get_truck_summary(date_from="2024-01")
        assert result == {"trucks": []}
        api.get_maintenance_truck_summary.assert_called_once_with(date_from="2024-01")

    def test_get_truck_summary_default_since(self, service, api):
        api.get_maintenance_truck_summary.return_value = {}
        service.get_truck_summary()
        api.get_maintenance_truck_summary.assert_called_once_with(date_from="")

    # ── get_top_categories ─────────────────────────────────────────

    def test_get_top_categories_calls_api_method(self, service, api):
        api.get_maintenance_top_categories.return_value = {"categories": []}
        result = service.get_top_categories(date_from="2024-01")
        assert result == {"categories": []}
        api.get_maintenance_top_categories.assert_called_once_with(date_from="2024-01")

    def test_get_top_categories_default_since(self, service, api):
        api.get_maintenance_top_categories.return_value = {}
        service.get_top_categories()
        api.get_maintenance_top_categories.assert_called_once_with(date_from="")

    # ── get_all ────────────────────────────────────────────────────

    def test_get_all_returns_items(self, service, api):
        api.list_trucks.return_value = {
            "items": [{"id": 1, "plate": "AB-123"}, {"id": 2, "plate": "CD-456"}],
        }
        result = service.get_all()
        assert result == [{"id": 1, "plate": "AB-123"}, {"id": 2, "plate": "CD-456"}]
        api.list_trucks.assert_called_once()

    def test_get_all_returns_empty_when_no_items(self, service, api):
        api.list_trucks.return_value = {}
        result = service.get_all()
        assert result == []
        api.list_trucks.assert_called_once()

    def test_get_all_returns_empty_when_none(self, service, api):
        api.list_trucks.return_value = None
        result = service.get_all()
        assert result == []
        api.list_trucks.assert_called_once()

    def test_get_all_returns_empty_on_exception(self, service, api):
        """Error handling: API failure returns empty list."""
        api.list_trucks.side_effect = RuntimeError("offline")
        result = service.get_all()
        assert result == []
        api.list_trucks.assert_called_once()

    def test_get_all_handles_500_gracefully(self, service, api):
        api.list_trucks.side_effect = RuntimeError("500 Server Error")
        result = service.get_all()
        assert result == []


# ── RemoteInvoiceService ────────────────────────────────────────────

class TestRemoteInvoiceService:
    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteInvoiceService(api)

    # ── generate ───────────────────────────────────────────────────

    def test_generate_returns_bytes(self, service, api):
        api.generate_invoice.return_value = b"%PDF-1.4 invoice content"
        result = service.generate(trip_data={"trip_id": 42}, mode="client")
        assert result == b"%PDF-1.4 invoice content"
        api.generate_invoice.assert_called_once_with(
            {"trip_id": 42}, mode="client",
        )

    def test_generate_default_mode(self, service, api):
        api.generate_invoice.return_value = b"PDF"
        result = service.generate(trip_data={"trip_id": 1})
        assert result == b"PDF"
        api.generate_invoice.assert_called_once_with(
            {"trip_id": 1}, mode="client",
        )

    def test_generate_with_different_mode(self, service, api):
        api.generate_invoice.return_value = b"XLSX"
        result = service.generate(trip_data={"trip_id": 7}, mode="company")
        assert result == b"XLSX"
        api.generate_invoice.assert_called_once_with(
            {"trip_id": 7}, mode="company",
        )

    # ── generate_and_record ─────────────────────────────────────────

    def test_generate_and_record_returns_bytes(self, service, api):
        api.generate_invoice.return_value = b"%PDF-1.4 recorded invoice"
        result = service.generate_and_record(
            trip_data={"trip_id": 99}, mode="client",
        )
        assert result == b"%PDF-1.4 recorded invoice"
        api.generate_invoice.assert_called_once_with(
            {"trip_id": 99}, mode="client",
        )

    def test_generate_and_record_default_mode(self, service, api):
        api.generate_invoice.return_value = b"PDF data"
        result = service.generate_and_record(trip_data={"trip_id": 1})
        assert result == b"PDF data"
        api.generate_invoice.assert_called_once_with(
            {"trip_id": 1}, mode="client",
        )

    # ── send_invoice_email ─────────────────────────────────────────

    def test_send_invoice_email_returns_true_when_sent(self, service, api):
        api.send_invoice_email.return_value = {"status": "sent"}
        result = service.send_invoice_email(
            trip_id=42, recipient="test@example.com",
        )
        assert result is True
        api.send_invoice_email.assert_called_once_with(
            invoice_id=42, recipient="test@example.com",
            trip_data={}, mode="client",
        )

    def test_send_invoice_email_returns_false_when_not_sent(self, service, api):
        api.send_invoice_email.return_value = {"status": "failed"}
        result = service.send_invoice_email(
            trip_id=42, recipient="test@example.com",
        )
        assert result is False

    def test_send_invoice_email_returns_false_on_exception(self, service, api):
        api.send_invoice_email.side_effect = RuntimeError("SMTP error")
        result = service.send_invoice_email(
            trip_id=1, recipient="fail@example.com",
        )
        assert result is False

    def test_send_invoice_email_passes_trip_data_and_mode(self, service, api):
        api.send_invoice_email.return_value = {"status": "sent"}
        service.send_invoice_email(
            trip_id=5, recipient="b@b.com",
            trip_data={"extra": "info"}, mode="company",
        )
        api.send_invoice_email.assert_called_once_with(
            invoice_id=5, recipient="b@b.com",
            trip_data={"extra": "info"}, mode="company",
        )


# ── RemoteDriverService ─────────────────────────────────────────────

class TestRemoteDriverService:
    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteDriverService(api)

    # ── get_all ────────────────────────────────────────────────────

    def test_get_all_returns_items(self, service, api):
        api.list_drivers.return_value = {
            "items": [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}],
        }
        result = service.get_all()
        assert result == [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]
        api.list_drivers.assert_called_once_with(limit=500, offset=0)

    def test_get_all_passes_limit_and_offset(self, service, api):
        api.list_drivers.return_value = {"items": []}
        service.get_all(limit=100, offset=50)
        api.list_drivers.assert_called_once_with(limit=100, offset=50)

    def test_get_all_returns_empty_when_no_items(self, service, api):
        api.list_drivers.return_value = {}
        result = service.get_all()
        assert result == []
        api.list_drivers.assert_called_once()

    def test_get_all_returns_empty_when_none(self, service, api):
        api.list_drivers.return_value = None
        result = service.get_all()
        assert result == []
        api.list_drivers.assert_called_once()

    # ── get_by_id ──────────────────────────────────────────────────

    def test_get_by_id_returns_driver(self, service, api):
        api.get_driver.return_value = {"id": 5, "name": "Alice"}
        result = service.get_by_id(5)
        assert result == {"id": 5, "name": "Alice"}
        api.get_driver.assert_called_once_with(5)

    def test_get_by_id_returns_none_on_exception(self, service, api):
        api.get_driver.side_effect = RuntimeError("not found")
        result = service.get_by_id(999)
        assert result is None
        api.get_driver.assert_called_once_with(999)

    def test_get_by_id_returns_none_on_500(self, service, api):
        api.get_driver.side_effect = RuntimeError("500 Server Error")
        result = service.get_by_id(1)
        assert result is None

    # ── create ─────────────────────────────────────────────────────

    def test_create_returns_id(self, service, api):
        api.create_driver.return_value = {"id": 42}
        result = service.create({"name": "Bob", "license": "B"})
        assert result == 42
        api.create_driver.assert_called_once_with({"name": "Bob", "license": "B"})

    def test_create_returns_zero_when_no_id(self, service, api):
        api.create_driver.return_value = {}
        result = service.create({"name": "Bob"})
        assert result == 0
        api.create_driver.assert_called_once()

    def test_create_returns_zero_on_exception(self, service, api):
        api.create_driver.side_effect = RuntimeError("failed")
        result = service.create({"name": "Bob"})
        assert result == 0
        api.create_driver.assert_called_once()

    # ── update ─────────────────────────────────────────────────────

    def test_update_calls_api_method(self, service, api):
        service.update(driver_id=1, data={"name": "Updated"})
        api.update_driver.assert_called_once_with(1, {"name": "Updated"})

    def test_update_does_not_return(self, service, api):
        api.update_driver.return_value = {"id": 1}
        result = service.update(driver_id=5, data={"name": "Test"})
        assert result is None  # method has no return

    # ── delete ─────────────────────────────────────────────────────

    def test_delete_calls_api_method(self, service, api):
        service.delete(driver_id=7)
        api.delete_driver.assert_called_once_with(7)

    def test_delete_does_not_return(self, service, api):
        result = service.delete(driver_id=3)
        assert result is None  # method has no return

    # ── assign_driver_to_truck ─────────────────────────────────────

    def test_assign_driver_to_truck_calls_api_method(self, service, api):
        api.assign_driver_to_truck.return_value = {"success": True}
        result = service.assign_driver_to_truck(driver_id=1, truck_id=5)
        assert result == {"success": True}
        api.assign_driver_to_truck.assert_called_once_with(1, 5)

    def test_assign_driver_to_truck_returns_dict(self, service, api):
        api.assign_driver_to_truck.return_value = {"assigned": True}
        result = service.assign_driver_to_truck(10, 20)
        assert isinstance(result, dict)
        assert result["assigned"] is True

    # ── unassign_driver ──────────────────────────────────────────

    def test_unassign_driver_returns_truck_id(self, service, api):
        api.unassign_driver.return_value = {"truck_id": 5}
        result = service.unassign_driver(driver_id=1)
        assert result == 5
        api.unassign_driver.assert_called_once_with(1)

    def test_unassign_driver_returns_none_no_truck_id(self, service, api):
        api.unassign_driver.return_value = {}
        result = service.unassign_driver(driver_id=1)
        assert result is None

    def test_unassign_driver_returns_none_on_exception(self, service, api):
        api.unassign_driver.side_effect = RuntimeError("failed")
        result = service.unassign_driver(driver_id=1)
        assert result is None

    # ── get_truck_plate_for_driver ────────────────────────────────

    def test_get_truck_plate_for_driver_returns_plate(self, service, api):
        api.get_driver_truck_plate.return_value = {"plate": "AB-123-CD"}
        result = service.get_truck_plate_for_driver(driver_id=1)
        assert result == "AB-123-CD"
        api.get_driver_truck_plate.assert_called_once_with(1)

    def test_get_truck_plate_for_driver_returns_empty_when_no_plate(self, service, api):
        api.get_driver_truck_plate.return_value = {}
        result = service.get_truck_plate_for_driver(driver_id=1)
        assert result == ""

    def test_get_truck_plate_for_driver_returns_empty_on_exception(self, service, api):
        api.get_driver_truck_plate.side_effect = RuntimeError("offline")
        result = service.get_truck_plate_for_driver(driver_id=1)
        assert result == ""

    # ── get_driver_name_for_truck ──────────────────────────────────

    def test_get_driver_name_for_truck_returns_name(self, service, api):
        api._get.return_value = {"name": "John Doe"}
        result = service.get_driver_name_for_truck(truck_id=10)
        assert result == "John Doe"
        api._get.assert_called_once_with("/api/v1/drivers/by-truck/10")

    def test_get_driver_name_for_truck_returns_empty_when_no_name(self, service, api):
        api._get.return_value = {}
        result = service.get_driver_name_for_truck(truck_id=10)
        assert result == ""

    def test_get_driver_name_for_truck_returns_empty_on_exception(self, service, api):
        api._get.side_effect = RuntimeError("offline")
        result = service.get_driver_name_for_truck(truck_id=10)
        assert result == ""

    # ── get_tacho_activity ─────────────────────────────────────────

    def test_get_tacho_activity_calls_api_method(self, service, api):
        api.get_driver_tacho_activity.return_value = {
            "items": [{"date": "2024-01-01", "activity": "driving"}],
        }
        result = service.get_tacho_activity(
            driver_id=1, from_date="2024-01-01", limit=50,
        )
        assert result == [{"date": "2024-01-01", "activity": "driving"}]
        api.get_driver_tacho_activity.assert_called_once_with(
            1, from_date="2024-01-01", limit=50,
        )

    def test_get_tacho_activity_returns_empty_when_no_items(self, service, api):
        api.get_driver_tacho_activity.return_value = {}
        result = service.get_tacho_activity(driver_id=1)
        assert result == []

    def test_get_tacho_activity_returns_empty_when_none(self, service, api):
        api.get_driver_tacho_activity.return_value = None
        result = service.get_tacho_activity(driver_id=1)
        assert result == []

    def test_get_tacho_activity_default_params(self, service, api):
        api.get_driver_tacho_activity.return_value = {"items": []}
        service.get_tacho_activity(driver_id=5)
        api.get_driver_tacho_activity.assert_called_once_with(
            5, from_date="", limit=100,
        )


# ── RemoteRouteHistoryService ───────────────────────────────────────

class TestRemoteRouteHistoryService:
    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteRouteHistoryService(api)

    # ── search_routes ─────────────────────────────────────────────

    def test_search_routes_calls_list_route_history(self, service, api):
        api.list_route_history.return_value = {
            "items": [
                {"id": 1, "name": "Berlin → Paris"},
                {"id": 2, "name": "London → Berlin"},
            ],
        }
        result = service.search_routes(search="Berlin")
        # Both items contain "Berlin" in their string representation
        assert len(result) == 2
        api.list_route_history.assert_called_once_with(limit=200)

    def test_search_routes_filters_by_search(self, service, api):
        api.list_route_history.return_value = {
            "items": [
                {"id": 1, "name": "Berlin → Paris"},
                {"id": 2, "name": "London → Rome"},
            ],
        }
        result = service.search_routes(search="Berlin")
        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_search_routes_returns_all_when_no_search(self, service, api):
        api.list_route_history.return_value = {
            "items": [
                {"id": 1, "name": "Route A"},
                {"id": 2, "name": "Route B"},
            ],
        }
        result = service.search_routes()
        assert len(result) == 2

    def test_search_routes_returns_empty_when_no_items(self, service, api):
        api.list_route_history.return_value = {}
        result = service.search_routes()
        assert result == []

    def test_search_routes_raises_when_response_is_none(self, service, api):
        """The real ``search_routes`` calls ``resp.get("items", [])`` on
        the API response, so a ``None`` response raises ``AttributeError``."""
        api.list_route_history.return_value = None
        with pytest.raises(AttributeError):
            service.search_routes()

    def test_search_routes_passes_limit_to_api(self, service, api):
        """search_routes hardcodes limit=200 to list_route_history."""
        api.list_route_history.return_value = {"items": []}
        service.search_routes()
        api.list_route_history.assert_called_once_with(limit=200)

    # ── load_route ────────────────────────────────────────────────

    def test_load_route_calls_api_method(self, service, api):
        api.get_route_history.return_value = {"id": 42, "name": "Test Route"}
        result = service.load_route(route_id=42)
        assert result == {"id": 42, "name": "Test Route"}
        api.get_route_history.assert_called_once_with(42)

    def test_load_route_returns_none_on_exception(self, service, api):
        api.get_route_history.side_effect = RuntimeError("not found")
        result = service.load_route(route_id=999)
        assert result is None
        api.get_route_history.assert_called_once_with(999)

    # ── get_statistics ──────────────────────────────────────────

    def test_get_statistics_calls_api_method(self, service, api):
        api.get_route_statistics.return_value = {"total_routes": 50, "total_km": 10000}
        result = service.get_statistics()
        assert result == {"total_routes": 50, "total_km": 10000}
        api.get_route_statistics.assert_called_once()

    def test_get_statistics_ignores_include_archived(self, service, api):
        """include_archived parameter is accepted but not sent to API."""
        api.get_route_statistics.return_value = {}
        service.get_statistics(include_archived=True)
        api.get_route_statistics.assert_called_once()

    # ── duplicate_route ─────────────────────────────────────────

    def test_duplicate_route_returns_new_id(self, service, api):
        api.duplicate_route.return_value = {"new_route_id": 100}
        result = service.duplicate_route(route_id=5)
        assert result == 100
        api.duplicate_route.assert_called_once_with(5)

    def test_duplicate_route_returns_none_no_id(self, service, api):
        api.duplicate_route.return_value = {}
        result = service.duplicate_route(route_id=5)
        assert result is None

    def test_duplicate_route_returns_none_on_exception(self, service, api):
        api.duplicate_route.side_effect = RuntimeError("failed")
        result = service.duplicate_route(route_id=5)
        assert result is None

    # ── archive_route ──────────────────────────────────────────

    def test_archive_route_returns_true(self, service, api):
        api.archive_route.return_value = {"success": True}
        result = service.archive_route(route_id=10)
        assert result is True
        api.archive_route.assert_called_once_with(10)

    def test_archive_route_returns_true_even_on_empty_response(self, service, api):
        api.archive_route.return_value = {}
        result = service.archive_route(route_id=10)
        assert result is True

    def test_archive_route_returns_false_on_exception(self, service, api):
        api.archive_route.side_effect = RuntimeError("failed")
        result = service.archive_route(route_id=10)
        assert result is False

    # ── delete_route ───────────────────────────────────────────

    def test_delete_route_returns_true(self, service, api):
        api.delete_route_history.return_value = {"success": True}
        result = service.delete_route(route_id=42)
        assert result is True
        api.delete_route_history.assert_called_once_with(42)

    def test_delete_route_returns_false_on_exception(self, service, api):
        api.delete_route_history.side_effect = RuntimeError("failed")
        result = service.delete_route(route_id=42)
        assert result is False

    # ── export_route ──────────────────────────────────────────

    def test_export_route_calls_api_method(self, service, api):
        api.export_route.return_value = {"data": "route export"}
        result = service.export_route(route_id=1, fmt="json")
        assert result == {"data": "route export"}
        api.export_route.assert_called_once_with(1, fmt="json")

    def test_export_route_default_format(self, service, api):
        api.export_route.return_value = {}
        service.export_route(route_id=1)
        api.export_route.assert_called_once_with(1, fmt="json")
