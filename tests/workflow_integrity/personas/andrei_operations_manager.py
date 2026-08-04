"""Persona: Andrei — operations manager for a 25-truck fleet.

Scale: 1 company (enterprise tier), 25 trucks, 30 drivers,
2 dispatchers, 1 accountant, 1 ops manager, 1 mechanic.
"""

from __future__ import annotations

from .fixtures import seed_client, seed_company, seed_driver, seed_trip, seed_truck, seed_user


def build_andrei_persona(db):
    """Seed the database with the Andrei operations manager persona."""
    company_id = seed_company(db, company_name="Andrei Fleet Management SA", subscription_tier="enterprise")

    ops_mgr_id = seed_user(db, company_id=company_id, email="andrei@fleet.ro",
                           role="dispatcher", display_name="Andrei Georgescu")
    disp1_id = seed_user(db, company_id=company_id, email="disp1@fleet.ro",
                         role="dispatcher", display_name="Diana Dispecer")
    disp2_id = seed_user(db, company_id=company_id, email="disp2@fleet.ro",
                         role="dispatcher", display_name="Florin Dispecer")
    acc_id = seed_user(db, company_id=company_id, email="contab@fleet.ro",
                       role="dispatcher", display_name="Elena Contabil")
    mech_id = seed_user(db, company_id=company_id, email="mecanic@fleet.ro",
                        role="dispatcher", display_name="Sorin Mecanic")

    driver_ids = []
    for i in range(1, 31):
        did = seed_driver(db, company_id=company_id, name=f"Driver A-{i:02d}",
                          license_number=f"RO-AND-{i:03d}")
        driver_ids.append(did)

    brands = ["Volvo"] * 8 + ["Mercedes"] * 8 + ["Scania"] * 5 + ["MAN"] * 4
    truck_ids = []
    for i in range(1, 26):
        tid = seed_truck(db, plate_number=f"B-{500+i}-AND", manufacturer=brands[i-1],
                         model="FH 500" if brands[i-1] == "Volvo" else "",
                         year=2021 + (i % 4), mileage=50000 + i * 15000,
                         company_id=company_id)
        truck_ids.append(tid)

    client_names = ["Lidl Romania", "Carrefour", "Profi", "Mega Image",
                    "eMAG", "Altex", "Dedeman", "Hornbach", "Brico Depot", "IKEA"]
    client_ids = [seed_client(db, name=n) for n in client_names]

    statuses = (["Planned"] * 8 + ["Loading"] * 6 + ["In Transit"] * 10 + ["Delivered"] * 8 + ["Invoiced"] * 5 + ["Paid"] * 3)
    trip_ids = []
    for i in range(40):
        tid = seed_trip(db, company_id=company_id, client_id=client_ids[i % 10],
                        client_name=client_names[i % 10],
                        driver_name=f"Driver A-{(i % 30) + 1:02d}",
                        driver_id=driver_ids[i % 30],
                        truck_number=f"B-{500 + (i % 25) + 1}-AND",
                        truck_id=truck_ids[i % 25],
                        distance_km=250 + i * 30, total_price_eur=800 + i * 100,
                        status=statuses[i], start_date=f"2026-07-{(5 + i // 2):02d}",
                        end_date=f"2026-07-{(8 + i // 2):02d}")
        trip_ids.append(tid)

    return {
        "company_id": company_id,
        "user_ids": {"ops_manager": ops_mgr_id, "dispatcher_1": disp1_id,
                     "dispatcher_2": disp2_id, "accountant": acc_id, "mechanic": mech_id},
        "driver_ids": driver_ids, "truck_ids": truck_ids, "client_ids": client_ids,
        "trip_ids": trip_ids,
    }
