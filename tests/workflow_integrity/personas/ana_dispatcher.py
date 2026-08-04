"""Persona: Ana — dispatcher for a 10-truck fleet.

Scale: 1 company (professional tier), 10 trucks, 12 drivers,
1 dispatcher, 1 accountant, 1 mechanic.
"""

from __future__ import annotations

from .fixtures import seed_client, seed_company, seed_driver, seed_trip, seed_truck, seed_user


def build_ana_persona(db):
    """Seed the database with the Ana dispatcher persona."""
    company_id = seed_company(db, company_name="Ana Logistics SRL", subscription_tier="professional")

    dispatcher_id = seed_user(db, company_id=company_id, email="ana@logistics.ro",
                              role="dispatcher", display_name="Ana Dumitrescu")
    accountant_id = seed_user(db, company_id=company_id, email="contabilitate@logistics.ro",
                              role="dispatcher", display_name="Maria Contabil")
    mechanic_id = seed_user(db, company_id=company_id, email="service@logistics.ro",
                            role="dispatcher", display_name="Andrei Mecanic")

    driver_ids = []
    for i in range(1, 13):
        did = seed_driver(db, company_id=company_id, name=f"Driver Ana-{i:02d}",
                          license_number=f"RO-ANA-{i:03d}")
        driver_ids.append(did)

    truck_ids = []
    for i in range(1, 11):
        tid = seed_truck(db, plate_number=f"B-{300+i}-ANA",
                         manufacturer="Mercedes" if i <= 5 else "MAN",
                         model="Actros 1845" if i <= 5 else "TGX 18.510",
                         year=2022 if i <= 7 else 2023, mileage=60000 + i * 10000,
                         company_id=company_id)
        truck_ids.append(tid)

    client_names = ["Metro Cash & Carry", "Selgros", "Cora", "Kaufland", "Penny Market", "Auchan"]
    client_ids = [seed_client(db, name=n) for n in client_names]

    statuses = ["Planned", "Planned", "Loading", "Loading",
                "In Transit", "In Transit", "In Transit",
                "Delivered", "Delivered", "Delivered",
                "Delivered", "Invoiced", "Invoiced", "Paid", "Paid"]
    trip_ids = []
    for i in range(15):
        tid = seed_trip(db, company_id=company_id,
                        client_id=client_ids[i % len(client_ids)],
                        client_name=client_names[i % len(client_names)],
                        driver_name=f"Driver Ana-{(i % 12)+1:02d}",
                        driver_id=driver_ids[i % 12],
                        truck_number=f"B-{300+(i%10)+1}-ANA",
                        truck_id=truck_ids[i % 10],
                        distance_km=300 + i * 50, total_price_eur=900 + i * 150,
                        status=statuses[i],
                        start_date=f"2026-07-{(10+i):02d}", end_date=f"2026-07-{(13+i):02d}")
        trip_ids.append(tid)

    return {
        "company_id": company_id,
        "user_ids": {"dispatcher": dispatcher_id, "accountant": accountant_id, "mechanic": mechanic_id},
        "driver_ids": driver_ids, "truck_ids": truck_ids, "client_ids": client_ids,
        "trip_ids": trip_ids,
    }
