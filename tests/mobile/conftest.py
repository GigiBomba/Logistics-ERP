"""Shared fixtures for mobile API tests.

Reuses the ``app`` fixture from ``tests/test_api/conftest.py`` (a minimal
FastAPI app with the v1 router) and follows its auth-override pattern
exactly.  Provides role-scoped test users and TestClients:

  - ``dispatcher_user`` / ``manager_user`` / ``admin_user`` — mock_user-shaped
    dicts with the matching role / is_admin.
  - ``dispatcher_client`` / ``manager_client`` / ``admin_client`` — TestClient
    with ``get_current_user`` overridden to the respective user (same pattern
    as ``tests/test_api/conftest.py::client``).
  - ``mobile_client`` — TestClient with ALL auth dependencies overridden
    (``get_current_user`` + ``require_dispatcher`` / ``require_manager`` /
    ``require_admin``) to the dispatcher user, so endpoint tests can rely on
    either dependency regardless of the guard used.
"""
from __future__ import annotations

import pytest

from tests.test_api.conftest import app  # noqa: F401  (re-exported)

_COMPANY_ID = 1


def _role_user(user_id: int, email: str, role: str, is_admin: bool) -> dict:
    """Build a ``mock_user``-shaped user dict for a given role."""
    return {
        "id": user_id,
        "email": email,
        "role": role,
        "is_admin": is_admin,
        "company_id": _COMPANY_ID,
    }


@pytest.fixture
def dispatcher_user() -> dict:
    return _role_user(2, "dispatcher@test.com", "dispatcher", is_admin=False)


@pytest.fixture
def manager_user() -> dict:
    return _role_user(3, "manager@test.com", "manager", is_admin=False)


@pytest.fixture
def admin_user() -> dict:
    return _role_user(1, "admin@test.com", "admin", is_admin=True)


def _override_auth(app, user: dict, *, require_gates: bool) -> None:
    """Override auth dependencies on *app* following the test_api pattern."""
    from backend.dependencies_security import (
        get_current_user,
        require_admin,
        require_dispatcher,
        require_manager,
    )

    app.dependency_overrides[get_current_user] = lambda: user
    if require_gates:
        app.dependency_overrides[require_dispatcher] = lambda: user
        app.dependency_overrides[require_manager] = lambda: user
        app.dependency_overrides[require_admin] = lambda: user


@pytest.fixture
def dispatcher_client(app, dispatcher_user):
    """TestClient authenticated as a dispatcher (get_current_user overridden)."""
    from fastapi.testclient import TestClient

    _override_auth(app, dispatcher_user, require_gates=False)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def manager_client(app, manager_user):
    """TestClient authenticated as a manager (get_current_user overridden)."""
    from fastapi.testclient import TestClient

    _override_auth(app, manager_user, require_gates=False)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(app, admin_user):
    """TestClient authenticated as an admin (get_current_user overridden)."""
    from fastapi.testclient import TestClient

    _override_auth(app, admin_user, require_gates=False)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def mobile_client(app, dispatcher_user):
    """TestClient with ALL auth dependencies overridden to the dispatcher user.

    Overrides ``get_current_user`` plus ``require_dispatcher`` /
    ``require_manager`` / ``require_admin`` so endpoint tests can rely on
    either dependency without being blocked by the guard.
    """
    from fastapi.testclient import TestClient

    _override_auth(app, dispatcher_user, require_gates=True)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ── Real-DB fixtures (Phase 1A) ─────────────────────────────────────────
# The record endpoints hit the actual repositories/DB (like the legacy
# mobile.py endpoints), so these fixtures provide a real, file-backed SQLite
# DatabaseManager with the full schema and the role users that the
# PermissionService decision logic looks up.


@pytest.fixture
def driver_user() -> dict:
    return _role_user(4, "driver@test.com", "driver", is_admin=False)


@pytest.fixture
def driver_client(app, driver_user):
    """TestClient authenticated as a driver with ALL auth gates overridden.

    Overriding the ``require_*`` gates as well means a 403 can only come from
    the endpoint's own PermissionService gate (RBAC matrix tests rely on this).
    """
    from fastapi.testclient import TestClient

    _override_auth(app, driver_user, require_gates=True)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def real_db(tmp_path):
    """File-backed SQLite DatabaseManager with full schema + companies + role users.

    A FILE (not ``:memory:``) is required because FastAPI ``def`` endpoints run
    on worker threads with their own thread-local sqlite connections; an
    in-memory DB would be a separate, empty database per thread.
    """
    from database.db_manager import DatabaseManager

    db = DatabaseManager(str(tmp_path / "mobile_test.db"))

    # Seed companies 0..100 so company_id FKs never block inserts.
    for cid in range(0, 101):
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
            "VALUES (?, ?, 'starter')",
            (cid, f"Company-{cid}"),
        )

    # Seed the role users the PermissionService._get_user lookup needs.
    for uid, email, role in (
        (1, "admin@test.com", "admin"),
        (2, "dispatcher@test.com", "dispatcher"),
        (3, "manager@test.com", "manager"),
        (4, "driver@test.com", "driver"),
    ):
        db.conn.execute(
            "INSERT OR IGNORE INTO users (id, email, password_hash, role, company_id, is_active, display_name) "
            "VALUES (?, ?, 'test-hash', ?, 1, 1, ?)",
            (uid, email, role, role),
        )
    db.conn.commit()
    yield db
    db.close()


@pytest.fixture
def mobile_app(app, real_db):
    """``app`` with the ``get_db`` dependency overridden to the real DB."""
    from backend.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: real_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _mobile_export_env(tmp_path_factory, monkeypatch):
    """Run Celery export tasks eagerly (in-process) + redirect exports to a temp dir.

    ``task_always_eager=True`` makes the history export POST execute its job
    synchronously inside the request, so tests observe the terminal job state
    without a broker.  ``OPERION_EXPORT_DIR`` redirects ``BackendSettings``
    export-dir resolution (and the Celery task's) away from the repo's
    ``data/exports``.  ``OPERION_TACHO_UPLOAD_DIR`` redirects tacho uploads.
    """
    from backend.celery_app.celery import celery_app

    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", False)
    monkeypatch.setenv("OPERION_EXPORT_DIR", str(tmp_path_factory.mktemp("mobile_exports")))
    monkeypatch.setenv("OPERION_TACHO_UPLOAD_DIR", str(tmp_path_factory.mktemp("tacho_uploads")))


# ── Phase 2A: record seeding for analytics / history / search tests ──────
# Deterministic fixture data spread across companies 1 (primary) and 2
# (isolation checks): trucks, drivers, clients, trips (across statuses and
# dates) and invoices (unpaid/paid with bucketed due dates).

_TODAY = __import__("datetime").date.today()


def seed_records(db, company_id: int = 1) -> dict:
    """Insert a fixed set of trucks/drivers/clients/trips/invoices.

    Returns the created primary keys so tests can assert on specifics.
    """
    from datetime import date, timedelta

    today = date.today()
    ids = {}

    # ── Trucks ──
    # trucks.plate_number is UNIQUE globally → other-company seeds need
    # distinct plates.
    plate_prefix = "AB" if company_id == 1 else f"OT{company_id}"
    trucks = [
        (f"{plate_prefix}-01-XYZ", "Volvo", "FH", "Active"),
        (f"{plate_prefix}-02-XYZ", "Scania", "R450", "In Service"),
        (f"{plate_prefix}-03-XYZ", "Mercedes", "Actros", "Inactive"),
    ]
    for plate, brand, model, status in trucks:
        cur = db.execute(
            "INSERT INTO trucks (plate_number, manufacturer, model, status, "
            "year, vin, active_status, company_id) VALUES (?, ?, ?, ?, 2022, ?, 1, ?)",
            (plate, brand, model, status, f"VIN-{plate}", company_id),
        )
        ids[f"truck_{plate}"] = cur.lastrowid

    # ── Drivers ──
    drivers = [
        ("Ion Popescu", "LIC-A", "0720000001"),
        ("Maria Ionescu", "LIC-B", "0720000002"),
    ]
    for name, lic, phone in drivers:
        cur = db.execute(
            "INSERT INTO drivers (name, phone, license_number, license_category, "
            "is_active, company_id, created_at, updated_at) "
            "VALUES (?, ?, ?, 'C', 1, ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
            (name, phone, lic, company_id),
        )
        ids[f"driver_{name}"] = cur.lastrowid

    # ── Clients ──
    clients = [
        ("ACME Corp", "RO12345"),
        ("Globex Ltd", "RO67890"),
    ]
    for name, vat in clients:
        cur = db.execute(
            "INSERT INTO clients (name, vat_number, contact_person, phone, email, "
            "address, currency_preference, notes, is_active, created_at, updated_at, "
            "client_type, payment_terms_days, credit_limit_eur, rating, company_id) "
            "VALUES (?, ?, 'P', '0700000000', ?, 'Addr', 'EUR', '', 1, "
            "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', '', 30, 0, 4, ?)",
            (name, vat, f"{name.lower().replace(' ', '')}@test.com", company_id),
        )
        ids[f"client_{name}"] = cur.lastrowid

    # ── Trips across statuses / dates / clients ──
    driver_a = ids["driver_Ion Popescu"]
    driver_b = ids["driver_Maria Ionescu"]
    client_a = ids["client_ACME Corp"]
    client_b = ids["client_Globex Ltd"]
    truck_a = ids[f"truck_{plate_prefix}-01-XYZ"]
    truck_b = ids[f"truck_{plate_prefix}-02-XYZ"]
    truck_c = ids[f"truck_{plate_prefix}-03-XYZ"]
    t1 = _insert_trip(db, company_id, client_a, "ACME Corp", driver_a, "Ion Popescu",
                      f"{plate_prefix}-01-XYZ", truck_id=truck_a, status="Delivered",
                      start=(today - timedelta(days=40)).isoformat(),
                      end=(today - timedelta(days=38)).isoformat(),
                      promised=(today - timedelta(days=38)).isoformat(),  # on-time
                      origin="Bucharest", dest="Vienna", km=900, price=2200, profit=350)
    t2 = _insert_trip(db, company_id, client_a, "ACME Corp", driver_a, "Ion Popescu",
                      f"{plate_prefix}-02-XYZ", truck_id=truck_b, status="Paid",
                      start=(today - timedelta(days=20)).isoformat(),
                      end=(today - timedelta(days=18)).isoformat(),
                      promised=(today - timedelta(days=19)).isoformat(),  # late
                      origin="Bucharest", dest="Budapest", km=600, price=1500, profit=180)
    t3 = _insert_trip(db, company_id, client_b, "Globex Ltd", driver_b, "Maria Ionescu",
                      f"{plate_prefix}-01-XYZ", truck_id=truck_a, status="Planned",
                      start=(today + timedelta(days=5)).isoformat(),
                      end=None, promised=None,
                      origin="Cluj", dest="Paris", km=1800, price=4200, profit=None)
    t4 = _insert_trip(db, company_id, client_b, "Globex Ltd", driver_b, "Maria Ionescu",
                      f"{plate_prefix}-03-XYZ", truck_id=truck_c, status="Cancelled",
                      start=(today - timedelta(days=3)).isoformat(),
                      end=None, promised=None,
                      origin="Iasi", dest="Chisinau", km=250, price=400, profit=-40)
    ids["trip_1"], ids["trip_2"], ids["trip_3"], ids["trip_4"] = t1, t2, t3, t4

    # ── Invoices (unpaid across aging buckets + paid) ──
    # Each invoice needs its own trip (invoices.trip_id is UNIQUE); invoice
    # numbers are UNIQUE globally → company-aware.  Carrier trips are
    # analytics-neutral (price 0, dedicated truck/driver).
    carrier_specs = [
        (f"INV-{company_id}-CUR", today - timedelta(days=10), 500.0),
        (f"INV-{company_id}-31-60", today - timedelta(days=45), 300.0),
        (f"INV-{company_id}-61-90", today - timedelta(days=75), 200.0),
        (f"INV-{company_id}-OVD", today - timedelta(days=110), 100.0),
        (f"INV-{company_id}-PAID", today - timedelta(days=15), 999.0),
    ]
    carriers = {}
    for idx, (number, due, amount) in enumerate(carrier_specs):
        status = "Paid" if number.endswith("-PAID") else "Unpaid"
        carrier_trip = _insert_trip(
            db, company_id, None, "Carrier Corp", None, "Carrier Driver",
            "AB-CARRIER", status="Delivered",
            start=(today - timedelta(days=30)).isoformat(),
            end=(today - timedelta(days=28)).isoformat(),
            promised=(today - timedelta(days=28)).isoformat(),
            origin="Bucharest", dest="Sofia", km=0, price=0, profit=0,
        )
        carriers[number] = carrier_trip
        db.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
            "total_amount, status, company_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (carrier_trip, number,
             (due - timedelta(days=10)).isoformat(), due.isoformat(), amount,
             status, company_id),
        )
    ids["invoice_carriers"] = carriers
    db.conn.commit()
    return ids


def _insert_trip(db, company_id, client_id, client_name, driver_id, driver_name,
                 truck_number, *, status, start, end, promised, origin, dest,
                 km, price, profit, truck_id=None):
    cur = db.execute(
        "INSERT INTO trips (company_id, client_id, client_name, driver_id, driver_name, "
        "truck_number, truck_id, status, start_date, end_date, promised_date, "
        "place_of_loading, delivery_country, distance_km, total_price_eur, "
        "net_profit, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (company_id, client_id, client_name, driver_id, driver_name, truck_number,
         truck_id, status, start, end, promised, origin, dest, km, price, profit,
         start),
    )
    return cur.lastrowid


@pytest.fixture
def records_seed(real_db):
    """Seed the standard analytics/history/search record set (company 1)."""
    return seed_records(real_db, company_id=1)


def _insert_client(db, name: str, *, company_id: int = 1, vat: str = "RO-T") -> int:
    """Insert a single client row (search/LIKE-escaping tests)."""
    cur = db.execute(
        "INSERT INTO clients (name, vat_number, contact_person, phone, email, "
        "address, currency_preference, notes, is_active, created_at, updated_at, "
        "client_type, payment_terms_days, credit_limit_eur, rating, company_id) "
        "VALUES (?, ?, 'P', '0700000000', 'c@t.com', 'Addr', 'EUR', '', 1, "
        "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', '', 30, 0, 4, ?)",
        (name, vat, company_id),
    )
    db.conn.commit()
    return cur.lastrowid


# ── Phase 3A: finance seeding (invoices + maintenance) ────────────────────
# Deterministic invoice rows across the REAL status machine (draft / finalized /
# paid / cancelled / accepted / xml_generated) with line_items_json computed by
# the REAL desktop calculator, plus maintenance schedules/records for the
# schedule-list + cost-trend endpoints.

_INVOICE_VECTORS = None


def _vector_input(index: int) -> dict:
    """Return the input payload of one committed invoice-calculation vector."""
    global _INVOICE_VECTORS
    import json
    import os

    if _INVOICE_VECTORS is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "shared", "test_vectors", "invoice_calculations.json",
        )
        with open(path, encoding="utf-8") as fh:
            _INVOICE_VECTORS = json.load(fh)
    return dict(_INVOICE_VECTORS[index]["input"])


def _calc_line_items(items):
    """Compute line totals through the REAL desktop calculator (no reimplementation)."""
    from services.invoicing.service import InvoiceService

    return InvoiceService(None)._calculate_line_items(items)


def _insert_invoice(db, company_id: int, client_id: int, trip_id, number: str,
                    status: str, line_items=None, *, issue_offset_days=5,
                    due_offset_days=25, notes: str = "") -> int:
    """Insert an invoice row; totals/line_items_json always via the REAL calc."""
    from datetime import date, timedelta

    import json as _json

    from models.invoice_models import InvoiceLineItem

    issue = (date.today() - timedelta(days=issue_offset_days)).isoformat()
    due = (date.today() + timedelta(days=due_offset_days)).isoformat()
    if line_items is None:
        line_items = [InvoiceLineItem(**_vector_input(0))]
    calc_items, net, vat, gross = _calc_line_items(line_items)
    line_items_json = _json.dumps([li.model_dump() for li in calc_items])
    cur = db.execute(
        "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
        "status, company_id, client_id, currency, notes, line_items_json, "
        "subtotal_net, total_vat, total_gross, total_amount, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'EUR', ?, ?, ?, ?, ?, ?, ?, ?)",
        (trip_id, number, issue, due, status, company_id, client_id, notes,
         line_items_json, net, vat, gross, gross,
         (date.today()).isoformat() + "T00:00:00Z", (date.today()).isoformat() + "T00:00:00Z"),
    )
    db.conn.commit()
    return cur.lastrowid


def seed_finance(db, company_id: int = 1) -> dict:
    """Seed maintenance schedules/records + invoices across the status machine.

    Returns the created ids (schedules, invoice ids, maintenance record ids).
    """
    from datetime import date, timedelta

    today = date.today()
    ids: dict = {}

    # ── Truck mileage so km-based overdue is deterministic (truck 1 only) ──
    trucks = [dict(r) for r in db.execute(
        "SELECT id, plate_number FROM trucks WHERE company_id = ? ORDER BY id",
        (company_id,),
    ).fetchall()]
    assert len(trucks) >= 2, "seed_finance needs the seed_records trucks"
    t1, t2 = trucks[0], trucks[1]
    db.execute("UPDATE trucks SET mileage = 200000 WHERE id = ?", (t1["id"],))

    # ── Maintenance schedules (3 overdue + 2 not) ──
    schedules = [
        # (truck, type, interval_km, interval_months, fixed_expiry, last_done_km, last_done_date)
        (t1["id"], "Oil Change", None, 3, None, None, (today - timedelta(days=200)).isoformat()),          # overdue (months)
        (t1["id"], "Tire Rotation", None, 12, None, None, (today - timedelta(days=30)).isoformat()),       # not overdue
        (t2["id"], "Inspection", None, None, (today - timedelta(days=5)).isoformat(), None, None),         # overdue (fixed)
        (t2["id"], "Brakes", 50000, None, None, 5000.0, None),                                             # not overdue (km)
        (t1["id"], "Gearbox", 50000, None, None, 100000.0, None),                                          # overdue (km: 200k >= 150k)
    ]
    for idx, (truck_id, mtype, km, months, fixed, last_km, last_date) in enumerate(schedules, start=1):
        cur = db.execute(
            "INSERT INTO maintenance_schedules (truck_id, maintenance_type, interval_km, "
            "interval_months, fixed_expiry_date, last_done_km, last_done_date, active, "
            "created_at, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (truck_id, mtype, km, months, fixed, last_km, last_date,
             datetime_utcnow(), company_id),
        )
        ids[f"schedule_{idx}"] = cur.lastrowid

    # ── Maintenance records for cost-trend (2 Oil Change, Brakes, Tires) ──
    records = [
        (t1["id"], "Oil Change", today - timedelta(days=30), 300.0),
        (t1["id"], "Brakes", today - timedelta(days=10), 1500.0),
        (t2["id"], "Oil Change", today - timedelta(days=5), 250.0),
        (t2["id"], "Tires", today - timedelta(days=60), 900.0),
        (t1["id"], "Oil Change", today - timedelta(days=400), 200.0),  # outside default 1y window
    ]
    for idx, (truck_id, mtype, rec_date, cost) in enumerate(records, start=1):
        cur = db.execute(
            "INSERT INTO maintenance_records (truck_id, maintenance_type, date, cost, "
            "notes, created_at, company_id) VALUES (?, ?, ?, ?, '', ?, ?)",
            (truck_id, mtype, rec_date.isoformat(), cost, rec_date.isoformat(), company_id),
        )
        ids[f"record_{idx}"] = cur.lastrowid

    # ── Invoices across the REAL status machine ──
    client_a = db.execute("SELECT id FROM clients WHERE company_id = ? ORDER BY id LIMIT 1", (company_id,)).fetchone()
    client_b = db.execute("SELECT id FROM clients WHERE company_id = ? ORDER BY id LIMIT 1 OFFSET 1", (company_id,)).fetchone()
    # seed_records already attaches invoices to its client-less carrier trips,
    # so create two FRESH trips for the accepted / xml invoice rows.
    client_trips = [dict(r) for r in db.execute(
        "SELECT id FROM trips WHERE company_id = ? AND client_id IS NOT NULL ORDER BY id", (company_id,),
    ).fetchall()]
    assert len(client_trips) >= 4, "seed_finance needs seed_records client trips"
    assert client_a and client_b

    def _extra_trip(num: int) -> int:
        cur = db.execute(
            "INSERT INTO trips (company_id, client_id, client_name, driver_id, driver_name, "
            "truck_number, status, start_date, end_date, promised_date, place_of_loading, "
            "delivery_country, distance_km, total_price_eur, net_profit, created_at) "
            "VALUES (?, NULL, 'Fin Carrier', NULL, 'Fin Driver', ?, 'Delivered', ?, ?, ?, "
            "'Bucharest', 'Munich', 1200, 0, 0, ?)",
            (company_id, f"FIN-CARRIER-{num}", today.isoformat(), today.isoformat(),
             today.isoformat(), today.isoformat()),
        )
        db.conn.commit()
        return cur.lastrowid

    extra_trip_a = _extra_trip(1)
    extra_trip_b = _extra_trip(2)

    from models.invoice_models import InvoiceLineItem

    draft_items = [InvoiceLineItem(**_vector_input(0))]                      # 370.35 / 70.37 / 440.72
    finalized_items = [InvoiceLineItem(**_vector_input(1))]                  # 950.00 / 180.50 / 1130.50
    paid_items = [InvoiceLineItem(**_vector_input(2))]                       # 319.69 / 0.00 / 319.69
    cancelled_items = [InvoiceLineItem(**_vector_input(3))]                  # 199.98 / 18.00 / 217.98
    xml2_items = [InvoiceLineItem(**_vector_input(4))]                       # 79.96 / 4.00 / 83.96
    xml_items = [InvoiceLineItem(**_vector_input(5))]                        # 100% discount → 0.00

    prefix = f"INV{company_id}"
    ids["invoice_draft"] = _insert_invoice(
        db, company_id, client_a["id"], client_trips[0]["id"], f"{prefix}-SEED-DRAFT", "draft", draft_items, notes="seed draft")
    ids["invoice_finalized"] = _insert_invoice(
        db, company_id, client_a["id"], client_trips[1]["id"], f"{prefix}-SEED-FINALIZED", "finalized", finalized_items)
    ids["invoice_paid"] = _insert_invoice(
        db, company_id, client_b["id"], client_trips[2]["id"], f"{prefix}-SEED-PAID", "paid", paid_items)
    ids["invoice_cancelled"] = _insert_invoice(
        db, company_id, client_b["id"], client_trips[3]["id"], f"{prefix}-SEED-CANCELLED", "cancelled", cancelled_items)
    # A second xml_generated invoice (the removed ANAF 'accepted' seed now maps
    # onto the legal machine — xml_generated is the pre-paid legal state).
    ids["invoice_xml2"] = _insert_invoice(
        db, company_id, client_b["id"], extra_trip_a, f"{prefix}-SEED-XML2", "xml_generated", xml2_items)
    ids["invoice_xml"] = _insert_invoice(
        db, company_id, client_a["id"], extra_trip_b, f"{prefix}-SEED-XML", "xml_generated", xml_items)
    ids["invoice_empty"] = _insert_invoice(
        db, company_id, client_a["id"], None, f"{prefix}-SEED-EMPTY", "draft", line_items=None)
    # line_items=None above computes vector(0); force empty for the empty-items case
    db.execute("UPDATE invoices SET line_items_json = '[]', subtotal_net = 0, total_vat = 0, "
               "total_gross = 0, total_amount = 0 WHERE id = ?", (ids["invoice_empty"],))
    db.conn.commit()

    ids["trucks"] = [t["id"] for t in trucks]
    ids["client_a"] = client_a["id"]
    ids["client_b"] = client_b["id"]
    return ids


def datetime_utcnow() -> str:
    from datetime import datetime

    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


@pytest.fixture
def finance_seed(real_db):
    """Seed the standard record set + finance data (company 1)."""
    base = seed_records(real_db, company_id=1)
    fin = seed_finance(real_db, company_id=1)
    return {**base, **fin}


# ── Phase 4A: team / settings / tacho seeding ──────────────────────────────


def seed_team(db, company_id: int = 1) -> dict:
    """Seed extra team members (non-role users) + mobile_devices rows.

    The role users (ids 1-4) come from the ``real_db`` fixture; this adds a
    plain dispatcher invitee and a linked-driver manager so team-list, invite
    and PATCH tests have non-admin targets, plus mobile_devices rows for the
    deactivation-cascade test.

    ``users.email`` is UNIQUE globally, so company-2 seeds use company-scoped
    email suffixes (the company isolation tests rely on this).
    """
    ids: dict = {}
    suffix = "" if company_id == 1 else f".c{company_id}"

    # An invitee (created via the endpoint in most tests; seeded here for
    # PATCH/list tests that need a pre-existing non-role member).
    cur = db.execute(
        "INSERT INTO users (email, password_hash, role, company_id, "
        "display_name, is_active) VALUES (?, ?, ?, ?, ?, 1)",
        (f"invitee{suffix}@test.com", "test-hash", "dispatcher", company_id, "Invitee"),
    )
    ids["invitee_user"] = cur.lastrowid

    cur = db.execute(
        "INSERT INTO users (email, password_hash, role, company_id, "
        "display_name, is_active) VALUES (?, ?, ?, ?, ?, 1)",
        (f"manager2{suffix}@test.com", "test-hash", "manager", company_id, "Manager Two"),
    )
    ids["manager2_user"] = cur.lastrowid

    # mobile_devices rows (one for invitee, one for manager2) so the
    # deactivation cascade has rows to delete.
    for user_id, device_id in (
        (ids["invitee_user"], f"DEV-INV-1{suffix}"),
        (ids["manager2_user"], f"DEV-MGR-2{suffix}"),
    ):
        db.execute(
            "INSERT INTO mobile_devices (user_id, company_id, device_id, "
            "device_name, token, platform, is_active) "
            "VALUES (?, ?, ?, 'Test Phone', 'tok', 'android', 1)",
            (user_id, company_id, device_id),
        )
        ids[f"device_{user_id}"] = device_id

    db.conn.commit()
    return ids


def seed_company_settings(db, company_id: int = 1) -> None:
    """Insert a fixed set of company settings rows (identity + SMTP + tracking
    + maintenance thresholds) under the tenant-scoped settings table.

    ``smtp_password`` and ``tracking.token`` are stored ENCRYPTED (via the
    REAL ``services.encryption_service``), mirroring production writes.
    """
    from services.encryption_service import encrypt_value

    rows = {
        "legal_name": "Operion Logistics SRL",
        "vat_number": "RO12345678",
        "address": "Str. Testului 1, Bucuresti",
        "invoice_footer": "Multumim pentru colaborare!",
        "smtp_server": "smtp.example.com",
        "smtp_port": "587",
        "smtp_user": "alerts@example.com",
        "smtp_password": encrypt_value("super-secret-smtp"),
        "tracking.platform": "Wialon / GPS-Trace (Gurtam)",
        "tracking.token": encrypt_value("wialon-api-token-123"),
        "alert_days_ahead": "30",
        "tacho_warning": "45",
        "tacho_critical": "15",
    }
    for key, value in rows.items():
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value, company_id) VALUES (?, ?, ?)",
            (key, value, company_id),
        )
    db.conn.commit()


# ── Phase 4A: tacho parser fixture JSON ────────────────────────────────────
# Shape understood by the REAL ``TachoService._process_driver_card``:
#   - driverCard.cardHolderName.holderSurname / holderFirstNames
#   - driverCard.cardNumber
#   - driverCard.activityDailyRecords[].activityRecordDate + activityChangeInfo[]
#     (activityType int enum: 0=driving, 1=work, 2=available, 3=rest)
# Day 1: driving 6h + work 2h + avail 3h + rest 13h  -> compliant.
# Day 2: driving 10h (violation: exceeds 9h) + rest 0 (violation: < 11h).
TACHO_CARD_FIXTURE = {
    "type": "CARD",
    "driverCard": {
        "cardHolderName": {"holderSurname": "POPESCU", "holderFirstNames": "ION"},
        "cardNumber": "RO-TACHO-FIXTURE-0001",
        "activityDailyRecords": [
            {
                "activityRecordDate": "2026-07-01",
                "activityChangeInfo": [
                    {"activityType": 0, "duration": 360},
                    {"activityType": 1, "duration": 120},
                    {"activityType": 2, "duration": 180},
                    {"activityType": 3, "duration": 780},
                ],
                "distanceDriven": 400,
            },
            {
                "activityRecordDate": "2026-07-02",
                "activityChangeInfo": [
                    {"activityType": 0, "duration": 600},
                ],
                "distanceDriven": 600,
            },
        ],
    },
}

# Day 1 driving (360) + day 2 driving (600) = 960 weekly minutes.
TACHO_FIXTURE_WEEKLY_MINUTES = 960
# Verbatim violation strings produced by the REAL _process_driver_card.
TACHO_FIXTURE_VIOLATIONS = [
    "Driving 10h0m exceeds 9h limit",
    "Daily rest period below 11 hours",
]
