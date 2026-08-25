"""Unit + integration tests for ClientService: creation, backfill, edge cases."""
from __future__ import annotations

import unittest
from datetime import datetime

from tests.test_helpers import make_db
from services.client_service import ClientService


def _add_trip(db, client_name, client_id=None, total_price=500.0):
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    start = datetime.now().strftime("%Y-%m-%d")
    db.conn.execute(
        "INSERT INTO trips (created_at, truck_number, driver_name, client_name, client_id, "
        "distance_km, total_price_eur, rate_per_km, gross_per_km, net_profit, "
        "start_date, end_date, fuel_cost, toll_cost, salary_cost, extra_costs, currency, status) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (now, "T-001", "D", client_name, client_id,
         100.0, total_price, 5.0, 5.0, total_price - 200.0,
         start, start, 100.0, 50.0, 50.0, 0, "EUR", "Delivered"),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestClientServiceCreation(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.svc = ClientService(self.db)

    def test_create_client_returns_id(self):
        client_id = self.svc.create("ACME Corp")
        self.assertIsInstance(client_id, int)
        self.assertGreater(client_id, 0)

    def test_create_client_persists_name(self):
        client_id = self.svc.create("Globex Inc")
        retrieved = self.svc.get_by_id(client_id)
        self.assertEqual(retrieved["name"], "Globex Inc")

    def test_create_client_defaults_active(self):
        client_id = self.svc.create("Initech")
        retrieved = self.svc.get_by_id(client_id)
        self.assertEqual(retrieved["is_active"], 1)

    def test_create_client_with_extra_fields(self):
        client_id = self.svc.create(
            "Umbrella Corp",
            vat_number="RO123456",
            contact_person="Alice",
            phone="+40700123456",
        )
        retrieved = self.svc.get_by_id(client_id)
        self.assertEqual(retrieved["vat_number"], "RO123456")
        self.assertEqual(retrieved["contact_person"], "Alice")

    def test_create_duplicate_name_allowed(self):
        id1 = self.svc.create("ACME")
        id2 = self.svc.create("ACME")
        self.assertNotEqual(id1, id2)

    def test_get_all_excludes_inactive_by_default(self):
        self.svc.create("ActiveCo")
        inactive_id = self.svc.create("InactiveCo")
        self.svc.deactivate(inactive_id)
        active = self.svc.get_all()
        names = {c["name"] for c in active}
        self.assertIn("ActiveCo", names)
        self.assertNotIn("InactiveCo", names)

    def test_get_all_includes_inactive_when_requested(self):
        self.svc.create("ActiveCo")
        inactive_id = self.svc.create("InactiveCo")
        self.svc.deactivate(inactive_id)
        all_clients = self.svc.get_all(include_inactive=True)
        names = {c["name"] for c in all_clients}
        self.assertIn("ActiveCo", names)
        self.assertIn("InactiveCo", names)


class TestClientServiceBackfill(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.svc = ClientService(self.db)

    def test_get_or_create_creates_new(self):
        client_id = self.svc.get_or_create("NewClient")
        self.assertIsNotNone(client_id)
        self.assertGreater(client_id, 0)

    def test_get_or_create_returns_existing(self):
        id1 = self.svc.get_or_create("UniqueCorp")
        id2 = self.svc.get_or_create("UniqueCorp")
        self.assertEqual(id1, id2)

    def test_get_or_create_empty_name_returns_none(self):
        result = self.svc.get_or_create("")
        self.assertIsNone(result)

    def test_get_or_create_whitespace_name_returns_none(self):
        result = self.svc.get_or_create("   ")
        self.assertIsNone(result)

    def test_get_or_create_strips_whitespace(self):
        id1 = self.svc.get_or_create("  Spaces Co  ")
        id2 = self.svc.get_or_create("Spaces Co")
        self.assertEqual(id1, id2)

    def test_resolve_client_id_returns_none_for_missing(self):
        self.assertIsNone(self.svc.resolve_client_id("Nonexistent"))

    def test_resolve_client_id_returns_id_for_existing(self):
        client_id = self.svc.create("KnownClient")
        resolved = self.svc.resolve_client_id("KnownClient")
        self.assertEqual(resolved, client_id)


class TestClientServiceQueries(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.svc = ClientService(self.db)

    def test_get_by_id_returns_none_for_missing(self):
        self.assertIsNone(self.svc.get_by_id(99999))

    def test_search_finds_by_name(self):
        self.svc.create("TransLogistics")
        self.svc.create("GlobalShip")
        results = self.svc.search("Trans")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "TransLogistics")

    def test_search_returns_empty_for_no_match(self):
        self.svc.create("ACME")
        results = self.svc.search("XYZ")
        self.assertEqual(len(results), 0)

    def test_get_trip_count_returns_correct_count(self):
        client_id = self.svc.create("TripHeavy")
        _add_trip(self.db, "TripHeavy", client_id=client_id, total_price=100.0)
        _add_trip(self.db, "TripHeavy", client_id=client_id, total_price=200.0)
        self.assertEqual(self.svc.get_trip_count(client_id), 2)

    def test_get_trip_count_zero_for_client_without_trips(self):
        client_id = self.svc.create("NoTrips")
        self.assertEqual(self.svc.get_trip_count(client_id), 0)

    def test_get_top_clients_ordered_by_revenue(self):
        c1 = self.svc.create("Big")
        c2 = self.svc.create("Small")
        _add_trip(self.db, "Big", client_id=c1, total_price=5000.0)
        _add_trip(self.db, "Small", client_id=c2, total_price=100.0)
        top = self.svc.get_top_clients(limit=2)
        self.assertGreater(len(top), 0)
        if len(top) >= 2:
            self.assertGreater(top[0]["total_revenue"], top[1]["total_revenue"])

    def test_deactivate_changes_status(self):
        client_id = self.svc.create("ToDeactivate")
        self.svc.deactivate(client_id)
        retrieved = self.svc.get_by_id(client_id)
        self.assertEqual(retrieved["is_active"], 0)

    def test_update_modifies_fields(self):
        client_id = self.svc.create("UpdateMe")
        self.svc.update(client_id, phone="+40700222333", email="test@test.com")
        retrieved = self.svc.get_by_id(client_id)
        self.assertEqual(retrieved["phone"], "+40700222333")
        self.assertEqual(retrieved["email"], "test@test.com")


if __name__ == "__main__":
    unittest.main()
