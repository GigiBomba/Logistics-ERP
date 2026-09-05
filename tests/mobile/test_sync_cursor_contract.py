"""Contract tests for the delta-sync cursor fix (Phase 1 + Gate-1b remediations).

Locks down the ``GET /api/v1/mobile/sync`` contract:

  1. **Compound data cursor** — timestamp entities (transport/trips, message,
     drivers, clients) return ``cursor = "<max_ts>|<boundary_id>"`` over the
     RETURNED rows (never the request wall-clock), so equal-timestamp bursts
     paginate by id and rows stamped at exactly the cursor second are never
     dropped.  The id component defaults to ``0`` for legacy plain-timestamp
     ``since`` values (row-value comparison ``(ts, id) > (?, ?)``).
  2. **No cursor poisoning (M1)** — a first-ever EMPTY page returns
     ``cursor=None`` (never ``_now_iso()``), so space-format SQLite
     ``created_at`` values never sort below a T-format cursor and get excluded
     forever.  ``send_message`` writes the canonical ``utc_now_iso()``
     T-format ``created_at`` going forward.
  3. **Fleet pagination (M2)** — ``full=true&since=<id>`` advances the fleet
     id cursor (``is_full`` must not force the first page) and terminates.
  4. **Same-timestamp burst (M3)** — a page of rows sharing one timestamp
     paginates completely via the compound cursor.
  5. **Honest ``has_more``** — ``has_more == len(records) >= <entity limit>``
     (200 for trips/trucks/drivers/clients, 100 for message).
  6. **Tenant isolation (sacred)** — sync under a company's JWT returns only
     that company's rows.

Fixtures reuse the ``tests/mobile`` real-DB pattern (``real_db``,
``mobile_app``, ``dispatcher_client``, ``seed_records``).

Seeding notes: the real DB installs AFTER INSERT/UPDATE ``updated_at``
stamping triggers on syncable tables (trips/clients/drivers/trucks).  Those
overwrite ``updated_at`` with the wall-clock unless ``sync_meta
.sync_in_progress='1'`` is set, so the timestamp-controlled tests suppress the
triggers while seeding and restore them afterwards.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from tests.mobile.conftest import seed_records

SYNC_URL = "/api/v1/mobile/sync"
MESSAGES_URL = "/api/v1/mobile/messages"

# Second-precision timestamp used to force the same-second boundary case.
_T0 = "2026-06-01T10:00:00Z"
# SQLite ``datetime('now')`` default format — space-separated, no zone.
_SPACE_TS_OLD = "2026-06-01 10:00:00"
_SPACE_TS_NEW = "2026-06-02 10:00:00"


# ── Seeding helpers ──────────────────────────────────────────────────────


def _iso_second(base: datetime, offset_seconds: int) -> str:
    """ISO-8601 UTC timestamp (second precision) offset by N seconds."""
    when = base.replace(tzinfo=timezone.utc) + timedelta(seconds=offset_seconds)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _suppress_sync_stamping(db) -> None:
    """Set the echo-suppression guard so seeded timestamps are preserved."""
    db.execute(
        "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('sync_in_progress', '1')"
    )
    db.conn.commit()


def _restore_sync_stamping(db) -> None:
    db.execute("DELETE FROM sync_meta WHERE key = 'sync_in_progress'")
    db.conn.commit()


def _seed_driver(db, company_id: int, name: str, updated_at: str, idx: int = 0) -> int:
    cur = db.execute(
        "INSERT INTO drivers (name, phone, license_number, license_category, "
        "is_active, company_id, created_at, updated_at) "
        "VALUES (?, ?, ?, 'C', 1, ?, ?, ?)",
        (name, f"07{idx:07d}", f"LIC-{idx:06d}", company_id, updated_at, updated_at),
    )
    db.conn.commit()
    return cur.lastrowid


def _seed_drivers(db, company_id: int, count: int, start: datetime) -> list[int]:
    """Seed *count* drivers with strictly increasing second-precision timestamps."""
    ids = []
    for i in range(count):
        ts = _iso_second(start, i)
        cur = db.execute(
            "INSERT INTO drivers (name, phone, license_number, license_category, "
            "is_active, company_id, created_at, updated_at) "
            "VALUES (?, ?, ?, 'C', 1, ?, ?, ?)",
            (f"Sync Driver {i:04d}", f"07{i:07d}", f"SYNC-LIC-{i:06d}",
             company_id, ts, ts),
        )
        ids.append(cur.lastrowid)
    db.conn.commit()
    return ids


def _seed_clients(db, company_id: int, count: int, start: datetime) -> list[int]:
    """Seed *count* clients with strictly increasing second-precision timestamps."""
    ids = []
    for i in range(count):
        ts = _iso_second(start, i)
        cur = db.execute(
            "INSERT INTO clients (name, vat_number, contact_person, phone, email, "
            "address, currency_preference, notes, is_active, created_at, updated_at, "
            "client_type, payment_terms_days, credit_limit_eur, rating, company_id) "
            "VALUES (?, ?, 'P', '0700000000', ?, 'Addr', 'EUR', '', 1, ?, ?, "
            "'', 30, 0, 4, ?)",
            (f"Sync Client {i:04d}", f"RO{i:08d}", f"sync{i}@test.com", ts, ts, company_id),
        )
        ids.append(cur.lastrowid)
    db.conn.commit()
    return ids


def _seed_trucks(db, company_id: int, count: int) -> list[int]:
    """Seed *count* trucks (fleet has no timestamps; id-cursor entity)."""
    ids = []
    for i in range(count):
        cur = db.execute(
            "INSERT INTO trucks (plate_number, manufacturer, model, status, "
            "year, vin, active_status, company_id) VALUES (?, ?, ?, 'Active', "
            "2026, ?, 1, ?)",
            (f"SYNC-PLT-{i:04d}", "SyncBrand", f"SyncModel-{i:04d}",
             f"VIN-SYNC-{i:04d}", company_id),
        )
        ids.append(cur.lastrowid)
    db.conn.commit()
    return ids


def _seed_message(db, sender_id: int, receiver_id: int, text: str, created_at: str) -> int:
    cur = db.execute(
        "INSERT INTO mobile_messages (company_id, sender_id, receiver_id, "
        "text, is_read, created_at) VALUES (?, ?, ?, ?, 0, ?)",
        (1, sender_id, receiver_id, text, created_at),
    )
    db.conn.commit()
    return cur.lastrowid


def _sync(client, **params):
    """GET the sync endpoint with the given query params, returning parsed JSON."""
    resp = client.get(SYNC_URL, params=params)
    assert resp.status_code == 200, f"sync failed: {resp.status_code} {resp.text}"
    return resp.json()


# ── Same-second regression (compound cursor) ─────────────────────────────


def test_same_second_rows_are_not_dropped(mobile_app, real_db, dispatcher_client):
    """Two rows in the same second; a third row at the same max timestamp must
    appear on the next sync with ``since = cursor``."""
    _suppress_sync_stamping(real_db)
    id_a = _seed_driver(real_db, 1, "Same-Second A", _T0, idx=1)
    id_b = _seed_driver(real_db, 1, "Same-Second B", _T0, idx=2)
    _restore_sync_stamping(real_db)

    # First sync: both rows returned, cursor = compound (max updated_at, id).
    body = _sync(dispatcher_client, entity="drivers", full="true")
    assert {r["name"] for r in body["records"]} == {"Same-Second A", "Same-Second B"}
    ts_part, id_part = body["cursor"].split("|")
    assert ts_part == _T0, (
        "cursor ts must be max(updated_at) of the returned rows, "
        f"got {body['cursor']!r}"
    )
    assert id_part == str(max(id_a, id_b)), "cursor id must be the boundary row id"
    assert body["has_more"] is False

    # A third row updated at the same max timestamp is inserted afterwards.
    _suppress_sync_stamping(real_db)
    id_c = _seed_driver(real_db, 1, "Same-Second C", _T0, idx=3)
    _restore_sync_stamping(real_db)

    # Next sync with since=cursor (strict (ts, id) > comparison) must still see it.
    body2 = _sync(dispatcher_client, entity="drivers", since=body["cursor"])
    names2 = {r["name"] for r in body2["records"]}
    assert "Same-Second C" in names2, (
        "row stamped at the cursor second must be included by the next sync "
        "(previously-dropped-row scenario)"
    )
    ts2, id2 = body2["cursor"].split("|")
    assert ts2 == _T0 and id2 == str(id_c)


# ── Pagination progression ───────────────────────────────────────────────


def test_pagination_progression_terminates(mobile_app, real_db, dispatcher_client):
    """More rows than the limit: first page has_more=True, subsequent pages
    with since=cursor return the remaining rows and the loop terminates."""
    start = datetime(2026, 6, 1)
    _suppress_sync_stamping(real_db)
    ids = set(_seed_drivers(real_db, company_id=1, count=250, start=start))
    _restore_sync_stamping(real_db)

    body = _sync(dispatcher_client, entity="drivers", full="true")
    assert body["has_more"] is True, "a full page must honestly report has_more"
    assert len(body["records"]) == 200, "first page should be the full 200-row limit"
    assert "|" in body["cursor"], "cursor must be the compound ts|id form"

    seen = {r["id"] for r in body["records"]}
    cursor = body["cursor"]
    pages = 1
    while body["has_more"]:
        body = _sync(dispatcher_client, entity="drivers", since=cursor)
        seen.update(r["id"] for r in body["records"])
        cursor = body["cursor"]
        pages += 1
        assert pages < 50, "pagination must terminate"

    assert body["has_more"] is False
    assert pages >= 2, "the loop must actually walk more than one page"
    assert seen == ids, (
        f"pagination must cover every row — got {len(seen)}/{len(ids)} distinct ids"
    )


# ── Full-sync completeness ───────────────────────────────────────────────


def test_full_sync_completeness_no_truncation(mobile_app, real_db, dispatcher_client):
    """``full=true`` paginated until ``has_more == False`` covers ALL rows —
    no silent 200-row truncation."""
    start = datetime(2026, 6, 1)
    _suppress_sync_stamping(real_db)
    ids = set(_seed_clients(real_db, company_id=1, count=250, start=start))
    _restore_sync_stamping(real_db)

    body = _sync(dispatcher_client, entity="clients", full="true")
    assert body["has_more"] is True, "a full page must honestly report has_more"
    assert "|" in body["cursor"], "cursor must be the compound ts|id form"

    seen = set()
    guard = 0
    while True:
        seen.update(r["id"] for r in body["records"])
        if not body["has_more"]:
            break
        body = _sync(dispatcher_client, entity="clients", full="true", since=body["cursor"])
        guard += 1
        assert guard < 50, "full-sync pagination must terminate"

    assert body["has_more"] is False
    assert seen == ids, (
        f"full sync must cover ALL rows — got {len(seen)}/{len(ids)} distinct ids"
    )


def test_message_entity_uses_its_100_row_limit(mobile_app, real_db, dispatcher_client):
    """Message pages cap at 100 (not 200) and has_more reflects that limit."""
    start = datetime(2026, 6, 1)
    for i in range(110):
        ts = _iso_second(start, i)
        real_db.execute(
            "INSERT INTO mobile_messages (company_id, sender_id, receiver_id, "
            "text, is_read, created_at) VALUES (?, ?, ?, ?, 0, ?)",
            (1, 2, 99, f"msg-{i:03d}", ts),
        )
    real_db.conn.commit()

    body = _sync(dispatcher_client, entity="message", full="true")
    assert len(body["records"]) == 100, "message pages must cap at 100 rows"
    assert body["has_more"] is True, "a full 100-row message page must report has_more"

    body2 = _sync(dispatcher_client, entity="message", since=body["cursor"])
    assert len(body2["records"]) == 10, (
        "keyset continuation returns ONLY the remaining rows (no boundary overlap)"
    )
    assert body2["has_more"] is False


# ── M1: space-format created_at cursor poisoning ─────────────────────────


def test_message_empty_first_sync_returns_null_cursor(mobile_app, real_db, dispatcher_client):
    """A first-ever EMPTY message page must return cursor=None, not a T-format
    wall-clock cursor that space-format ``created_at`` rows sort below forever."""
    # Legacy message for a DIFFERENT user with SQLite space-format created_at
    # — this user's first sync is genuinely empty.
    _seed_message(real_db, sender_id=99, receiver_id=98, text="other-user",
                  created_at=_SPACE_TS_OLD)

    body = _sync(dispatcher_client, entity="message", full="true")
    assert body["records"] == []
    assert body["cursor"] is None, (
        "first-ever empty page must return cursor=None, not a T-format cursor "
        "that would sort above every space-format created_at row forever"
    )

    # A space-format message now arrives for the dispatcher user (the SQLite
    # datetime('now') default that predates the send_message fix).
    _seed_message(real_db, sender_id=2, receiver_id=99, text="hello-space",
                  created_at=_SPACE_TS_NEW)

    # The client treats None as "no cursor" → first page again → message present.
    body2 = _sync(dispatcher_client, entity="message")
    assert any(r["text"] == "hello-space" for r in body2["records"]), (
        "a space-format message must be reachable after a None-cursor first sync"
    )
    ts_part, _ = body2["cursor"].split("|")
    assert ts_part == _SPACE_TS_NEW, (
        "cursor ts must be max(created_at) in the row's own (space) format"
    )


def test_message_space_format_rows_use_data_cursor(mobile_app, real_db, dispatcher_client):
    """Space-format rows are returned on the first sync with cursor =
    max(created_at) in their own format; the next delta catches newer rows."""
    _seed_message(real_db, sender_id=2, receiver_id=99, text="m1", created_at=_SPACE_TS_OLD)
    _seed_message(real_db, sender_id=2, receiver_id=99, text="m2", created_at=_SPACE_TS_OLD)

    body = _sync(dispatcher_client, entity="message", full="true")
    assert {r["text"] for r in body["records"]} == {"m1", "m2"}
    ts_part, _ = body["cursor"].split("|")
    assert ts_part == _SPACE_TS_OLD, (
        "cursor ts must be max(created_at) in the row's own (space) format, "
        "not a T-format wall-clock"
    )

    # A newer space-format message → the next delta catches it.
    _seed_message(real_db, sender_id=2, receiver_id=99, text="m3", created_at=_SPACE_TS_NEW)
    body2 = _sync(dispatcher_client, entity="message", since=body["cursor"])
    assert any(r["text"] == "m3" for r in body2["records"]), (
        "a newer space-format message must be caught by the delta after the "
        "space-format data cursor"
    )


def test_send_message_writes_canonical_created_at(mobile_app, real_db, dispatcher_client):
    """New messages get the canonical T-format created_at (not the SQLite
    space-format ``datetime('now')`` default)."""
    resp = dispatcher_client.post(
        MESSAGES_URL, json={"receiver_id": 99, "text": "canonical-ts"},
    )
    assert resp.status_code == 201, f"send failed: {resp.status_code} {resp.text}"
    msg_id = resp.json()["id"]

    row = real_db.execute(
        "SELECT created_at FROM mobile_messages WHERE id = ?", (msg_id,)
    ).fetchone()
    assert row is not None
    created_at = row["created_at"]
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", created_at), (
        f"send_message must write the canonical T-format created_at, got {created_at!r}"
    )
    assert " " not in created_at


# ── M2: fleet pagination ─────────────────────────────────────────────────


def test_fleet_pagination_advances_and_terminates(mobile_app, real_db, dispatcher_client):
    """``full=true&since=<id>`` must advance the fleet id cursor and terminate
    (is_full must not force the first page forever)."""
    ids = set(_seed_trucks(real_db, company_id=1, count=250))

    body = _sync(dispatcher_client, entity="fleet", full="true")
    assert body["has_more"] is True, "250 trucks must honestly report has_more"
    assert len(body["records"]) == 200, "fleet first page must be the 200-row limit"

    seen = set()
    prev_cursor = None
    guard = 0
    while True:
        seen.update(r["id"] for r in body["records"])
        if not body["has_more"]:
            break
        cursor = body["cursor"]
        # M2: the fleet id cursor must STRICTLY advance on continuation —
        # otherwise ``full=true&since=<id>`` re-serves page 1 forever.
        if prev_cursor is not None:
            assert int(cursor) > int(prev_cursor), (
                f"fleet cursor must advance, got {prev_cursor} → {cursor}"
            )
        prev_cursor = cursor
        body = _sync(dispatcher_client, entity="fleet", full="true", since=cursor)
        guard += 1
        assert guard < 50, "fleet pagination must terminate"

    assert body["has_more"] is False
    assert seen == ids, f"fleet sync must cover all trucks — got {len(seen)}/{len(ids)}"


# ── M3: same-timestamp burst ─────────────────────────────────────────────


def test_same_timestamp_burst_paginates_completely(mobile_app, real_db, dispatcher_client):
    """>LIMIT rows sharing ONE timestamp must paginate completely via the
    compound (ts, id) cursor — no non-terminating loop, no unreachable rows."""
    _suppress_sync_stamping(real_db)
    ids = set()
    for i in range(250):
        ids.add(_seed_driver(real_db, 1, f"Burst {i:03d}", _T0, idx=i + 10))
    _restore_sync_stamping(real_db)

    # Legacy plain-timestamp since (no id part) must still work: an
    # older-than-all since returns the first page of the whole result set.
    body0 = _sync(dispatcher_client, entity="drivers", since="2000-01-01T00:00:00Z")
    assert len(body0["records"]) == 200
    assert body0["has_more"] is True

    # Paginate with the compound cursor → covers ALL 250 rows, terminates.
    body = _sync(dispatcher_client, entity="drivers", full="true")
    assert body["has_more"] is True
    assert "|" in body["cursor"], "compound cursor required to page a same-second burst"

    seen = set()
    guard = 0
    while True:
        seen.update(r["id"] for r in body["records"])
        if not body["has_more"]:
            break
        body = _sync(dispatcher_client, entity="drivers", since=body["cursor"])
        guard += 1
        assert guard < 50, "same-timestamp burst pagination must terminate"

    assert body["has_more"] is False
    assert seen == ids, (
        f"burst must cover every row — got {len(seen)}/{len(ids)} distinct ids"
    )


# ── Tenant isolation (sacred) ────────────────────────────────────────────


def test_tenant_isolation_sync_returns_only_own_company(mobile_app, real_db, records_seed, dispatcher_client):
    """Sync under company-1's identity returns ONLY company-1 rows, never
    company-2 rows seeded in the same table."""
    # Company 2 rows alongside company 1 (both in the trips table).
    seed_records(real_db, company_id=2)

    total_a = real_db.execute(
        "SELECT COUNT(*) AS n FROM trips WHERE company_id = 1"
    ).fetchone()["n"]
    assert total_a > 0, "test precondition: company-1 trips must be seeded"

    body = _sync(dispatcher_client, entity="transport", full="true")
    assert len(body["records"]) == total_a, (
        f"sync must return every company-1 trip ({total_a}), got {len(body['records'])}"
    )
    assert all(r["company_id"] == 1 for r in body["records"]), (
        "company-2 rows must NEVER leak into company-1 sync"
    )
    company_2_ids = {
        r["id"] for r in real_db.execute(
            "SELECT id FROM trips WHERE company_id = 2"
        ).fetchall()
    }
    assert not (company_2_ids & {r["id"] for r in body["records"]}), (
        "company-2 trip ids leaked into the response"
    )


# ── Empty-page cursor semantics ──────────────────────────────────────────


def test_empty_page_echoes_incoming_since(mobile_app, real_db, dispatcher_client):
    """An empty delta page echoes the incoming ``since`` unchanged; a first-
    ever empty page returns ``cursor=None`` (never a T-format wall-clock)."""
    # A page strictly newer than ALL rows comes back empty while echoing the
    # incoming cursor (compound or plain — unchanged).
    body = _sync(dispatcher_client, entity="drivers", since="2030-01-01T00:00:00Z")
    assert body["records"] == []
    assert body["cursor"] == "2030-01-01T00:00:00Z", (
        "empty page must echo the incoming since cursor"
    )
    assert body["has_more"] is False

    # An empty first-ever sync (no since, no data) returns cursor=None — the
    # client re-syncs from scratch instead of holding a stale cursor.
    body2 = _sync(dispatcher_client, entity="drivers", full="true")
    assert body2["records"] == []
    assert body2["cursor"] is None, "first-ever empty sync must return cursor=None"
    assert body2["has_more"] is False