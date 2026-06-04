"""Unit + integration tests for TripService: creation, status transitions, edge cases."""
import unittest
from datetime import datetime

from tests.test_helpers import make_db
from services.trip_service import TripService


def _trip_data(**overrides):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    data = {
        "created_at": now,
        "truck_number": "B-123-ABC",
        "truck_id": None,
        "driver_name": "John Doe",
        "driver_id": None,
        "client_name": "ACME Corp",
        "client_id": None,
        "distance_km": 500.0,
        "total_price_eur": 1000.0,
        "rate_per_km": 2.0,
        "gross_per_km": 2.0,
        "net_profit": 800.0,
        "start_date": datetime.now().strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "fuel_cost": 100.0,
        "toll_cost": 50.0,
        "salary_cost": 50.0,
        "extra_costs": 0,
        "currency": "EUR",
        "status": "Planned",
    }
    data.update(overrides)
    return data


class TestTripServiceCreation(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.svc = TripService(self.db)

    def test_add_trip_returns_id(self):
        trip_id = self.svc.add(_trip_data())
        self.assertIsInstance(trip_id, int)
        self.assertGreater(trip_id, 0)

    def test_add_trip_persists_all_fields(self):
        data = _trip_data(client_name="TestClient", distance_km=750.0)
        trip_id = self.svc.add(data)

        retrieved = self.svc.get_by_id(trip_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["client_name"], "TestClient")
        self.assertEqual(retrieved["distance_km"], 750.0)
        self.assertEqual(retrieved["status"], "Planned")

    def test_add_trip_with_truck_id(self):
        data = _trip_data(truck_id=42, truck_number="B-42-XYZ")
        trip_id = self.svc.add(data)
        retrieved = self.svc.get_by_id(trip_id)
        self.assertEqual(retrieved["truck_id"], 42)
        self.assertEqual(retrieved["truck_number"], "B-42-XYZ")

    def test_add_trip_with_driver_id(self):
        data = _trip_data(driver_id=7, driver_name="Alice")
        trip_id = self.svc.add(data)
        retrieved = self.svc.get_by_id(trip_id)
        self.assertEqual(retrieved["driver_id"], 7)
        self.assertEqual(retrieved["driver_name"], "Alice")

    def test_add_trip_with_negative_profit(self):
        data = _trip_data(net_profit=-50.0, total_price_eur=200.0)
        trip_id = self.svc.add(data)
        retrieved = self.svc.get_by_id(trip_id)
        self.assertEqual(retrieved["net_profit"], -50.0)

    def test_add_trip_zero_distance(self):
        data = _trip_data(distance_km=0.0)
        trip_id = self.svc.add(data)
        retrieved = self.svc.get_by_id(trip_id)
        self.assertEqual(retrieved["distance_km"], 0.0)

    def test_add_multiple_trips_have_unique_ids(self):
        id1 = self.svc.add(_trip_data())
        id2 = self.svc.add(_trip_data())
        id3 = self.svc.add(_trip_data())
        self.assertNotEqual(id1, id2)
        self.assertNotEqual(id2, id3)
        self.assertNotEqual(id1, id3)


class TestTripServiceStatusTransitions(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.svc = TripService(self.db)
        self.trip_id = self.svc.add(_trip_data(status="Planned"))

    def test_update_status_to_loading(self):
        self.svc.update(self.trip_id, {"status": "Loading"})
        retrieved = self.svc.get_by_id(self.trip_id)
        self.assertEqual(retrieved["status"], "Loading")

    def test_update_status_to_in_transit(self):
        self.svc.update(self.trip_id, {"status": "In Transit"})
        retrieved = self.svc.get_by_id(self.trip_id)
        self.assertEqual(retrieved["status"], "In Transit")

    def test_update_status_to_delivered(self):
        self.svc.update(self.trip_id, {"status": "Delivered"})
        retrieved = self.svc.get_by_id(self.trip_id)
        self.assertEqual(retrieved["status"], "Delivered")

    def test_update_multiple_fields_at_once(self):
        self.svc.update(self.trip_id, {
            "status": "In Transit",
            "distance_km": 600.0,
            "net_profit": 950.0,
        })
        retrieved = self.svc.get_by_id(self.trip_id)
        self.assertEqual(retrieved["status"], "In Transit")
        self.assertEqual(retrieved["distance_km"], 600.0)
        self.assertEqual(retrieved["net_profit"], 950.0)

    def test_update_truck_assignment(self):
        self.svc.update(self.trip_id, {"truck_id": 99, "truck_number": "B-99-NEW"})
        retrieved = self.svc.get_by_id(self.trip_id)
        self.assertEqual(retrieved["truck_id"], 99)
        self.assertEqual(retrieved["truck_number"], "B-99-NEW")

    def test_update_driver_assignment(self):
        self.svc.update(self.trip_id, {"driver_id": 5, "driver_name": "Bob"})
        retrieved = self.svc.get_by_id(self.trip_id)
        self.assertEqual(retrieved["driver_id"], 5)
        self.assertEqual(retrieved["driver_name"], "Bob")

    def test_update_clears_truck_id(self):
        self.svc.update(self.trip_id, {"truck_id": 1})
        self.svc.update(self.trip_id, {"truck_id": None})
        retrieved = self.svc.get_by_id(self.trip_id)
        self.assertIsNone(retrieved["truck_id"])


class TestTripServiceQueries(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.svc = TripService(self.db)
        self.svc.add(_trip_data(status="Planned", client_name="ACME"))
        self.svc.add(_trip_data(status="In Transit", client_name="Globex"))
        self.svc.add(_trip_data(status="Delivered", client_name="ACME"))

    def test_get_by_id_returns_none_for_missing(self):
        self.assertIsNone(self.svc.get_by_id(99999))

    def test_get_by_statuses_filters_correctly(self):
        active = self.svc.get_by_statuses(["Planned", "In Transit"])
        self.assertEqual(len(active), 2)
        statuses = {t["status"] for t in active}
        self.assertIn("Planned", statuses)
        self.assertIn("In Transit", statuses)

    def test_get_by_statuses_returns_empty_for_no_match(self):
        result = self.svc.get_by_statuses(["Cancelled"])
        self.assertEqual(len(result), 0)

    def test_get_all_respects_limit(self):
        result = self.svc.get_all(limit=2)
        self.assertLessEqual(len(result), 2)

    def test_get_filtered_by_status(self):
        result = self.svc.get_filtered(status="Delivered")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "Delivered")

    def test_get_filtered_by_client_search(self):
        result = self.svc.get_filtered(search="ACME")
        self.assertEqual(len(result), 2)

    def test_get_filtered_by_client_search_case_insensitive(self):
        result = self.svc.get_filtered(search="acme")
        self.assertEqual(len(result), 2)


class TestTripServiceDelete(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.svc = TripService(self.db)
        self.trip_id = self.svc.add(_trip_data())

    def test_delete_removes_trip(self):
        self.svc.delete(self.trip_id)
        self.assertIsNone(self.svc.get_by_id(self.trip_id))

    def test_delete_nonexistent_does_not_raise(self):
        self.svc.delete(99999)


if __name__ == "__main__":
    unittest.main()
