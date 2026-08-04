"""Persona: Mihai — 5-truck owner-operator (3 owned + 2 leased).

Scale: 1 company, 5 trucks, 5 drivers, minimal staff (owner only).
"""

from __future__ import annotations

from .fixtures import seed_client, seed_company, seed_driver, seed_trip, seed_truck, seed_user


def build_mihai_persona(db):
    """Seed the database with the Mihai owner-operator persona."""
    company_id = seed_company(db, company_name="Mihai Transport SRL", subscription_tier="professional")

    user_id = seed_user(db, company_id=company_id, email="mihai@transport.ro",
                        role="dispatcher", display_name="Mihai Ionescu", password="owner123")

    driver_names = ["Mihai Ionescu", "Vasile Popa", "Gheorghe Marin", "Adrian Stan", "Cristian Dumitru"]
    driver_ids = []
    for name in driver_names:
        did = seed_driver(db, company_id=company_id, name=name,
                          license_number=f"RO-{name[:3].upper()}-{len(driver_ids)+1:03d}",
                          phone=f"+40-72{len(driver_ids):07d}")
        driver_ids.append(did)

    owned_plates = ["B-101-MIH", "B-102-MIH", "B-103-MIH"]
    leased_plates = ["B-201-MIH", "B-202-MIH"]
    truck_ids = []

    for plate in owned_plates:
        tid = seed_truck(db, plate_number=plate, manufacturer="Volvo", model="FH 500", year=2021, mileage=120000,
                         company_id=company_id)
        truck_ids.append(tid)

    for plate in leased_plates:
        tid = seed_truck(db, plate_number=plate, manufacturer="Scania", model="R 450", year=2022, mileage=80000,
                         company_id=company_id)
        truck_ids.append(tid)

    client_1 = seed_client(db, name="Dedeman SRL", email="logistica@dedeman.ro")
    client_2 = seed_client(db, name="Autonom Distribution", email="flota@autonom.ro")
    client_3 = seed_client(db, name="Praktiker Romania", email="transport@praktiker.ro")

    trip_ids = []
    for i in range(5):
        tid = seed_trip(db, company_id=company_id,
                        client_id=[client_1, client_2, client_3][i % 3],
                        client_name=["Dedeman SRL", "Autonom Distribution", "Praktiker Romania"][i % 3],
                        driver_name=driver_names[i], driver_id=driver_ids[i],
                        truck_number=([owned_plates + leased_plates][0][i]),
                        truck_id=truck_ids[i],
                        distance_km=400 + i * 100, total_price_eur=1200 + i * 300,
                        status=["Planned", "Loading", "In Transit", "Delivered", "Invoiced"][i],
                        start_date=f"2026-07-{(20+i):02d}", end_date=f"2026-07-{(23+i):02d}")
        trip_ids.append(tid)

    return {
        "company_id": company_id, "user_id": user_id,
        "driver_ids": driver_ids, "truck_ids": truck_ids,
        "client_ids": [client_1, client_2, client_3],
        "trip_ids": trip_ids,
        "owned_truck_ids": truck_ids[:3], "leased_truck_ids": truck_ids[3:],
    }
