"""Persona: Marius — ops manager with ARGO autonomy enabled.

Scale: enterprise tier, ARGO autonomy flags active, large fleet.
Represents the power-user who relies on autonomous scheduling,
conflict resolution, and predictive maintenance.
"""

from __future__ import annotations

from .fixtures import seed_client, seed_company, seed_driver, seed_trip, seed_truck, seed_user


def build_marius_persona(db):
    """Seed the database with the Marius ARGO power-user persona."""
    company_id = seed_company(db, company_name="Marius ARGO Logistics SA", subscription_tier="enterprise")

    user_id = seed_user(db, company_id=company_id, email="marius@argo.ro",
                        role="dispatcher", display_name="Marius Vasilescu")

    driver_ids = []
    for i in range(1, 21):
        did = seed_driver(db, company_id=company_id, name=f"ARGO Driver {i:02d}",
                          license_number=f"RO-ARGO-{i:03d}")
        driver_ids.append(did)

    truck_ids = []
    for i in range(1, 21):
        tid = seed_truck(db, plate_number=f"B-{700+i}-ARG", manufacturer="Volvo",
                         model="FH 500 I-Save", year=2024, mileage=20000 + i * 5000, fuel_consumption=24.5,
                         company_id=company_id)
        truck_ids.append(tid)

    clients = ["ARGO Client A", "ARGO Client B", "ARGO Client C", "ARGO Client D",
               "ARGO Client E", "ARGO Client F", "ARGO Client G", "ARGO Client H"]
    client_ids = [seed_client(db, name=n) for n in clients]

    statuses = (["Planned"] * 5 + ["Loading"] * 5 + ["In Transit"] * 8 + ["Delivered"] * 6 + ["Invoiced"] * 4 + ["Paid"] * 2)
    trip_ids = []
    for i in range(30):
        tid = seed_trip(db, company_id=company_id, client_id=client_ids[i % 8],
                        client_name=clients[i % 8],
                        driver_name=f"ARGO Driver {(i % 20) + 1:02d}",
                        driver_id=driver_ids[i % 20],
                        truck_number=f"B-{700 + (i % 20) + 1}-ARG",
                        truck_id=truck_ids[i % 20],
                        distance_km=350 + i * 40, total_price_eur=1100 + i * 120,
                        status=statuses[i], start_date=f"2026-07-{(10 + i // 2):02d}",
                        end_date=f"2026-07-{(13 + i // 2):02d}")
        trip_ids.append(tid)

    return {
        "company_id": company_id, "user_id": user_id,
        "driver_ids": driver_ids, "truck_ids": truck_ids,
        "client_ids": client_ids, "trip_ids": trip_ids,
    }
