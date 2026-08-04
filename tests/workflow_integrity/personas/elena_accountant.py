"""Persona: Elena — accountant with invoice/payment workflow data.

Scale: 1 company, 1 accountant, 5 delivered trips (awaiting invoicing),
3 invoiced trips (awaiting payment), 2 paid trips.
"""

from __future__ import annotations

from .fixtures import seed_client, seed_company, seed_driver, seed_trip, seed_truck, seed_user


def build_elena_persona(db):
    """Seed the database with the Elena accountant persona."""
    company_id = seed_company(db, company_name="Elena Contabilitate SRL", subscription_tier="professional")

    user_id = seed_user(db, company_id=company_id, email="elena@contabilitate.ro",
                        role="dispatcher", display_name="Elena Ionescu")

    driver_id = seed_driver(db, company_id=company_id, name="Generic Driver", license_number="RO-ACC-001")
    truck_id = seed_truck(db, plate_number="B-600-ACC", manufacturer="Volvo", model="FH 500", year=2023,
                          company_id=company_id)

    client_1 = seed_client(db, name="Client Facturabil 1 SRL")
    client_2 = seed_client(db, name="Client Facturabil 2 SA")

    delivered_ids = []
    for i in range(5):
        tid = seed_trip(db, company_id=company_id, client_id=client_1,
                        client_name="Client Facturabil 1 SRL",
                        driver_name="Generic Driver", driver_id=driver_id,
                        truck_number="B-600-ACC", truck_id=truck_id,
                        distance_km=400 + i * 50, total_price_eur=1200 + i * 200,
                        status="Delivered",
                        start_date=f"2026-07-{(10+i):02d}", end_date=f"2026-07-{(13+i):02d}")
        delivered_ids.append(tid)

    invoiced_ids = []
    for i in range(3):
        tid = seed_trip(db, company_id=company_id, client_id=client_2,
                        client_name="Client Facturabil 2 SA",
                        driver_name="Generic Driver", driver_id=driver_id,
                        truck_number="B-600-ACC", truck_id=truck_id,
                        distance_km=300 + i * 80, total_price_eur=900 + i * 150,
                        status="Invoiced",
                        start_date=f"2026-07-{(5+i):02d}", end_date=f"2026-07-{(8+i):02d}")
        invoiced_ids.append(tid)

    paid_ids = []
    for i in range(2):
        tid = seed_trip(db, company_id=company_id, client_id=client_1,
                        client_name="Client Facturabil 1 SRL",
                        driver_name="Generic Driver", driver_id=driver_id,
                        truck_number="B-600-ACC", truck_id=truck_id,
                        distance_km=200 + i * 60, total_price_eur=600 + i * 100,
                        status="Paid",
                        start_date=f"2026-07-{(1+i):02d}", end_date=f"2026-07-{(4+i):02d}")
        paid_ids.append(tid)

    return {
        "company_id": company_id, "user_id": user_id,
        "driver_id": driver_id, "truck_id": truck_id,
        "client_ids": [client_1, client_2],
        "trip_ids": {"delivered": delivered_ids, "invoiced": invoiced_ids, "paid": paid_ids},
    }
