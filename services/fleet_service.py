"""Truck and expense service — delegates all DB operations to DatabaseManager."""

from services.operations.event_bus import EventBus, TRUCK_CREATED, TRUCK_UPDATED, TRUCK_DELETED


class FleetService:
    def __init__(self, db):
        self.db = db
        self._event_bus = EventBus()

    def get_trucks(self):
        return self.db.get_all_trucks()

    def get_truck(self, truck_id):
        return self.db.get_truck_by_id(truck_id)

    def get_assigned_routes(self, truck_id, status=None):
        return self.db.get_truck_routes(truck_id, status=status)

    def add_truck(self, data: dict) -> int:
        truck_id = self.db.add_truck(data)
        self._event_bus.publish(TRUCK_CREATED, {
            "truck_id": truck_id,
            "plate_number": data.get("plate_number", ""),
            "model": data.get("model", ""),
        })
        return truck_id

    def update_truck(self, truck_id, data: dict):
        self.db.update_truck(truck_id, data)
        self._event_bus.publish(TRUCK_UPDATED, {"truck_id": truck_id, "changes": data})

    def delete_truck(self, truck_id):
        self.db.delete_truck(truck_id)
        self._event_bus.publish(TRUCK_DELETED, {"truck_id": truck_id})

    def ensure_expenses_table(self):
        self.db.ensure_expenses_table()

    def get_expenses(self, truck_id):
        return self.db.get_expenses(truck_id)

    def add_expense(self, truck_id, date, category, description, amount):
        return self.db.add_expense(truck_id, date, category, description, amount)
