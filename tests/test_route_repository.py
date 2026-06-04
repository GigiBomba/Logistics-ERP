"""Integration tests for RouteRepository: CRUD, upsert, search, edge cases."""
import unittest
from datetime import datetime

from tests.test_helpers import make_db
from repositories.route_repository import RouteRepository


def _route_data(**overrides):
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    data = {
        "route_fingerprint": "fp-unique-001",
        "metadata_version": 1,
        "created_at": now,
        "last_calculated_at": now,
        "calculation_count": 1,
        "stops_json": '[{"type":"start","address":"Bucharest"},{"type":"destination","address":"Paris"}]',
        "geometry_compressed": b"",
        "geometry_encoding": "zlib-json",
        "total_distance_km": 2300.0,
        "duration_min": 1800.0,
        "truck_id": "1",
        "truck_label": "B-100-XYZ",
        "truck_json": '{"id":1,"plate_number":"B-100-XYZ"}',
        "profile": "truck",
        "excluded_countries_json": "[]",
        "toll_estimates_json": "{}",
        "fuel_estimates_json": "{}",
        "profit_estimates_json": "{}",
        "countries_traversed_json": "[]",
        "route_summary_json": '{"origin":"Bucharest","destination":"Paris"}',
        "archived_at": None,
    }
    data.update(overrides)
    return data


class TestRouteRepositoryCRUD(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.repo = RouteRepository(self.db)

    def test_create_returns_id(self):
        route_id = self.repo.create(_route_data())
        self.assertIsInstance(route_id, int)
        self.assertGreater(route_id, 0)

    def test_get_by_id_returns_route(self):
        route_id = self.repo.create(_route_data())
        route = self.repo.get_by_id(route_id)
        self.assertIsNotNone(route)
        self.assertEqual(route["total_distance_km"], 2300.0)
        self.assertEqual(route["truck_label"], "B-100-XYZ")

    def test_get_by_id_returns_none_for_missing(self):
        self.assertIsNone(self.repo.get_by_id(99999))

    def test_update_changes_fields(self):
        route_id = self.repo.create(_route_data())
        self.repo.update(route_id, {"total_distance_km": 2500.0, "profile": "truck_fast"})
        route = self.repo.get_by_id(route_id)
        self.assertEqual(route["total_distance_km"], 2500.0)
        self.assertEqual(route["profile"], "truck_fast")

    def test_delete_removes_record(self):
        route_id = self.repo.create(_route_data())
        self.repo.delete(route_id)
        self.assertIsNone(self.repo.get_by_id(route_id))

    def test_count_reflects_changes(self):
        self.assertEqual(self.repo.count(), 0)
        self.repo.create(_route_data())
        self.assertEqual(self.repo.count(), 1)
        self.repo.create(_route_data(route_fingerprint="fp-002"))
        self.assertEqual(self.repo.count(), 2)

    def test_archive_sets_archived_at(self):
        route_id = self.repo.create(_route_data())
        self.repo.archive(route_id, "2025-01-01T00:00:00Z")
        route = self.repo.get_by_id(route_id)
        self.assertEqual(route["archived_at"], "2025-01-01T00:00:00Z")

    def test_get_all_excludes_archived(self):
        r1 = self.repo.create(_route_data(route_fingerprint="fp-a"))
        r2 = self.repo.create(_route_data(route_fingerprint="fp-b"))
        self.repo.archive(r1)
        active = self.repo.get_all()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["id"], r2)

    def test_get_all_includes_archived_when_requested(self):
        r1 = self.repo.create(_route_data(route_fingerprint="fp-a"))
        self.repo.create(_route_data(route_fingerprint="fp-b"))
        self.repo.archive(r1)
        all_routes = self.repo.get_all(include_archived=True)
        self.assertEqual(len(all_routes), 2)


class TestRouteRepositoryUpsert(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.repo = RouteRepository(self.db)

    def test_upsert_creates_new_when_not_exists(self):
        route_id = self.repo.upsert(
            _route_data(route_fingerprint="fp-upsert-new"),
            fingerprint="fp-upsert-new",
        )
        self.assertGreater(route_id, 0)

    def test_upsert_updates_existing_fingerprint(self):
        self.repo.upsert(
            _route_data(route_fingerprint="fp-upsert", total_distance_km=100.0),
            fingerprint="fp-upsert",
        )
        route_id = self.repo.upsert(
            _route_data(route_fingerprint="fp-upsert", total_distance_km=200.0),
            fingerprint="fp-upsert",
        )
        route = self.repo.get_by_id(route_id)
        self.assertEqual(route["total_distance_km"], 200.0)
        self.assertEqual(route["calculation_count"], 2)

    def test_get_id_by_fingerprint_returns_correct_id(self):
        route_id = self.repo.create(_route_data(route_fingerprint="fp-by-fp"))
        found = self.repo.get_id_by_fingerprint("fp-by-fp")
        self.assertEqual(found, route_id)

    def test_get_id_by_fingerprint_returns_none_for_missing(self):
        self.assertIsNone(self.repo.get_id_by_fingerprint("fp-nonexistent"))


class TestRouteRepositoryQueries(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.repo = RouteRepository(self.db)
        self.repo.create(_route_data(
            route_fingerprint="fp-q1", truck_id="1", truck_label="Truck A",
            profile="truck",
        ))
        self.repo.create(_route_data(
            route_fingerprint="fp-q2", truck_id="2", truck_label="Truck B",
            profile="truck_fast",
        ))
        self.repo.create(_route_data(
            route_fingerprint="fp-q3", truck_id="1", truck_label="Truck A",
            profile="truck",
        ))

    def test_get_by_truck_returns_all_for_truck(self):
        results = self.repo.get_by_truck("1")
        self.assertEqual(len(results), 2)

    def test_get_by_truck_returns_empty_for_unknown(self):
        results = self.repo.get_by_truck("999")
        self.assertEqual(len(results), 0)

    def test_get_by_profile_returns_correct_count(self):
        results = self.repo.get_by_profile("truck")
        self.assertEqual(len(results), 2)
        results_fast = self.repo.get_by_profile("truck_fast")
        self.assertEqual(len(results_fast), 1)

    def test_search_by_truck_label(self):
        results = self.repo.search(truck="Truck A")
        self.assertEqual(len(results), 2)

    def test_search_by_profile(self):
        results = self.repo.search(profile="truck_fast")
        self.assertEqual(len(results), 1)

    def test_search_empty_returns_all(self):
        results = self.repo.search()
        self.assertEqual(len(results), 3)

    def test_search_respects_limit(self):
        results = self.repo.search(limit=1)
        self.assertEqual(len(results), 1)

    def test_count_filtered_returns_correct_count(self):
        count = self.repo.count_filtered(truck="Truck B")
        self.assertEqual(count, 1)

    def test_prune_before_removes_old(self):
        old_date = "2020-01-01T00:00:00Z"
        self.repo.create(_route_data(
            route_fingerprint="fp-old",
            last_calculated_at=old_date,
        ))
        removed = self.repo.prune_before("2021-01-01T00:00:00Z")
        self.assertGreater(removed, 0)


class TestRouteRepositoryEdgeCases(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.repo = RouteRepository(self.db)

    def test_create_with_long_fingerprint(self):
        long_fp = "fp-" + ("x" * 200)
        route_id = self.repo.create(_route_data(route_fingerprint=long_fp))
        self.assertGreater(route_id, 0)

    def test_update_nonexistent_does_not_raise(self):
        self.repo.update(99999, {"total_distance_km": 0.0})

    def test_clear_all_removes_everything(self):
        self.repo.create(_route_data(route_fingerprint="fp-clr1"))
        self.repo.create(_route_data(route_fingerprint="fp-clr2"))
        self.assertEqual(self.repo.count(), 2)
        removed = self.repo.clear_all()
        self.assertEqual(removed, 2)
        self.assertEqual(self.repo.count(), 0)


if __name__ == "__main__":
    unittest.main()
