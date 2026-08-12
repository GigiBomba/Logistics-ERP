"""Driver self-service tachograph endpoint tests (Tier-2) — REAL DB.

Covers ``GET /api/v1/mobile/driver/tacho`` (ANY authenticated role): driver-role
200 + shape + 7-day default window, driver with no activity → empty days / 0
weekly, unresolved user (no linked driver row) → 404, and 401 without a token.
The driver is resolved server-side from the JWT via the shared
``_resolve_driver_id`` helper (email match) — never from client input.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

BASE = "/api/v1/mobile/driver/tacho"


def _seed_driver(db, *, email="driver@test.com", company_id=1, name="Self Driver") -> int:
    cur = db.execute(
        "INSERT INTO drivers (name, phone, email, license_number, license_category, "
        "is_active, company_id, created_at, updated_at) "
        "VALUES (?, '0700000000', ?, 'LIC-SELF', 'C', 1, ?, '2026-01-01T00:00:00Z', "
        "'2026-01-01T00:00:00Z')",
        (name, email, company_id),
    )
    db.conn.commit()
    return cur.lastrowid


def _seed_activity(db, driver_id, *, days_ago, driving=300, work=120, rest=600, avail=180) -> None:
    # tacho_driver_activity.import_id is NOT NULL + REFERENCES tacho_imports(id)
    # → seed a parent import row first.
    cur = db.execute(
        "INSERT INTO tacho_imports (imported_at, file_name, file_type, file_hash, "
        "driver_id, parse_status, company_id) "
        "VALUES (datetime('now'), 'self.ddd', 'ddd', 'self-hash', ?, 'ok', 1)",
        (driver_id,),
    )
    import_id = cur.lastrowid
    day = (date.today() - timedelta(days=days_ago)).isoformat()
    db.execute(
        "INSERT INTO tacho_driver_activity (import_id, driver_id, activity_date, "
        "driving_minutes, work_minutes, rest_minutes, avail_minutes, distance_km) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 400)",
        (import_id, driver_id, day, driving, work, rest, avail),
    )
    db.conn.commit()


class TestDriverTachoSelf:
    def test_driver_200_shape_and_7day_default(self, mobile_app, real_db, driver_client):
        driver_id = _seed_driver(real_db)
        _seed_activity(real_db, driver_id, days_ago=2, driving=300, work=120, rest=600, avail=180)
        _seed_activity(real_db, driver_id, days_ago=4, driving=120)

        resp = driver_client.get(BASE)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["weekly_limit_minutes"] == 3360
        assert body["weekly_driving_minutes"] == 420
        assert len(body["days"]) == 2

        by_day = {d["date"]: d for d in body["days"]}
        two_ago = (date.today() - timedelta(days=2)).isoformat()
        four_ago = (date.today() - timedelta(days=4)).isoformat()
        assert two_ago in by_day and four_ago in by_day
        assert by_day[two_ago]["driving_minutes"] == 300
        assert by_day[two_ago]["working_minutes"] == 120
        assert by_day[two_ago]["rest_minutes"] == 600
        assert by_day[two_ago]["availability_minutes"] == 180
        assert by_day[four_ago]["driving_minutes"] == 120
        # Buckets sorted ascending by date (oldest first).
        assert body["days"][0]["date"] < body["days"][1]["date"]

    def test_driver_no_activity_empty_days(self, mobile_app, real_db, driver_client):
        _seed_driver(real_db)
        resp = driver_client.get(BASE)
        assert resp.status_code == 200
        body = resp.json()
        assert body["days"] == []
        assert body["weekly_driving_minutes"] == 0
        assert body["weekly_limit_minutes"] == 3360

    def test_unresolved_user_404(self, mobile_app, real_db, dispatcher_client):
        # The dispatcher user (id 2) has NO linked drivers row → 404.
        resp = dispatcher_client.get(BASE)
        assert resp.status_code == 404
        assert resp.json()["detail"]["error_code"] == "driver_not_linked"

    def test_no_token_401(self, app):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(BASE)
        assert resp.status_code == 401
