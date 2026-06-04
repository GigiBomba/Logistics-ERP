"""Unit + integration tests for AlertManager: creation, persistence after restart."""
import unittest
from unittest import mock

from services.operations.alert_manager import AlertManager, Alert, AlertType, Severity


class TestAlertCreation(unittest.TestCase):
    def setUp(self):
        AlertManager._instance = None

    def test_create_alert_returns_alert_object(self):
        mgr = AlertManager(db=None)
        alert = mgr.create_alert(
            AlertType.MAINTENANCE,
            Severity.WARNING,
            "Oil change due",
            "Truck ABC-123 needs oil change",
        )
        self.assertIsInstance(alert, Alert)
        self.assertEqual(alert.type, AlertType.MAINTENANCE)
        self.assertEqual(alert.severity, Severity.WARNING)
        self.assertEqual(alert.title, "Oil change due")
        self.assertFalse(alert.resolved)

    def test_create_alert_generates_unique_id(self):
        mgr = AlertManager(db=None)
        a1 = mgr.create_alert(AlertType.INSPECTION, Severity.INFO, "T1", "M1")
        a2 = mgr.create_alert(AlertType.INSURANCE, Severity.INFO, "T2", "M2")
        self.assertNotEqual(a1.id, a2.id)

    def test_create_alert_stores_metadata(self):
        mgr = AlertManager(db=None)
        alert = mgr.create_alert(
            AlertType.TRIP_DELAY,
            Severity.CRITICAL,
            "Late delivery",
            "Trip #42 is 4 hours late",
            metadata={"trip_id": 42, "minutes_overdue": 240},
        )
        self.assertEqual(alert.metadata["trip_id"], 42)
        self.assertEqual(alert.metadata["minutes_overdue"], 240)

    def test_create_alert_stores_truck_id(self):
        mgr = AlertManager(db=None)
        alert = mgr.create_alert(
            AlertType.MAINTENANCE, Severity.WARNING,
            "T", "M", truck_id="5",
        )
        self.assertEqual(alert.truck_id, "5")

    def test_alert_to_dict_includes_all_fields(self):
        mgr = AlertManager(db=None)
        alert = mgr.create_alert(
            AlertType.COMPLIANCE_WARNING, Severity.INFO, "Test", "Body",
            trip_id="42",
        )
        d = alert.to_dict()
        self.assertEqual(d["type"], "compliance_warning")
        self.assertEqual(d["severity"], "info")
        self.assertEqual(d["title"], "Test")
        self.assertEqual(d["trip_id"], "42")


class TestAlertResolution(unittest.TestCase):
    def setUp(self):
        AlertManager._instance = None
        self.mgr = AlertManager(db=None)

    def test_resolve_alert_sets_resolved_true(self):
        alert = self.mgr.create_alert(
            AlertType.INSPECTION, Severity.WARNING, "T", "M",
        )
        resolved = self.mgr.resolve_alert(alert.id)
        self.assertTrue(resolved.resolved)
        self.assertIsNotNone(resolved.resolved_at)

    def test_resolve_nonexistent_returns_none(self):
        self.assertIsNone(self.mgr.resolve_alert("nonexistent-id"))

    def test_resolve_already_resolved_returns_alert(self):
        alert = self.mgr.create_alert(AlertType.INSPECTION, Severity.WARNING, "T", "M")
        self.mgr.resolve_alert(alert.id)
        result = self.mgr.resolve_alert(alert.id)
        self.assertIsNotNone(result)

    def test_get_active_alerts_excludes_resolved(self):
        a1 = self.mgr.create_alert(AlertType.MAINTENANCE, Severity.WARNING, "T1", "M1")
        a2 = self.mgr.create_alert(AlertType.INSPECTION, Severity.INFO, "T2", "M2")
        self.mgr.resolve_alert(a1.id)
        active = self.mgr.get_active_alerts()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].id, a2.id)

    def test_get_active_count_counts_correctly(self):
        self.mgr.create_alert(AlertType.MAINTENANCE, Severity.WARNING, "T1", "M1")
        a2 = self.mgr.create_alert(AlertType.INSPECTION, Severity.INFO, "T2", "M2")
        self.mgr.resolve_alert(a2.id)
        self.assertEqual(self.mgr.get_active_count(), 1)


class TestAlertQuerying(unittest.TestCase):
    def setUp(self):
        AlertManager._instance = None
        self.mgr = AlertManager(db=None)
        self.mgr.create_alert(AlertType.MAINTENANCE, Severity.WARNING, "T1", "M1", truck_id="T1")
        self.mgr.create_alert(AlertType.INSPECTION, Severity.CRITICAL, "T2", "M2", truck_id="T2")
        self.mgr.create_alert(AlertType.MAINTENANCE, Severity.INFO, "T3", "M3", truck_id="T1")

    def test_get_alerts_by_type(self):
        results = self.mgr.get_alerts(alert_type=AlertType.MAINTENANCE)
        self.assertEqual(len(results), 2)
        for a in results:
            self.assertEqual(a.type, AlertType.MAINTENANCE)

    def test_get_alerts_by_severity(self):
        results = self.mgr.get_alerts(severity=Severity.CRITICAL)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].severity, Severity.CRITICAL)

    def test_get_alerts_by_truck_id(self):
        results = self.mgr.get_alerts(truck_id="T1")
        self.assertEqual(len(results), 2)

    def test_get_alerts_combined_filters(self):
        results = self.mgr.get_alerts(
            alert_type=AlertType.MAINTENANCE,
            severity=Severity.WARNING,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "T1")

    def test_get_alerts_limit(self):
        results = self.mgr.get_alerts(limit=1)
        self.assertEqual(len(results), 1)

    def test_resolve_by_truck_resolves_all_for_truck(self):
        self.mgr.resolve_by_truck("T1")
        active = self.mgr.get_active_alerts()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].truck_id, "T2")

    def test_resolve_by_truck_with_type_filter(self):
        self.mgr.resolve_by_truck("T1", AlertType.MAINTENANCE)
        active = self.mgr.get_active_alerts()
        self.assertEqual(len(active), 1)  # Only T2/CRITICAL remains

    def test_get_active_by_type_and_entity(self):
        result = self.mgr.get_active_by_type_and_entity(
            AlertType.MAINTENANCE, "T1", entity_field="truck_id"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.type, AlertType.MAINTENANCE)


class TestAlertPersistence(unittest.TestCase):
    """Verify that alerts survive AlertManager restart (load from DB)."""

    def setUp(self):
        AlertManager._instance = None
        from tests.test_helpers import make_db
        self.db = make_db()

    def test_alerts_persisted_and_reloaded(self):
        mgr1 = AlertManager(db=self.db)
        a1 = mgr1.create_alert(
            AlertType.OVERDUE_INVOICE, Severity.CRITICAL,
            "Unpaid invoice", "Trip #7 overdue",
            trip_id="7",
            metadata={"amount": 500.0},
        )
        a2 = mgr1.create_alert(
            AlertType.MAINTENANCE, Severity.WARNING,
            "Tire change", "Truck needs tires",
            truck_id="3",
        )

        # Simulate restart: reset singleton and create fresh instance
        AlertManager._instance = None
        mgr2 = AlertManager(db=self.db)

        active = mgr2.get_active_alerts()
        self.assertEqual(len(active), 2)

        ids = {a.id for a in active}
        self.assertIn(a1.id, ids)
        self.assertIn(a2.id, ids)

    def test_resolved_alerts_not_reloaded(self):
        mgr1 = AlertManager(db=self.db)
        a1 = mgr1.create_alert(
            AlertType.INSPECTION, Severity.INFO, "T1", "M1",
        )
        mgr1.resolve_alert(a1.id)

        AlertManager._instance = None
        mgr2 = AlertManager(db=self.db)

        active = mgr2.get_active_alerts()
        self.assertEqual(len(active), 0)

    def test_persistence_preserves_metadata(self):
        mgr1 = AlertManager(db=self.db)
        mgr1.create_alert(
            AlertType.TRIP_DELAY, Severity.CRITICAL,
            "Late", "Desc",
            metadata={"minutes_overdue": 180, "status": "In Transit"},
        )

        AlertManager._instance = None
        mgr2 = AlertManager(db=self.db)

        active = mgr2.get_active_alerts()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].metadata["minutes_overdue"], 180)
        self.assertEqual(active[0].metadata["status"], "In Transit")

    def test_cleanup_old_alerts(self):
        mgr1 = AlertManager(db=self.db)
        old = mgr1.create_alert(
            AlertType.MAINTENANCE, Severity.INFO, "Old", "Very old alert",
        )
        # Manually set created_at to 100 days ago
        from datetime import datetime, timedelta
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        mgr1._alerts[old.id].created_at = old_date
        mgr1._db.conn.execute(
            "UPDATE alerts SET created_at = ? WHERE id = ?", (old_date, old.id)
        )
        mgr1._db.conn.commit()
        mgr1.resolve_alert(old.id)
        # Also persist the resolution
        mgr1._persist_resolution(mgr1._alerts[old.id])

        removed = mgr1.cleanup_old(days=90)
        self.assertEqual(removed, 1)


if __name__ == "__main__":
    unittest.main()
