"""Shared test infrastructure: in-memory SQLite database with full schema."""
import sqlite3
from typing import Any, Dict, Optional


class InMemoryDB:
    """Lightweight in-memory database that mimics DatabaseManager's interface."""

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        from database.schema import (
            TABLE_TRIPS, TABLE_TRUCKS, TABLE_DRIVERS, TABLE_CLIENTS,
            TABLE_INVOICES, TABLE_ALERTS, TABLE_ROUTE_HISTORY_V2,
            TABLE_ROUTE_EVENTS, TABLE_TRUCK_ROUTE_ASSIGNMENTS,
            TABLE_SETTINGS, TABLE_EMAIL_LOGS, TABLE_TRIP_STATUS_HISTORY,
            TABLE_OPERATION_EVENTS, TABLE_DRIVER_TRUCK_ASSIGNMENTS,
            TABLE_MAINTENANCE_RECORDS, TABLE_MAINTENANCE_SCHEDULES,
            TABLE_TRUCK_HEALTH_SCORES,
            TABLE_TACHO_IMPORTS, TABLE_TACHO_DRIVER_ACTIVITY,
            TABLE_TACHO_VEHICLE_DATA,
            TABLE_CLIENT_CONTACTS, TABLE_CLIENT_TAGS,
            ALTER_TRIPS_ADD_DRIVER_ID, ALTER_TRIPS_ADD_TRUCK_ID,
            ALTER_CLIENTS_ADD_TYPE, ALTER_CLIENTS_ADD_PAYMENT_TERMS,
            ALTER_CLIENTS_ADD_CREDIT_LIMIT, ALTER_CLIENTS_ADD_DEFAULT_RATE,
            ALTER_CLIENTS_ADD_RATING,
        )
        self.conn.execute(TABLE_TRIPS)
        self.conn.execute(TABLE_TRUCKS)
        self.conn.execute(TABLE_DRIVERS)
        self.conn.execute(TABLE_CLIENTS)
        self.conn.execute(TABLE_INVOICES)
        self.conn.execute(TABLE_ALERTS)
        self.conn.execute(TABLE_ROUTE_HISTORY_V2)
        self.conn.execute(TABLE_ROUTE_EVENTS)
        self.conn.execute(TABLE_TRUCK_ROUTE_ASSIGNMENTS)
        self.conn.execute(TABLE_SETTINGS)
        self.conn.execute(TABLE_EMAIL_LOGS)
        self.conn.execute(TABLE_TRIP_STATUS_HISTORY)
        self.conn.execute(TABLE_OPERATION_EVENTS)
        self.conn.execute(TABLE_DRIVER_TRUCK_ASSIGNMENTS)
        self.conn.execute(TABLE_MAINTENANCE_RECORDS)
        self.conn.execute(TABLE_MAINTENANCE_SCHEDULES)
        self.conn.execute(TABLE_TRUCK_HEALTH_SCORES)
        self.conn.execute(TABLE_TACHO_IMPORTS)
        self.conn.execute(TABLE_TACHO_DRIVER_ACTIVITY)
        self.conn.execute(TABLE_TACHO_VEHICLE_DATA)
        self.conn.execute(TABLE_CLIENT_CONTACTS)
        self.conn.execute(TABLE_CLIENT_TAGS)
        # Apply migrations (columns added after initial schema)
        self.conn.execute(ALTER_TRIPS_ADD_DRIVER_ID)
        self.conn.execute(ALTER_TRIPS_ADD_TRUCK_ID)
        self.conn.execute("ALTER TABLE trips ADD COLUMN client_id INTEGER REFERENCES clients(id)")
        self.conn.execute("ALTER TABLE trips ADD COLUMN context_json TEXT")
        self.conn.execute("ALTER TABLE trips ADD COLUMN route_history_v2_id INTEGER REFERENCES route_history_v2(id)")
        self.conn.execute("ALTER TABLE trips ADD COLUMN truck_consumption_l_per_100km REAL")
        self.conn.execute(ALTER_CLIENTS_ADD_TYPE)
        self.conn.execute(ALTER_CLIENTS_ADD_PAYMENT_TERMS)
        self.conn.execute(ALTER_CLIENTS_ADD_CREDIT_LIMIT)
        self.conn.execute(ALTER_CLIENTS_ADD_DEFAULT_RATE)
        self.conn.execute(ALTER_CLIENTS_ADD_RATING)
        self.conn.commit()

    @staticmethod
    def row_to_dict(row) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def rows_to_dicts(rows) -> list:
        return [dict(r) for r in rows] if rows else []

    def get_trip_by_id(self, trip_id: int) -> Optional[Dict[str, Any]]:
        return self.row_to_dict(
            self.conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
        )

    def get_all_trips(self, limit: int = 500):
        return self.rows_to_dicts(
            self.conn.execute("SELECT * FROM trips ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        )

    def get_filtered_trips(self, search="", truck="", status="", limit: int = 200):
        query = "SELECT * FROM trips WHERE 1=1"
        params = []
        if search:
            query += " AND (client_name LIKE ? OR driver_name LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if truck:
            query += " AND truck_number = ?"
            params.append(truck)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self.rows_to_dicts(self.conn.execute(query, params).fetchall())

    def create_invoice_record(self, trip_id, inv_number, amount, due_date):
        from datetime import datetime
        try:
            self.conn.execute(
                "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
                "VALUES (?, ?, ?, ?, ?, 'Unpaid')",
                (trip_id, inv_number, datetime.now().strftime("%Y-%m-%d"), due_date, amount),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass


def make_db() -> InMemoryDB:
    return InMemoryDB()
