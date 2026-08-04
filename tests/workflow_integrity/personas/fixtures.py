"""Shared persona data generators — thin SQL-level seed helpers.

Every helper inserts exactly one row and returns the new ``id``.
Callers compose these to build persona-specific configurations.

All helpers accept ``**overrides`` so persona builders can replace
any column value without rewriting the INSERT.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

_TODAY = date.today()
_NOW = datetime.now().isoformat()
_TOMORROW = (_TODAY + timedelta(days=1)).isoformat()
_DAY_AFTER = (_TODAY + timedelta(days=4)).isoformat()


# ── Companies ────────────────────────────────────────────────────

def seed_company(db, *, company_name: str,
                 subscription_tier: str = "starter",
                 is_active: int = 1) -> int:
    """Insert a company row and return its id."""
    db.conn.execute(
        "INSERT INTO companies (company_name, subscription_tier, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (company_name, subscription_tier, is_active, _NOW, _NOW),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Users ────────────────────────────────────────────────────────

def seed_user(db, *, company_id: int, email: str, role: str = "dispatcher",
              display_name: str = "", password: str = "s3cur3P@ss!",
              is_active: int = 1) -> int:
    """Insert a user row and return its id."""
    db.conn.execute(
        "INSERT INTO users (company_id, email, password_hash, role, is_active, display_name, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (company_id, email, f"hashed:{password}", role, is_active, display_name or email, _NOW),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Drivers ──────────────────────────────────────────────────────

def seed_driver(db, *, company_id: int, name: str, license_number: str = "",
                phone: str = "", email: str = "", is_active: int = 1,
                user_id: int = None, monthly_salary: float = 0.0) -> int:
    """Insert a driver row and return its id."""
    db.conn.execute(
        "INSERT INTO drivers (company_id, name, license_number, phone, email, "
        "is_active, monthly_salary, user_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (company_id, name, license_number or f"LIC-{name.replace(' ', '-')}",
         phone or "+40-700-111-111", email or f"{name.lower().replace(' ', '.')}@example.com",
         is_active, monthly_salary, user_id, _NOW, _NOW),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Trucks ───────────────────────────────────────────────────────

def seed_truck(db, *, plate_number: str, manufacturer: str = "Volvo",
               model: str = "FH 460", year: int = 2022,
               mileage: float = 0.0, fuel_consumption: float = 28.5,
               **overrides: Any) -> int:
    """Insert a truck row and return its id."""
    args = {
        "plate_number": plate_number,
        "manufacturer": manufacturer,
        "model": model,
        "year": year,
        "mileage": mileage,
        "fuel_consumption": fuel_consumption,
    }
    args.update(overrides)
    db.conn.execute(
        "INSERT INTO trucks (plate_number, manufacturer, model, year, mileage, "
        "status, active_status, fuel_consumption) "
        "VALUES (?, ?, ?, ?, ?, 'active', 1, ?)",
        (args["plate_number"], args["manufacturer"], args["model"],
         args["year"], args["mileage"], args["fuel_consumption"]),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Clients ──────────────────────────────────────────────────────

def seed_client(db, *, name: str, email: str = "", phone: str = "",
                address: str = "", vat_number: str = "",
                is_active: int = 1, **overrides: Any) -> int:
    """Insert a client row and return its id."""
    args = {
        "name": name,
        "email": email or f"{name.lower().replace(' ', '_')}@example.com",
        "phone": phone or "+40-700-000-000",
        "address": address or "123 Main St",
        "vat_number": vat_number or f"RO{name[:4].upper()}001",
        "is_active": is_active,
    }
    args.update(overrides)
    db.conn.execute(
        "INSERT INTO clients (name, email, phone, address, vat_number, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (args["name"], args["email"], args["phone"], args["address"],
         args["vat_number"], args["is_active"], _NOW, _NOW),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Trips ────────────────────────────────────────────────────────

def seed_trip(db, *, company_id: int = None, client_id: int = None,
              client_name: str = "Default Client",
              driver_name: str = "Default Driver",
              driver_id: int = None,
              truck_number: str = "AB-123-CD",
              truck_id: int = None,
              distance_km: float = 850.0,
              total_price_eur: float = 2450.0,
              status: str = "Planned",
              start_date: str = _TOMORROW,
              end_date: str = _DAY_AFTER,
              currency: str = "EUR",
              fuel_cost: float = 320.0,
              toll_cost: float = 85.0,
              salary_cost: float = 600.0,
              extra_costs: float = 50.0,
              net_profit: float = 1395.0,
              rate_per_km: float = 2.88,
              gross_per_km: float = 1.64,
              **overrides: Any) -> int:
    """Insert a trip row and return its id."""
    args = {
        "company_id": company_id,
        "client_id": client_id,
        "client_name": client_name,
        "driver_name": driver_name,
        "driver_id": driver_id,
        "truck_number": truck_number,
        "truck_id": truck_id,
        "distance_km": distance_km,
        "total_price_eur": total_price_eur,
        "status": status,
        "start_date": start_date,
        "end_date": end_date,
        "currency": currency,
        "fuel_cost": fuel_cost,
        "toll_cost": toll_cost,
        "salary_cost": salary_cost,
        "extra_costs": extra_costs,
        "net_profit": net_profit,
        "rate_per_km": rate_per_km,
        "gross_per_km": gross_per_km,
    }
    args.update(overrides)
    db.conn.execute(
        "INSERT INTO trips (company_id, client_id, client_name, driver_name, driver_id, "
        "truck_number, truck_id, distance_km, total_price_eur, status, start_date, end_date, "
        "currency, fuel_cost, toll_cost, salary_cost, extra_costs, net_profit, "
        "rate_per_km, gross_per_km, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (args["company_id"], args["client_id"], args["client_name"],
         args["driver_name"], args["driver_id"], args["truck_number"],
         args["truck_id"], args["distance_km"], args["total_price_eur"],
         args["status"], args["start_date"], args["end_date"],
         args["currency"], args["fuel_cost"], args["toll_cost"],
         args["salary_cost"], args["extra_costs"], args["net_profit"],
         args["rate_per_km"], args["gross_per_km"], _NOW),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
