"""Tests for client.remote_services — RemoteFleetService, RemoteTripService, RemoteClientService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from client.remote_services import (
    RemoteClientService,
    RemoteFleetService,
    RemoteTripService,
)


# ── RemoteFleetService ─────────────────────────────────────────────────

class TestRemoteFleetService:
    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteFleetService(api)

    def test_get_trucks_returns_items(self, service, api):
        api.list_trucks.return_value = {"items": [{"id": 1, "plate": "AB-123"}]}
        result = service.get_trucks()
        assert result == [{"id": 1, "plate": "AB-123"}]
        api.list_trucks.assert_called_once()

    def test_get_trucks_returns_empty_when_no_items(self, service, api):
        api.list_trucks.return_value = {}
        result = service.get_trucks()
        assert result == []

    def test_get_trucks_returns_empty_when_none(self, service, api):
        api.list_trucks.return_value = None
        result = service.get_trucks()
        assert result == []

    def test_get_truck_returns_truck(self, service, api):
        api.get_truck.return_value = {"id": 1, "plate": "CD-456"}
        result = service.get_truck(1)
        assert result == {"id": 1, "plate": "CD-456"}
        api.get_truck.assert_called_with(1)

    def test_get_truck_returns_none_on_error(self, service, api):
        api.get_truck.side_effect = RuntimeError("offline")
        result = service.get_truck(1)
        assert result is None

    def test_add_truck_returns_id(self, service, api):
        api._post.return_value = {"id": 42}
        result = service.add_truck({"plate": "EF-789"})
        assert result == 42
        api._post.assert_called_once()

    def test_add_truck_returns_zero_on_error(self, service, api):
        api._post.side_effect = RuntimeError("offline")
        result = service.add_truck({"plate": "EF-789"})
        assert result == 0

    def test_add_truck_returns_zero_when_no_id(self, service, api):
        api._post.return_value = {}
        result = service.add_truck({"plate": "EF-789"})
        assert result == 0

    def test_update_truck_calls_put(self, service, api):
        service.update_truck(1, {"plate": "GH-012"})
        api._put.assert_called_with(
            "/api/v1/fleet/trucks/1", json_data={"plate": "GH-012"}
        )

    def test_delete_truck_calls_delete(self, service, api):
        service.delete_truck(5)
        api._delete.assert_called_with("/api/v1/fleet/trucks/5")


# ── RemoteTripService ──────────────────────────────────────────────────

class TestRemoteTripService:
    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteTripService(api)

    def test_get_filtered_returns_items(self, service, api):
        api.list_trips.return_value = {
            "items": [{"id": 1, "origin": "Berlin", "status": "active"}]
        }
        result = service.get_filtered(search="Berlin", status="active", limit=50)
        assert result == [{"id": 1, "origin": "Berlin", "status": "active"}]
        api.list_trips.assert_called_with(search="Berlin", status="active", limit=50)

    def test_get_filtered_returns_empty_when_no_items(self, service, api):
        api.list_trips.return_value = {}
        result = service.get_filtered()
        assert result == []

    def test_get_by_id_returns_trip(self, service, api):
        api.get_trip.return_value = {"id": 5, "origin": "Paris"}
        result = service.get_by_id(5)
        assert result == {"id": 5, "origin": "Paris"}
        api.get_trip.assert_called_with(5)

    def test_get_by_id_returns_none_on_error(self, service, api):
        api.get_trip.side_effect = RuntimeError("not found")
        result = service.get_by_id(999)
        assert result is None

    def test_get_all_calls_get_filtered_with_limit(self, service, api):
        api.list_trips.return_value = {"items": [{"id": 1}]}
        result = service.get_all(limit=500)
        assert len(result) == 1
        api.list_trips.assert_called_with(search="", status="", limit=500)

    def test_get_by_statuses_deduplicates(self, service, api):
        # Trip with id=1 appears in both "active" and "planning" responses
        api.list_trips.side_effect = [
            {"items": [{"id": 1, "status": "active"}, {"id": 2, "status": "active"}]},
            {"items": [{"id": 1, "status": "active"}, {"id": 3, "status": "planning"}]},
            {"items": [{"id": 4, "status": "completed"}]},
        ]
        result = service.get_by_statuses(["active", "planning", "completed"])
        # Should have 4 unique trips filtered by status_set
        ids = {t["id"] for t in result}
        assert ids == {1, 2, 3, 4}

    def test_get_by_statuses_filters_by_status_set(self, service, api):
        # A trip returned under wrong status should be excluded
        api.list_trips.side_effect = [
            {"items": [{"id": 1, "status": "active"}]},
            {"items": [{"id": 2, "status": "cancelled"}]},  # not in statuses list!
        ]
        result = service.get_by_statuses(["active"])
        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_get_by_statuses_empty_response(self, service, api):
        api.list_trips.return_value = {}
        result = service.get_by_statuses(["active"])
        assert result == []

    def test_get_by_statuses_passes_limit(self, service, api):
        """A caller-supplied limit is forwarded to each status API call."""
        api.list_trips.side_effect = [
            {"items": [{"id": 1, "status": "active"}]},
            {"items": [{"id": 2, "status": "planning"}]},
        ]
        result = service.get_by_statuses(["active", "planning"], limit=25)
        assert len(result) == 2
        api.list_trips.assert_any_call(search="", status="active", limit=25)
        api.list_trips.assert_any_call(search="", status="planning", limit=25)

    def test_get_by_statuses_default_limit_unchanged(self, service, api):
        """Without a limit, the previous per-status limit of 1000 is kept."""
        api.list_trips.side_effect = [
            {"items": [{"id": 1, "status": "active"}]},
        ]
        result = service.get_by_statuses(["active"])
        assert len(result) == 1
        api.list_trips.assert_called_with(search="", status="active", limit=1000)


# ── RemoteClientService ────────────────────────────────────────────────

class TestRemoteClientService:
    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteClientService(api)

    def test_get_all_returns_items(self, service, api):
        api.list_clients.return_value = {
            "items": [{"id": 1, "name": "Acme Corp"}]
        }
        result = service.get_all()
        assert result == [{"id": 1, "name": "Acme Corp"}]
        api.list_clients.assert_called_with(limit=1000, include_inactive=False)

    def test_get_all_returns_empty_when_no_items(self, service, api):
        api.list_clients.return_value = {}
        result = service.get_all()
        assert result == []

    def test_get_by_id_returns_client(self, service, api):
        api.get_client.return_value = {"id": 3, "name": "Beta Inc"}
        result = service.get_by_id(3)
        assert result == {"id": 3, "name": "Beta Inc"}
        api.get_client.assert_called_with(3)

    def test_get_by_id_returns_none_on_error(self, service, api):
        api.get_client.side_effect = RuntimeError("offline")
        result = service.get_by_id(999)
        assert result is None

    def test_search_returns_items(self, service, api):
        api.list_clients.return_value = {
            "items": [{"id": 1, "name": "Gamma LLC"}]
        }
        result = service.search("Gamma", limit=20)
        assert result == [{"id": 1, "name": "Gamma LLC"}]
        api.list_clients.assert_called_with(query="Gamma", limit=20)

    def test_search_advanced_passes_include_inactive(self, service, api):
        api.list_clients.return_value = {
            "items": [{"id": 1, "name": "Delta"}]
        }
        result = service.search_advanced("Delta", include_inactive=True, limit=200)
        assert result == [{"id": 1, "name": "Delta"}]
        api.list_clients.assert_called_with(
            query="Delta", limit=200, include_inactive=True,
        )

    def test_search_advanced_include_inactive_false_by_default(self, service, api):
        api.list_clients.return_value = {"items": []}
        service.search_advanced("Delta")
        api.list_clients.assert_called_with(
            query="Delta", limit=200, include_inactive=False,
        )

    def test_create_returns_id(self, service, api):
        api._post.return_value = {"id": 42}
        result = service.create("Epsilon Ltd", country="DE")
        assert result == 42
        api._post.assert_called_once()

    def test_create_returns_zero_on_error(self, service, api):
        api._post.side_effect = RuntimeError("failed")
        result = service.create("Epsilon Ltd")
        assert result == 0

    def test_update_calls_put(self, service, api):
        service.update(1, name="Updated Name", country="FR")
        api._put.assert_called_with(
            "/api/v1/clients/1", json_data={"name": "Updated Name", "country": "FR"}
        )

    def test_get_client_dashboard_returns_data(self, service, api):
        api._get.return_value = {"revenue": 50000, "trip_count": 12}
        result = service.get_client_dashboard(1)
        assert result == {"revenue": 50000, "trip_count": 12}
        api._get.assert_called_with("/api/v1/clients/1/dashboard")

    def test_get_client_dashboard_returns_empty_on_error(self, service, api):
        api._get.side_effect = RuntimeError("offline")
        result = service.get_client_dashboard(1)
        assert result == {}

    def test_get_all_with_revenue_enriches_clients(self, service, api):
        api.list_clients.return_value = {
            "items": [{"id": 1, "name": "Zeta"}, {"id": 2, "name": "Eta"}]
        }
        api._get.side_effect = [
            {"revenue": 100, "trip_count": 5},
            {"revenue": 200, "trip_count": 10},
        ]
        result = service.get_all_with_revenue()
        assert len(result) == 2
        assert result[0]["revenue"] == 100
        assert result[0]["trip_count"] == 5
        assert result[1]["revenue"] == 200
        assert result[1]["trip_count"] == 10

    def test_get_all_with_revenue_handles_dashboard_error(self, service, api):
        api.list_clients.return_value = {
            "items": [{"id": 1, "name": "Zeta"}]
        }
        api._get.side_effect = RuntimeError("dashboard offline")
        result = service.get_all_with_revenue()
        assert len(result) == 1
        # Dashboard returns {} on error, so .get("revenue", 0) yields 0
        assert result[0]["revenue"] == 0
        assert result[0]["trip_count"] == 0

    def test_get_all_with_revenue_reads_backend_dashboard_keys(self, service, api):
        """Backend dashboard exposes total_revenue/total_trips — wrapper falls back to them."""
        api.list_clients.return_value = {"items": [{"id": 1, "name": "Zeta"}]}
        api._get.return_value = {"total_revenue": 3000, "total_trips": 15}
        result = service.get_all_with_revenue()
        assert result[0]["revenue"] == 3000
        assert result[0]["trip_count"] == 15

    # ── get_client_trips ─────────────────────────────────────────────

    def test_get_client_trips_returns_items(self, service, api):
        api.get_client_trips.return_value = {
            "items": [{"id": 1, "start_date": "2026-01-01"}]
        }
        result = service.get_client_trips(1)
        assert result == [{"id": 1, "start_date": "2026-01-01"}]
        api.get_client_trips.assert_called_with(1, limit=100)

    def test_get_client_trips_respects_limit(self, service, api):
        api.get_client_trips.return_value = {"items": []}
        service.get_client_trips(1, limit=50)
        api.get_client_trips.assert_called_with(1, limit=50)

    def test_get_client_trips_returns_empty_when_none(self, service, api):
        api.get_client_trips.return_value = None
        result = service.get_client_trips(1)
        assert result == []

    # ── get_client_invoices ──────────────────────────────────────────

    def test_get_client_invoices_returns_items(self, service, api):
        api.get_client_invoices.return_value = {
            "items": [{"id": 1, "invoice_number": "INV-001"}]
        }
        result = service.get_client_invoices(1)
        assert result == [{"id": 1, "invoice_number": "INV-001"}]
        api.get_client_invoices.assert_called_with(1, limit=100)

    def test_get_client_invoices_returns_empty_when_none(self, service, api):
        api.get_client_invoices.return_value = None
        result = service.get_client_invoices(1)
        assert result == []

    # ── get_trip_count ───────────────────────────────────────────────

    def test_get_trip_count_returns_count(self, service, api):
        api.get_client_trip_count.return_value = {"count": 42}
        result = service.get_trip_count(1)
        assert result == 42
        api.get_client_trip_count.assert_called_with(1)

    def test_get_trip_count_returns_zero_when_missing(self, service, api):
        api.get_client_trip_count.return_value = {}
        result = service.get_trip_count(1)
        assert result == 0

    def test_get_trip_count_returns_zero_when_none(self, service, api):
        api.get_client_trip_count.return_value = None
        result = service.get_trip_count(1)
        assert result == 0

    # ── deactivate ───────────────────────────────────────────────────

    def test_deactivate_calls_api(self, service, api):
        api.deactivate_client.return_value = {"status": "deactivated"}
        result = service.deactivate(7)
        assert result is None
        api.deactivate_client.assert_called_with(7)

    # ── get_client_revenue_history ───────────────────────────────────

    def test_get_client_revenue_history_returns_list(self, service, api):
        api.get_client_revenue_history.return_value = [
            {"month": "2026-01", "revenue": 1000, "profit": 200},
        ]
        result = service.get_client_revenue_history(1, months=12)
        assert result == [{"month": "2026-01", "revenue": 1000, "profit": 200}]
        api.get_client_revenue_history.assert_called_with(1, months=12)

    def test_get_client_revenue_history_returns_empty_when_none(self, service, api):
        api.get_client_revenue_history.return_value = None
        result = service.get_client_revenue_history(1)
        assert result == []

    def test_get_client_revenue_history_returns_empty_dict_gracefully(self, service, api):
        api.get_client_revenue_history.return_value = {}
        result = service.get_client_revenue_history(1)
        assert result == []

    # ── merge_clients ────────────────────────────────────────────────

    def test_merge_clients_calls_api(self, service, api):
        api.merge_clients.return_value = {"trips": 3, "invoices": 2, "contacts": 1}
        result = service.merge_clients(1, 2)
        assert result == {"trips": 3, "invoices": 2, "contacts": 1}
        api.merge_clients.assert_called_with(1, 2)

    # ── create / update payload shape ─────────────────────────────────

    def test_create_sends_flat_payload(self, service, api):
        """Create posts flat fields (not a nested ``data`` dict)."""
        api._post.return_value = {"id": 42}
        result = service.create("Epsilon Ltd", country="DE", vat_number="RO1")
        assert result == 42
        api._post.assert_called_with(
            "/api/v1/clients/",
            json_data={"name": "Epsilon Ltd", "country": "DE", "vat_number": "RO1"},
        )

    def test_update_sends_flat_payload(self, service, api):
        """Update posts flat fields matching ClientUpdateRequest."""
        service.update(1, name="Updated Name", country="FR")
        api._put.assert_called_with(
            "/api/v1/clients/1", json_data={"name": "Updated Name", "country": "FR"}
        )

    # ── get_all / include_inactive passthrough ────────────────────────

    def test_get_all_passes_include_inactive_true(self, service, api):
        api.list_clients.return_value = {"items": []}
        service.get_all(include_inactive=True)
        api.list_clients.assert_called_with(limit=1000, include_inactive=True)

    def test_get_all_with_revenue_passes_include_inactive(self, service, api):
        api.list_clients.return_value = {"items": [{"id": 1, "name": "Zeta"}]}
        api._get.return_value = {"revenue": 100, "trip_count": 5}
        service.get_all_with_revenue(include_inactive=True)
        api.list_clients.assert_called_with(
            include_inactive=True, page=1, page_size=200,
        )

    def test_get_all_with_revenue_paginates(self, service, api):
        """Multi-page: fetch page 1 (200) then page 2 (<200) and merge."""
        api.list_clients.side_effect = [
            {"items": [{"id": i, "name": f"C{i}"} for i in range(1, 201)]},
            {"items": [{"id": 201, "name": "C201"}]},
        ]
        api._get.return_value = {"revenue": 100, "trip_count": 5}
        result = service.get_all_with_revenue()
        assert len(result) == 201
        assert api.list_clients.call_count == 2
        api.list_clients.assert_any_call(
            include_inactive=False, page=1, page_size=200,
        )
        api.list_clients.assert_any_call(
            include_inactive=False, page=2, page_size=200,
        )

    def test_get_all_with_revenue_dedupes_repeated_page(self, service, api):
        """A backend that re-returns the same full page must not duplicate."""
        api.list_clients.return_value = {
            "items": [{"id": i, "name": f"C{i}"} for i in range(1, 201)]
        }
        api._get.return_value = {"revenue": 0, "trip_count": 0}
        result = service.get_all_with_revenue()
        # Page 2 adds nothing (all ids already seen) → loop stops.
        assert api.list_clients.call_count == 2
        assert len(result) == 200
        ids = {c["id"] for c in result}
        assert len(ids) == 200

    # ── get_contacts ──────────────────────────────────────────────────

    def test_get_contacts_returns_items(self, service, api):
        api.get_client_contacts.return_value = {
            "items": [{"id": 1, "full_name": "Jane Smith"}]
        }
        result = service.get_contacts(1)
        assert result == [{"id": 1, "full_name": "Jane Smith"}]
        api.get_client_contacts.assert_called_with(1)

    def test_get_contacts_returns_empty_when_none(self, service, api):
        api.get_client_contacts.return_value = None
        result = service.get_contacts(1)
        assert result == []
        api.get_client_contacts.assert_called_with(1)

    # ── add_contact ───────────────────────────────────────────────────

    def test_add_contact_calls_api_with_kwargs(self, service, api):
        api.add_client_contact.return_value = {"id": 7}
        result = service.add_contact(1, full_name="Jane Smith", phone="+40123")
        assert result == 7
        api.add_client_contact.assert_called_with(
            1, {"full_name": "Jane Smith", "phone": "+40123"}
        )

    def test_add_contact_accepts_positional_data(self, service, api):
        api.add_client_contact.return_value = {"id": 8}
        result = service.add_contact(1, {"name": "Jane Smith"})
        assert result == 8
        api.add_client_contact.assert_called_with(1, {"name": "Jane Smith"})

    def test_add_contact_returns_zero_on_error(self, service, api):
        api.add_client_contact.side_effect = RuntimeError("offline")
        result = service.add_contact(1, full_name="Jane")
        assert result == 0

    def test_add_contact_returns_zero_when_no_id(self, service, api):
        api.add_client_contact.return_value = {}
        result = service.add_contact(1, full_name="Jane")
        assert result == 0

    # ── update_contact / delete_contact (remote delegation) ─────────────

    def test_update_contact_delegates_to_api(self, service, api):
        api.update_client_contact.return_value = {"status": "updated"}
        result = service.update_contact(5, full_name="Jane Smith", phone="+40123")
        assert result is None
        api.update_client_contact.assert_called_with(
            5, {"full_name": "Jane Smith", "phone": "+40123"}
        )

    def test_delete_contact_delegates_to_api(self, service, api):
        api.delete_client_contact.return_value = {"status": "deleted"}
        result = service.delete_contact(5)
        assert result is None
        api.delete_client_contact.assert_called_with(5)

    # ── add_tag ───────────────────────────────────────────────────────

    def test_add_tag_calls_api(self, service, api):
        api.add_client_tag.return_value = {"status": "tag_added"}
        result = service.add_tag(1, "vip")
        assert result is None
        api.add_client_tag.assert_called_with(1, "vip")

    # ── get_payment_summary ───────────────────────────────────────────

    def test_get_payment_summary_returns_dict(self, service, api):
        api.get_client_payment_summary.return_value = {
            "total_billed": 200000, "total_paid": 180000,
            "unpaid": 20000, "overdue": 5000, "invoice_count": 10,
        }
        result = service.get_payment_summary(1)
        assert result["invoice_count"] == 10
        assert result["total_billed"] == 200000
        api.get_client_payment_summary.assert_called_with(1)

    def test_get_payment_summary_returns_empty_when_none(self, service, api):
        api.get_client_payment_summary.return_value = None
        result = service.get_payment_summary(1)
        assert result == {}
