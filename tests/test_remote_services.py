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
        api.list_clients.assert_called_with(limit=1000)

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

    def test_search_advanced_delegates_to_search(self, service, api):
        api.list_clients.return_value = {
            "items": [{"id": 1, "name": "Delta"}]
        }
        result = service.search_advanced("Delta", include_inactive=True, limit=200)
        assert result == [{"id": 1, "name": "Delta"}]
        api.list_clients.assert_called_with(query="Delta", limit=200)

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
