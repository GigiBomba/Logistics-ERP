"""Golden-flow data factories — SQL-level row builders.

Each ``make_*`` function inserts one (or more) fresh row(s) into the
in-memory workflow DB and returns a ``dict`` of ids / derived values
that a golden-flow test can feed straight into a service or repository
call.  Calling a factory twice always produces *new* rows: every
marker value (external id, doc number, plate, file hash…) is drawn from
a module-level counter so nothing collides on UNIQUE columns.

All factories are thin SQL seed helpers in the same style as
``tests/workflow_integrity/personas/fixtures.py`` — they do not route
through services, so they emit no domain events.  Tests that assert on
events should keep creating trips/documents through ``workflow_env`` /
``DocumentService`` and use these factories for the surrounding state.

Domain mapping (verified against the live schema at runtime):
    * A *lead* is an accepted freight offer that immediately becomes a
      ``trips`` row in ``Planned`` state carrying the external id in
      ``source_reference_id`` (migration ``add_trips_source_columns``)
      plus route hints (loading/delivery country).  Economics stay NULL
      until ``make_route`` prices the route.
    * A *freight-exchange load* is a ``trips`` row flagged
      ``source='freight_exchange'`` (shape used by
      ``test_freight_exchange_import.py``).
    * A *maintenance ticket* is a ``maintenance_records`` row plus a
      ``maintenance`` alert carrying the severity (the alert is what the
      dispatch block actually reads).
"""

from __future__ import annotations

import itertools
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

_NOW = datetime.now().isoformat()
_DAY_ISO = date.today().isoformat()
_seq = itertools.count(1)


# ── Small helpers ──────────────────────────────────────────────────────────

def _next() -> int:
    """Next monotonically-increasing sequence number (per process)."""
    return next(_seq)


def _insert(db, table: str, fields: dict[str, Any]) -> int:
    """Insert one row built from ``fields`` (key = column name).

    Only keys that name real columns of ``table`` are written, so
    factories survive schema drift on optional columns.  Missing
    ``created_at`` / ``updated_at`` are defaulted only when the target
    table actually defines them.
    """
    existing = {
        row[1]
        for row in db.conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    data = dict(fields)
    for default_col in ("created_at", "updated_at"):
        if default_col in existing and default_col not in data:
            data[default_col] = _NOW
    data = {k: v for k, v in data.items() if k in existing}
    cols = ", ".join(data)
    marks = ", ".join("?" for _ in data)
    db.conn.execute(
        f"INSERT INTO {table} ({cols}) VALUES ({marks})",
        tuple(data.values()),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _row(db, table: str, row_id: int) -> dict[str, Any] | None:
    """Fetch one row by integer primary key as a dict (or None)."""
    row = db.conn.execute(
        f"SELECT * FROM {table} WHERE id = ?", (row_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def _client_name(db, client_id: int) -> str:
    """Resolve a client's display name (fallback id-based label)."""
    row = db.conn.execute(
        "SELECT name FROM clients WHERE id = ?", (client_id,)
    ).fetchone()
    return (row["name"] if row else None) or f"Client-{client_id}"


# ── Lead → Route → Trip ───────────────────────────────────────────────────
# Known-value profile used by test_full_trip_lifecycle at 450 km:
# price 1350 €, fuel 135 €, toll 45 €, salary 275 €, extra 25 €,
# net_profit 870 €, rate_per_km 3.00, gross_per_km 1.93.

_PRICE_PER_KM = 3.00
_FUEL_PER_KM = 0.30      # 450 km → 135 €
_TOLL_PER_KM = 0.10      # 450 km →  45 €
_SALARY_COST = 275.0     # flat driver wage share
_EXTRA_COSTS = 25.0      # flat incidental costs


def make_lead(db, client_id: int, *,
              loading_country: str = "DE", delivery_country: str = "RO",
              origin: str = "Frankfurt am Main, DE",
              destination: str = "Bucharest, RO",
              external_id: str | None = None,
              **overrides: Any) -> dict[str, Any]:
    """Create a lead: a ``Planned`` trip row with route hints, no economics.

    Mirrors the "create trip from lead" step of
    ``test_full_trip_lifecycle``: the accepted lead materialises as a
    Planned trip, the external freight reference is stored in
    ``source_reference_id`` and route hints in the country columns.
    Costs stay NULL until ``make_route`` prices the route.

    Returns a dict with ``lead_id``/``trip_id``/``id``, ``client_id``,
    ``external_id`` and the route hints.
    """
    ext = external_id or f"LEAD-{_next():06d}"
    fields = {
        "client_id": client_id,
        "client_name": _client_name(db, client_id),
        "status": "Planned",
        "currency": "EUR",
        "source": "lead",
        "source_reference_id": ext,
        "loading_country": loading_country,
        "delivery_country": delivery_country,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    fields.update(overrides)
    lead_id = _insert(db, "trips", fields)
    return {
        "id": lead_id,
        "lead_id": lead_id,
        "trip_id": lead_id,
        "client_id": client_id,
        "external_id": ext,
        "status": fields["status"],
        "loading_country": loading_country,
        "delivery_country": delivery_country,
        "origin": origin,
        "destination": destination,
    }


def make_route(db, lead: dict[str, Any], distance_km: float = 450.0,
               **overrides: Any) -> dict[str, Any]:
    """Price a route for a lead at ``distance_km`` (default 450 km).

    Inserts one ``routes`` row (start/destination from the lead's route
    hints) and one ``route_history`` row carrying the cost estimates.
    Economics follow the known-value 450 km profile from
    ``test_full_trip_lifecycle`` and stay internally consistent for any
    distance::

        price   = distance_km * 3.00     (450 → 1350 €)
        fuel    = distance_km * 0.30     (450 →  135 €)
        toll    = distance_km * 0.10     (450 →   45 €)
        salary  = 275 €, extra = 25 €
        net     = price - fuel - toll - salary - extra   (450 → 870 €)

    When ``lead`` contains a real ``lead_id`` (i.e. the trip row created
    by :func:`make_lead`) the derived economics are also written back to
    that trip row so downstream dispatch / invoicing sees the profile.

    Returns a dict with ``route_id``, ``route_history_id``, ``trip_id``
    and the full financial breakdown.
    """
    price_eur = distance_km * _PRICE_PER_KM
    fuel_cost = round(distance_km * _FUEL_PER_KM, 2)
    toll_cost = round(distance_km * _TOLL_PER_KM, 2)
    salary_cost = _SALARY_COST
    extra_costs = _EXTRA_COSTS
    net_profit = round(price_eur - fuel_cost - toll_cost - salary_cost - extra_costs, 2)
    total_cost = round(fuel_cost + toll_cost + salary_cost + extra_costs, 2)
    duration_min = round(distance_km * 1.2)  # ≈ 50 km/h effective

    origin = str(lead.get("origin") or "Origin")
    destination = str(lead.get("destination") or "Destination")

    route_fields = {
        "name": f"Route {lead.get('external_id', _next())}",
        "start": origin,
        "destination": destination,
        "distance_km": distance_km,
        "duration_min": duration_min,
        "created_at": _NOW,
    }
    route_fields.update(overrides.pop("route", {}) or {})
    route_id = _insert(db, "routes", route_fields)

    hist_fields = {
        "route_id": route_id,
        "computed_at": _NOW,
        "distance_km": distance_km,
        "duration_min": duration_min,
        "fuel_cost": fuel_cost,
        "toll_cost": toll_cost,
        "total_cost": total_cost,
        "price_recommended": price_eur,
    }
    hist_fields.update(overrides.pop("route_history", {}) or {})
    route_history_id = _insert(db, "route_history", hist_fields)

    result = {
        "route_id": route_id,
        "route_history_id": route_history_id,
        "distance_km": distance_km,
        "duration_min": duration_min,
        "price_eur": price_eur,
        "total_price_eur": price_eur,
        "fuel_cost": fuel_cost,
        "toll_cost": toll_cost,
        "salary_cost": salary_cost,
        "extra_costs": extra_costs,
        "net_profit": net_profit,
        "rate_per_km": round(price_eur / distance_km, 2),
        "gross_per_km": round(net_profit / distance_km, 2),
    }
    result.update(overrides)

    # Publish economics back onto the lead's trip row (if any).
    lead_id = lead.get("lead_id") or lead.get("trip_id")
    if lead_id is not None:
        db.conn.execute(
            "UPDATE trips SET distance_km = ?, total_price_eur = ?, fuel_cost = ?, "
            "toll_cost = ?, salary_cost = ?, extra_costs = ?, net_profit = ?, "
            "rate_per_km = ?, gross_per_km = ?, updated_at = ? WHERE id = ?",
            (distance_km, price_eur, fuel_cost, toll_cost, salary_cost,
             extra_costs, net_profit, result["rate_per_km"],
             result["gross_per_km"], _NOW, lead_id),
        )
        db.conn.commit()
        result["lead_id"] = lead_id
        result["trip_id"] = lead_id
    return result


# ── Freight exchange loads (§3.6) ─────────────────────────────────────────

def make_freight_loads(db, n: int, **overrides: Any) -> dict[str, Any]:
    """Create ``n`` freight-exchange loads (fresh trip rows, Planned).

    Shape mirrors ``test_freight_exchange_import.py`` (850 km / 2450 € /
    Planned).  Each load gets a unique ``source_reference_id`` and is
    flagged ``source='freight_exchange'`` so imported loads are
    distinguishable from manually-created trips.  A fresh client row is
    auto-created per call to satisfy the ``trips.client_id`` FK.

    Returns a dict with the auto-created ``client_id`` and the list of
    new load ids under ``load_ids`` (``id`` = first load when n == 1).
    """
    n = int(n)
    if n < 1:
        raise ValueError("make_freight_loads requires n >= 1")
    client_id = _insert(db, "clients", {
        "name": f"Freight Load Client {_next():04d}",
        "email": f"freight{_next()}@example.com",
        "phone": "+40-700-000-001",
        "vat_number": f"RO-FX-{_next():04d}",
        "is_active": 1,
        "created_at": _NOW,
        "updated_at": _NOW,
    })
    load_ids = []
    for _ in range(n):
        distance = float(overrides.get("distance_km", 850.0))
        price = float(overrides.get("total_price_eur", 2450.0))
        fuel = float(overrides.get("fuel_cost", round(distance * _FUEL_PER_KM, 2)))
        toll = float(overrides.get("toll_cost", round(distance * _TOLL_PER_KM, 2)))
        salary = float(overrides.get("salary_cost", 600.0))
        extra = float(overrides.get("extra_costs", 50.0))
        fields = {
            "client_id": client_id,
            "client_name": f"Freight Load Client {client_id}",
            "status": "Planned",
            "currency": "EUR",
            "distance_km": distance,
            "total_price_eur": price,
            "fuel_cost": fuel,
            "toll_cost": toll,
            "salary_cost": salary,
            "extra_costs": extra,
            "net_profit": round(price - fuel - toll - salary - extra, 2),
            "rate_per_km": round(price / distance, 2),
            "gross_per_km": round((price - fuel - toll - salary - extra) / distance, 2),
            "loading_country": "DE",
            "delivery_country": "RO",
            "source": "freight_exchange",
            "source_provider_id": "trans-eu",
            "source_reference_id": f"LOAD-{_next():07d}",
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        fields.update(overrides)
        load_ids.append(_insert(db, "trips", fields))
    result: dict[str, Any] = {
        "client_id": client_id,
        "load_ids": load_ids,
        "count": n,
    }
    if n == 1:
        result["id"] = load_ids[0]
        result["load_id"] = load_ids[0]
    return result


# ── Maintenance ────────────────────────────────────────────────────────────

def make_maintenance_ticket(db, truck_id: int, severity: str = "CRITICAL",
                            **overrides: Any) -> dict[str, Any]:
    """Raise a maintenance ticket for ``truck_id``.

    Inserts a ``maintenance_records`` row (blocking fault, mirroring
    ``test_maintenance_blocking.py``) plus a ``maintenance`` alert whose
    ``severity`` (CRITICAL/WARNING) the dispatch block reads.

    Returns a dict with ``maintenance_id``, ``alert_id`` and
    ``truck_id``.
    """
    sev = str(severity).upper()
    maint_fields = {
        "truck_id": truck_id,
        "maintenance_type": "engine",
        "date": _DAY_ISO,
        "notes": f"{sev} — truck cannot operate",
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    maint_fields.update(overrides.pop("record", {}) or {})
    maint_fields.update(overrides.pop("maintenance", {}) or {})
    maintenance_id = _insert(db, "maintenance_records", maint_fields)

    alert_id = uuid.uuid4().hex[:12]
    alert_fields = {
        "id": alert_id,
        "type": "maintenance",
        "severity": sev.lower(),
        "title": f"Maintenance required — truck #{truck_id}",
        "message": f"Truck #{truck_id} flagged {sev}: engine fault, dispatch blocked",
        "truck_id": str(truck_id),
        "trip_id": None,
        "created_at": _NOW,
        "resolved": 0,
        "metadata_json": json.dumps({"source": "make_maintenance_ticket",
                                     "maintenance_id": maintenance_id}),
    }
    alert_fields.update(overrides.pop("alert", {}) or {})
    db.conn.execute(
        "INSERT INTO alerts (id, type, severity, title, message, truck_id, trip_id, "
        "created_at, resolved, resolved_at, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (alert_fields["id"], alert_fields["type"], alert_fields["severity"],
         alert_fields["title"], alert_fields["message"], alert_fields["truck_id"],
         alert_fields["trip_id"], alert_fields["created_at"],
         alert_fields["resolved"], alert_fields.get("resolved_at"),
         alert_fields["metadata_json"]),
    )
    db.conn.commit()
    return {
        "id": maintenance_id,
        "maintenance_id": maintenance_id,
        "alert_id": alert_id,
        "truck_id": truck_id,
        "severity": sev,
    }


# ── OCR documents ─────────────────────────────────────────────────────────

def make_ocr_document(db, trip_id: int, confidence: float,
                      **overrides: Any) -> dict[str, Any]:
    """Seed an OCR'd document linked to ``trip_id``.

    ``confidence`` selects the payload profile used by the OCR recovery
    golden flow::

        0.97 — clean extraction (auto-accepted)
        0.72 — partially extracted (needs review)
        0.12 — low confidence (human correction required)

    Confidence is embedded in ``extracted_data_json`` exactly as
    ``test_ocr_recovery.py`` seeds documents (no dedicated
    ``ocr_confidence`` column exists).

    Returns a dict with ``document_id``/``id``, ``trip_id`` and the
    ``confidence`` stored.
    """
    doc_number = overrides.pop("doc_number", f"DOC-OCR-{_next():05d}")
    conf = float(confidence)
    if conf >= 0.9:
        payload = {
            "cmr_number": f"CMR-{trip_id:06d}",
            "invoice_number": f"INV-{trip_id:06d}",
            "confidence": round(conf, 2),
            "amount_eur": 1350.0,
            "currency": "EUR",
        }
        ocr_text = f"Extracted CMR-{trip_id:06d} and invoice data at high confidence."
    elif conf >= 0.5:
        payload = {
            "cmr_number": f"CMR-{trip_id:06d}",
            "invoice_number": "",
            "confidence": round(conf, 2),
            "amount_eur": None,
            "currency": "EUR",
        }
        ocr_text = f"Extracted CMR-{trip_id:06d}; invoice number unreadable."
    else:
        payload = {
            "cmr_number": "",
            "invoice_number": "",
            "confidence": round(conf, 2),
            "amount_eur": None,
            "currency": "EUR",
        }
        ocr_text = "Low-confidence OCR — fields require human correction."

    fields = {
        "doc_number": doc_number,
        "title": f"OCR doc for trip {trip_id} (conf {conf:.2f})",
        "category": "invoice",
        "entity_type": "trip",
        "entity_id": trip_id,
        "file_path": f"/tmp/ocr_{doc_number}.pdf",
        "file_name": f"ocr_{doc_number}.pdf",
        "mime_type": "application/pdf",
        "ocr_text": ocr_text,
        "ocr_engine": "test",
        "extracted_data_json": json.dumps(payload),
        "uploaded_at": _NOW,
        "updated_at": _NOW,
    }
    fields.update(overrides)
    document_id = _insert(db, "documents", fields)
    return {
        "id": document_id,
        "document_id": document_id,
        "trip_id": trip_id,
        "confidence": round(conf, 2),
        "payload": payload,
    }


# ── Dunning ───────────────────────────────────────────────────────────────

def make_dunning_sequence(db, invoice_id: int, **overrides: Any) -> dict[str, Any]:
    """Pre-seed the day-1/7/14/30 reminder ladder for an invoice.

    Mirrors the overdue-reminder schedule exercised by
    ``test_dunning_workflow.py``.  The invoice's ``trip_id`` and the
    client's email are resolved from the DB (recipient falls back to a
    stable placeholder when the invoice/client has no email).

    Returns a dict with ``invoice_id``, ``trip_id`` and
    ``reminder_ids`` mapping each day offset to the created reminder id.
    """
    invoice = _row(db, "invoices", invoice_id)
    if invoice is None:
        raise ValueError(
            f"make_dunning_sequence requires an existing invoice; id={invoice_id} not found"
        )
    trip_id = invoice.get("trip_id")
    if trip_id is None:
        raise ValueError(f"Invoice #{invoice_id} has no trip_id — cannot seed reminders")

    recipient = overrides.pop("recipient_email", None)
    if not recipient:
        client_id = invoice.get("client_id")
        client = db.conn.execute(
            "SELECT email FROM clients WHERE id = ?", (client_id,)
        ).fetchone() if client_id else None
        recipient = (client["email"] if client and client["email"] else
                     f"billing@client-{client_id or 0}.local")

    days = [int(d) for d in overrides.pop("days", [1, 7, 14, 30])]
    reminder_ids: dict[str, int] = {}
    for offset in days:
        rid = _insert(db, "invoice_reminders", {
            "invoice_id": invoice_id,
            "trip_id": trip_id,
            "reminder_type": f"reminder_day_{offset}",
            "days_offset": offset,
            "sent_at": _NOW,
            "recipient_email": recipient,
            "status": "sent",
            "updated_at": _NOW,
        })
        reminder_ids[str(offset)] = rid
    return {
        "invoice_id": invoice_id,
        "trip_id": trip_id,
        "recipient_email": recipient,
        "reminder_ids": reminder_ids,
    }


# ── Tachograph ────────────────────────────────────────────────────────────

def make_tachograph_import(db, driver_id: int, weekly_hours: float = 55.0,
                           **overrides: Any) -> dict[str, Any]:
    """Import a week of tachograph activity for ``driver_id``.

    Defaults to 55 weekly driving hours — just under the 56 h EU weekly
    limit, so a compliance sweep raises the "approaching limit" warning
    but not a violation (shape follows ``test_tachograph_compliance.py``).

    Inserts one ``tacho_imports`` row plus seven ``tacho_driver_activity``
    rows (one per day, ending today) whose ``driving_minutes`` sum to
    ``weekly_hours * 60``.  No single day exceeds 9 h (540 min) when the
    weekly total fits in 63 h.

    Returns a dict with ``import_id``, ``driver_id``,
    ``activity_ids`` and the weekly totals.
    """
    weekly_minutes = int(round(float(weekly_hours) * 60))
    if weekly_minutes < 0:
        raise ValueError("weekly_hours must be >= 0")

    hash_hex = uuid.uuid4().hex
    file_name = overrides.pop("file_name", f"tacho_week_{_next():04d}.ddd")
    import_fields = {
        "file_name": file_name,
        "file_type": "ddd",
        "file_hash": f"sha256:{hash_hex}",
        "driver_id": driver_id,
        "parse_status": "ok",
        "raw_json": json.dumps({"weekly_hours": float(weekly_hours)}),
        "notes": f"{weekly_hours:.1f}h weekly import",
        "updated_at": _NOW,
    }
    import_fields.update(overrides.pop("import", {}) or {})
    import_id = _insert(db, "tacho_imports", import_fields)

    # Spread the minutes across the last 7 days, capping each day at
    # 9 h (540 min) so the default 55 h profile stays daily-legal.
    remaining = weekly_minutes
    minutes: list[int] = []
    for _ in range(7):
        take = min(540, remaining)
        minutes.append(take)
        remaining -= take
    if remaining > 0:  # weekly_hours > 63 → overflow onto last day
        minutes[-1] += remaining

    activity_ids: list[int] = []
    for i, driving in enumerate(minutes):
        activity_date = (date.today() - timedelta(days=6 - i)).isoformat()
        activity_id = _insert(db, "tacho_driver_activity", {
            "import_id": import_id,
            "driver_id": driver_id,
            "activity_date": activity_date,
            "driving_minutes": driving,
            "work_minutes": driving,
            "rest_minutes": 0,
            "avail_minutes": 0,
            "distance_km": round(driving * 0.8, 1),  # ≈ 80 km/h avg
            "violations": "[]",
            "country_codes": json.dumps(["DE", "RO"]),
            "updated_at": _NOW,
        })
        activity_ids.append(activity_id)

    return {
        "import_id": import_id,
        "driver_id": driver_id,
        "activity_ids": activity_ids,
        "weekly_minutes": weekly_minutes,
        "weekly_hours": round(float(weekly_hours), 2),
        "file_name": file_name,
    }


__all__ = [
    "make_lead",
    "make_route",
    "make_freight_loads",
    "make_maintenance_ticket",
    "make_ocr_document",
    "make_dunning_sequence",
    "make_tachograph_import",
]
