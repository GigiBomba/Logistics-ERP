"""Persona: Ionut Popescu — single driver with mobile-only access.

Scale: 1 company, 1 driver, 1 truck, 2 clients, 3 trips (Planned,
In Transit, Delivered).

Represents the mobile-first user who monitors trips via the app,
updates statuses from the road, and submits delivery confirmations.
"""

from __future__ import annotations

from .fixtures import seed_client, seed_company, seed_driver, seed_trip, seed_truck, seed_user


def build_ionut_persona(db):
    """Seed the database with the Ionut driver persona.

    Returns a dict of entity IDs so tests can reference seeded rows.
    """
    company_id = seed_company(db, company_name="Ionut Transport SRL", subscription_tier="starter")

    user_id = seed_user(db, company_id=company_id, email="ionut@transport.ro",
                        role="driver", display_name="Ionut Popescu", password="driver123")

    driver_id = seed_driver(db, company_id=company_id, name="Ionut Popescu",
                            license_number="RO-000001", phone="+40-722-123-456",
                            email="ionut@transport.ro", user_id=user_id)

    truck_id = seed_truck(db, plate_number="CJ-01-ION", manufacturer="MAN",
                          model="TGX 18.510", year=2023, mileage=45000,
                          company_id=company_id)

    client_1 = seed_client(db, name="Transilvania Fresh SRL",
                           email="office@transilvaniafresh.ro", phone="+40-264-123-456",
                           address="Str. Fabricii 12, Cluj-Napoca")
    client_2 = seed_client(db, name="Moldova Logistics SA",
                           email="contact@moldovalogistics.ro", phone="+40-232-654-321",
                           address="Bd. Stefan cel Mare 45, Iasi")

    trip_planned = seed_trip(db, company_id=company_id, client_id=client_1,
                             client_name="Transilvania Fresh SRL", driver_name="Ionut Popescu",
                             driver_id=driver_id, truck_number="CJ-01-ION", truck_id=truck_id,
                             distance_km=320.0, total_price_eur=980.0, status="Planned",
                             start_date="2026-07-22", end_date="2026-07-23")

    trip_in_transit = seed_trip(db, company_id=company_id, client_id=client_2,
                                 client_name="Moldova Logistics SA", driver_name="Ionut Popescu",
                                 driver_id=driver_id, truck_number="CJ-01-ION", truck_id=truck_id,
                                 distance_km=680.0, total_price_eur=1850.0, status="In Transit",
                                 start_date="2026-07-20", end_date="2026-07-22")

    trip_delivered = seed_trip(db, company_id=company_id, client_id=client_1,
                                client_name="Transilvania Fresh SRL", driver_name="Ionut Popescu",
                                driver_id=driver_id, truck_number="CJ-01-ION", truck_id=truck_id,
                                distance_km=150.0, total_price_eur=450.0, status="Delivered",
                                start_date="2026-07-15", end_date="2026-07-16")

    return {
        "company_id": company_id,
        "user_id": user_id,
        "driver_id": driver_id,
        "truck_id": truck_id,
        "client_ids": [client_1, client_2],
        "trip_ids": {
            "planned": trip_planned,
            "in_transit": trip_in_transit,
            "delivered": trip_delivered,
        },
    }
