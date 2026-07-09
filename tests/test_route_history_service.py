"""Comprehensive tests for RouteHistoryService — CRUD, fingerprinting, events, lifecycle."""

from __future__ import annotations

import json
import zlib
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.route_history_service import (
    ROUTE_HISTORY_METADATA_VERSION,
    RouteHistoryListItem,
    RouteHistoryRecord,
    RouteHistoryService,
    RouteEventBus,
    _RECENT_ROUTE_CACHE,
    _RecentRouteCache,
)


@pytest.fixture(autouse=True)
def clear_route_cache():
    """Clear the module-level route cache between tests to avoid cross-test pollution."""
    _RECENT_ROUTE_CACHE._items.clear()
    _RECENT_ROUTE_CACHE._order.clear()


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service(mock_db):
    svc = RouteHistoryService(mock_db)
    # Replace repos with mocks for fast unit tests
    svc._route_repo = MagicMock()
    svc._event_repo = MagicMock()
    svc._assignment_repo = MagicMock()
    svc.retention_days = 9999  # disable pruning during tests by default
    return svc


@pytest.fixture
def sample_record() -> RouteHistoryRecord:
    return RouteHistoryRecord(
        stops=[{"lat": 48.8566, "lon": 2.3522, "address": "Paris"}, {"lat": 44.4268, "lon": 26.1025, "address": "Bucharest"}],
        geometry=[(48.85, 2.35), (44.43, 26.10)],
        total_distance_km=1870.0,
        duration_min=1200.0,
        truck_id="TRUCK-001",
        truck_label="Scania R500",
        truck={"id": "TRUCK-001", "plate": "B-123-XYZ"},
        profile="truck",
        excluded_countries=["UA", "MD"],
        countries_traversed=["FR", "DE", "AT", "HU", "RO"],
    )


# ── RouteHistoryRecord dataclass ────────────────────────────────────────

class TestRouteHistoryRecord:
    def test_default_values(self):
        r = RouteHistoryRecord(stops=[])
        assert r.stops == []
        assert r.geometry == []
        assert r.total_distance_km is None
        assert r.toll_estimates == {}
        assert r.metadata_version == ROUTE_HISTORY_METADATA_VERSION

    def test_with_full_data(self, sample_record):
        assert sample_record.total_distance_km == 1870.0
        assert sample_record.truck_id == "TRUCK-001"
        assert len(sample_record.excluded_countries) == 2


# ── CRUD operations ─────────────────────────────────────────────────────

class TestSaveRoute:
    def test_save_creates_new_record(self, service, sample_record):
        service._route_repo.upsert.return_value = None
        service._route_repo.get_id_by_fingerprint.return_value = 42
        with patch.object(service, "prune_old_routes") as mock_prune:
            route_id = service.save_route(sample_record)
        assert route_id == 42
        service._route_repo.upsert.assert_called_once()
        args, _ = service._route_repo.upsert.call_args
        data, fingerprint = args
        assert data["route_fingerprint"] == fingerprint
        assert data["total_distance_km"] == 1870.0
        assert data["truck_id"] == "TRUCK-001"
        assert data["profile"] == "truck"
        mock_prune.assert_called_once()

    def test_save_raises_if_no_id_after_upsert(self, service, sample_record):
        service._route_repo.upsert.return_value = None
        service._route_repo.get_id_by_fingerprint.return_value = None
        with pytest.raises(RuntimeError, match="Upsert failed"):
            service.save_route(sample_record)

    def test_save_duplicate_updates_existing(self, service, sample_record):
        """Same fingerprint should reuse the same row (dedup via upsert)."""
        service._route_repo.upsert.return_value = None
        service._route_repo.get_id_by_fingerprint.return_value = 42
        with patch.object(service, "prune_old_routes"):
            id1 = service.save_route(sample_record)
            id2 = service.save_route(sample_record)
        assert id1 == id2 == 42
        assert service._route_repo.upsert.call_count == 2

    def test_save_normalizes_excluded_countries(self, service):
        """Country codes should be uppercased and deduplicated."""
        record = RouteHistoryRecord(
            stops=[{"lat": 48.85, "lon": 2.35}],
            excluded_countries=["ro", "RO", "md"],
        )
        service._route_repo.upsert.return_value = None
        service._route_repo.get_id_by_fingerprint.return_value = 1
        with patch.object(service, "prune_old_routes"):
            service.save_route(record)
        call_data = service._route_repo.upsert.call_args[0][0]
        stored = json.loads(call_data["excluded_countries_json"])
        assert stored == ["MD", "RO"]


class TestLoadRoute:
    def test_load_returns_record(self, service):
        row = {
            "stops_json": json.dumps([{"lat": 48.85, "lon": 2.35}]),
            "geometry_compressed": zlib.compress(json.dumps([(48.85, 2.35)]).encode()),
            "total_distance_km": 100.0,
            "duration_min": 60.0,
            "truck_id": "T1",
            "truck_label": "Truck 1",
            "truck_json": json.dumps({"id": "T1"}),
            "profile": "truck",
            "excluded_countries_json": "[]",
            "countries_traversed_json": "[]",
            "metadata_version": 1,
        }
        service._route_repo.get_by_id.return_value = row
        record = service.load_route(1)
        assert record is not None
        assert record.total_distance_km == 100.0
        assert record.truck_id == "T1"

    def test_load_not_found(self, service):
        service._route_repo.get_by_id.return_value = None
        assert service.load_route(999) is None

    def test_load_uses_cache(self, service):
        row = {
            "stops_json": "[]",
            "geometry_compressed": zlib.compress(b"[]"),
            "total_distance_km": 50.0,
            "duration_min": 30.0,
            "truck_id": None,
            "truck_label": None,
            "truck_json": "{}",
            "profile": "car",
            "excluded_countries_json": "[]",
            "countries_traversed_json": "[]",
            "metadata_version": 1,
        }
        service._route_repo.get_by_id.return_value = row
        record1 = service.load_route(1)
        record2 = service.load_route(1)
        assert record1 is record2  # same cached object
        service._route_repo.get_by_id.assert_called_once()  # second call cached


class TestListRoutes:
    def test_list_returns_list_items(self, service):
        row = {
            "id": 1,
            "route_fingerprint": "abc123",
            "created_at": "2025-01-01T00:00:00Z",
            "last_calculated_at": "2025-01-02T00:00:00Z",
            "calculation_count": 1,
            "total_distance_km": 100.0,
            "duration_min": 60.0,
            "truck_id": "T1",
            "truck_label": "Truck 1",
            "profile": "truck",
            "stops_json": json.dumps([{"lat": 48.85, "lon": 2.35, "address": "Paris"}, {"lat": 44.43, "lon": 26.10, "address": "Bucharest"}]),
            "excluded_countries_json": "[]",
            "countries_traversed_json": '["FR", "RO"]',
            "metadata_version": 1,
            "archived_at": None,
        }
        service._route_repo.search.return_value = [row]
        items = service.list_routes(limit=10, offset=0)
        assert len(items) == 1
        assert items[0].id == 1
        assert items[0].origin == "Paris"
        assert items[0].destination == "Bucharest"

    def test_list_pagination_delegation(self, service):
        service._route_repo.search.return_value = []
        items = service.list_routes(limit=5, offset=10)
        service._route_repo.search.assert_called_once_with(
            search="", truck="", profile="", include_archived=False,
            sort_by="last_calculated_at", sort_dir="DESC", limit=5, offset=10,
        )
        assert items == []


class TestCountRoutes:
    def test_count_routes(self, service):
        service._route_repo.count_filtered.return_value = 7
        result = service.count_routes(search="Paris")
        assert result == 7
        service._route_repo.count_filtered.assert_called_once_with(
            search="Paris", truck="", profile="", include_archived=False,
        )


class TestDeleteRoute:
    def test_delete_delegates(self, service):
        result = service.delete_route(42)
        assert result is True
        service._route_repo.delete.assert_called_with(42)


# ── Route lifecycle (commit / discard / archive / complete) ─────────────

class TestRouteLifecycle:
    def test_commit_route(self, service):
        result = service.commit_route(1)
        assert result is True
        service._route_repo.commit.assert_called_with(1)
        service._event_repo.create.assert_called_once()

    def test_discard_route(self, service):
        result = service.discard_route(1)
        assert result is True
        service._route_repo.discard.assert_called_with(1)
        service._event_repo.create.assert_called_once()

    def test_archive_route(self, service):
        result = service.archive_route(1)
        assert result is True
        service._route_repo.archive.assert_called_once()
        args = service._route_repo.archive.call_args[0]
        assert args[0] == 1

    def test_complete_route(self, service):
        service._assignment_repo.complete.return_value = True
        result = service.complete_route(1)
        assert result is True
        service._assignment_repo.complete.assert_called_once()


# ── Active route management ─────────────────────────────────────────────

class TestActiveRoute:
    def test_set_active_route(self, service, mock_db):
        with patch("services.route_history_service.SettingsRepository") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings_cls.return_value = mock_settings
            service.set_active_route(5)
            mock_settings.upsert_setting.assert_called_with(
                "current_active_route_id", "5",
            )
        service._event_repo.create.assert_called_once()

    def test_get_active_route_id(self, service):
        with patch("services.route_history_service.SettingsRepository") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.get_setting_value.return_value = "42"
            mock_settings_cls.return_value = mock_settings
            result = service.get_active_route_id()
            assert result == 42

    def test_get_active_route_id_none(self, service):
        with patch("services.route_history_service.SettingsRepository") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.get_setting_value.return_value = None
            mock_settings_cls.return_value = mock_settings
            result = service.get_active_route_id()
            assert result is None

    def test_get_active_route_delegates(self, service):
        with patch.object(service, "get_active_route_id", return_value=5), \
             patch.object(service, "load_route") as mock_load:
            mock_load.return_value = MagicMock()
            result = service.get_active_route()
            assert result is mock_load.return_value
            mock_load.assert_called_with(5)


# ── Truck assignment ────────────────────────────────────────────────────

class TestTruckAssignment:
    def test_assign_route_to_truck(self, service):
        service._assignment_repo.assign.return_value = 99
        result = service.assign_route_to_truck(1, "TRUCK-001")
        assert result == 99
        service._assignment_repo.assign.assert_called_once()
        service._event_repo.create.assert_called_once()

    def test_assign_with_active_status(self, service):
        service._assignment_repo.assign.return_value = 99
        with patch.object(service, "set_active_route") as mock_set:
            service.assign_route_to_truck(1, "TRUCK-001", status="active")
            mock_set.assert_called_with(1)

    def test_get_truck_routes(self, service):
        service._assignment_repo.get_by_truck.return_value = [{"id": 1}]
        result = service.get_truck_routes("TRUCK-001", status="active")
        assert result == [{"id": 1}]
        service._assignment_repo.get_by_truck.assert_called_with("TRUCK-001", status="active")


# ── Events ──────────────────────────────────────────────────────────────

class TestRecordEvent:
    def test_record_event_persists_and_publishes(self, service):
        service._event_repo.create.return_value = 1
        event_id = service.record_event(5, "test_event", {"key": "val"})
        assert event_id == 1
        service._event_repo.create.assert_called_once()

    def test_record_event_without_payload(self, service):
        service._event_repo.create.return_value = 2
        event_id = service.record_event(5, "simple_event")
        assert event_id == 2


# ── Duplication ─────────────────────────────────────────────────────────

class TestDuplicateRoute:
    def test_duplicate_returns_new_id(self, service):
        row = {
            "stops_json": "[]",
            "geometry_compressed": zlib.compress(b"[]"),
            "total_distance_km": 100.0,
            "duration_min": 60.0,
            "truck_id": None,
            "truck_label": None,
            "truck_json": "{}",
            "profile": "truck",
            "excluded_countries_json": "[]",
            "countries_traversed_json": "[]",
            "metadata_version": 1,
        }
        service._route_repo.get_by_id.return_value = row
        service._route_repo.create.return_value = 99
        new_id = service.duplicate_route(1)
        assert new_id == 99

    def test_duplicate_not_found(self, service):
        service._route_repo.get_by_id.return_value = None
        result = service.duplicate_route(999)
        assert result is None


# ── Fingerprinting ──────────────────────────────────────────────────────

class TestFingerprinting:
    def test_build_fingerprint_stable(self, service, sample_record):
        fp1 = service.build_fingerprint(sample_record)
        fp2 = service.build_fingerprint(sample_record)
        assert fp1 == fp2

    def test_build_fingerprint_changes_with_profile(self, service, sample_record):
        fp_original = service.build_fingerprint(sample_record)
        sample_record.profile = "car"
        fp_car = service.build_fingerprint(sample_record)
        assert fp_original != fp_car

    def test_fingerprint_normalizes_countries(self, service):
        """Country code casing should not affect the fingerprint."""
        r1 = RouteHistoryRecord(stops=[{"lat": 48.85, "lon": 2.35}], excluded_countries=["ro", "MD"])
        r2 = RouteHistoryRecord(stops=[{"lat": 48.85, "lon": 2.35}], excluded_countries=["RO", "md"])
        fp1 = service.build_fingerprint(r1)
        fp2 = service.build_fingerprint(r2)
        assert fp1 == fp2

    def test_fingerprint_stops_rounding(self, service):
        """Lat/lon should be rounded to 5 decimal places for fingerprinting."""
        # Both round to 48.85660, 2.35220 at 5 decimal places
        r1 = RouteHistoryRecord(stops=[{"lat": 48.856600, "lon": 2.352200}])
        r2 = RouteHistoryRecord(stops=[{"lat": 48.856604, "lon": 2.352204}])
        fp1 = service.build_fingerprint(r1)
        fp2 = service.build_fingerprint(r2)
        assert fp1 == fp2


# ── Retention / Pruning / Cleanup ───────────────────────────────────────

class TestRetention:
    def test_prune_old_routes(self, service):
        service._route_repo.prune_before.return_value = 3
        result = service.prune_old_routes()
        assert result == 3

    def test_prune_disabled_when_days_zero(self, service):
        service.retention_days = 0
        result = service.prune_old_routes()
        assert result == 0
        service._route_repo.prune_before.assert_not_called()

    def test_run_cleanup(self, service):
        service._route_repo.prune_before.return_value = 2
        service._event_repo.delete_orphans.return_value = 1
        result = service.run_cleanup()
        assert result == {"pruned_routes": 2, "orphan_events": 1}

    def test_set_and_get_retention_days(self, service):
        with patch("services.route_history_service.SettingsRepository") as mock_cls:
            mock_repo = MagicMock()
            mock_cls.return_value = mock_repo
            service.set_retention_days(30)
            mock_repo.upsert_setting.assert_called_with("route_history_retention_days", "30")
            assert service.retention_days == 30
            # get_retention_days should return the local value first
            assert service.get_retention_days() == 30


# ── Statistics / Analytics ──────────────────────────────────────────────

class TestStatistics:
    def test_get_statistics(self, service):
        service._route_repo.get_statistics_aggregate.return_value = {"route_count": 2, "total_distance": 150.0}
        service._route_repo.get_stops_for_statistics.return_value = [
            {"stops_json": json.dumps([{"lat": 48.85, "lon": 2.35, "address": "Paris"}, {"lat": 44.43, "lon": 26.10, "address": "Bucharest"}])},
            {"stops_json": json.dumps([{"lat": 51.50, "lon": -0.13, "address": "London"}])},
        ]
        stats = service.get_statistics()
        assert stats["route_count"] == 2
        assert stats["total_distance_km"] == 150.0

    def test_get_route_analytics(self, service):
        service._route_repo.get_countries_and_durations.return_value = [
            {"countries_traversed_json": json.dumps(["FR", "DE"]), "duration_min": 120.0},
            {"countries_traversed_json": json.dumps(["FR", "BE"]), "duration_min": 60.0},
        ]
        analytics = service.get_route_analytics()
        assert analytics["average_trip_duration_min"] == 90.0
        assert analytics["country_frequency"]["FR"] == 2


# ── Export ──────────────────────────────────────────────────────────────

class TestExport:
    def test_export_json(self, service, sample_record):
        with patch.object(service, "load_route", return_value=sample_record):
            payload = service.export_route(1, fmt="json")
        assert payload is not None
        assert payload["metadata"]["route_id"] == 1
        assert payload["route"]["origin"] == "Paris"
        assert payload["route"]["destination"] == "Bucharest"

    def test_export_not_found(self, service):
        with patch.object(service, "load_route", return_value=None):
            result = service.export_route(999)
        assert result is None

    def test_export_unsupported_format(self, service, sample_record):
        with patch.object(service, "load_route", return_value=sample_record):
            with pytest.raises(ValueError, match="Unsupported export format"):
                service.export_route(1, fmt="xml")


# ── _RecentRouteCache ───────────────────────────────────────────────────

class TestRecentRouteCache:
    def test_get_missing(self):
        cache = _RecentRouteCache(max_size=3)
        assert cache.get(1) is None

    def test_put_and_get(self):
        cache = _RecentRouteCache(max_size=3)
        record = RouteHistoryRecord(stops=[])
        cache.put(1, record)
        assert cache.get(1) is record

    def test_eviction(self):
        cache = _RecentRouteCache(max_size=2)
        cache.put(1, RouteHistoryRecord(stops=[]))
        cache.put(2, RouteHistoryRecord(stops=[]))
        cache.put(3, RouteHistoryRecord(stops=[]))
        assert cache.get(1) is None
        assert cache.get(3) is not None

    def test_reorder_on_get(self):
        cache = _RecentRouteCache(max_size=2)
        r1 = RouteHistoryRecord(stops=[])
        r2 = RouteHistoryRecord(stops=[])
        cache.put(1, r1)
        cache.put(2, r2)
        cache.get(1)  # access 1, making 2 the LRU
        cache.put(3, RouteHistoryRecord(stops=[]))
        assert cache.get(2) is None  # 2 was evicted
        assert cache.get(1) is r1  # 1 still present


# ── RouteEventBus ───────────────────────────────────────────────────────

class TestRouteEventBus:
    def test_subscribe_and_publish(self):
        events = []
        RouteEventBus._listeners = {}
        RouteEventBus.subscribe("route_committed", lambda t, p: events.append((t, p)))
        RouteEventBus.publish("route_committed", {"id": 1})
        assert len(events) == 1

    def test_unsubscribe(self):
        events = []
        cb = lambda t, p: events.append((t, p))
        RouteEventBus._listeners = {}
        RouteEventBus.subscribe("test", cb)
        RouteEventBus.publish("test", {"v": 1})
        assert len(events) == 1
        RouteEventBus.unsubscribe("test", cb)
        RouteEventBus.publish("test", {"v": 2})
        assert len(events) == 1  # no new event

    def test_wildcard_subscriber(self):
        events = []
        RouteEventBus._listeners = {}
        RouteEventBus.subscribe("*", lambda t, p: events.append((t, p)))
        RouteEventBus.publish("any_event", {"k": "v"})
        assert len(events) == 1

    def test_publish_does_not_raise_on_callback_failure(self):
        RouteEventBus._listeners = {}
        RouteEventBus.subscribe("fails", lambda t, p: (_ for _ in ()).throw(Exception("boom")))
        RouteEventBus.publish("fails", {})  # should not raise
