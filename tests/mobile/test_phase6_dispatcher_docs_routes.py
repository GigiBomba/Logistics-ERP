"""Phase-6 follow-up contract tests (backend lane).

Four bounded additions:

  1. ``DispatcherOverviewResponse`` += ``revenue_trend`` (last 6 calendar
     months from the REAL analytics monthly-revenue query) and
     ``recent_activity`` (5 newest trips ∪ 5 newest alerts, capped 10).
  2. ``POST /routes/calculate`` += ``excluded_countries`` (passed through to
     the routing service's exclusion engine; the endpoint does NOT write
     route_history_v2 — that is asserted as the real behavior).
  3. ``GET /documents/categories`` — distinct non-empty company-scoped
     categories with counts.
  4. ``DispatcherJobResponse`` += ``start_date`` / ``end_date`` and an
     optional comma-separated ``statuses`` filter on ``GET /mobile/dispatcher/jobs``.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest


def _month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _last_n_months(n: int) -> list[str]:
    """Return the last *n* calendar months (YYYY-MM), oldest → newest."""
    today = date.today()
    keys = []
    y, m = today.year, today.month
    for _ in range(n):
        keys.append(_month_key(y, m))
        m -= 1
        if m == 0:
            y -= 1
            m = 12
    return keys[::-1]


def _seed_trip(db, *, company_id: int = 1, created_at: str, price: float = 1000.0,
               status: str = "Delivered", start_date=None, end_date=None,
               cmr: str = "") -> int:
    cur = db.execute(
        "INSERT INTO trips (company_id, client_id, client_name, driver_id, driver_name, "
        "truck_number, status, start_date, end_date, place_of_loading, delivery_country, "
        "distance_km, total_price_eur, net_profit, created_at, cmr_number) "
        "VALUES (?, NULL, 'P6 Client', NULL, 'P6 Driver', 'AB-P6', ?, ?, ?, 'Bucharest', "
        "'Vienna', 100, ?, 0.0, ?, ?)",
        (company_id, status, start_date, end_date, price, created_at, cmr),
    )
    db.conn.commit()
    return cur.lastrowid


def _seed_alert(db, *, company_id: int = 1, alert_id: str, title: str,
                created_at: str, resolved: int = 0) -> None:
    db.execute(
        "INSERT INTO alerts (id, type, severity, title, message, created_at, resolved, "
        "company_id) VALUES (?, 'maintenance', 'warning', ?, '', ?, ?, ?)",
        (alert_id, title, created_at, resolved, company_id),
    )
    db.conn.commit()


def _seed_document(db, *, company_id: int = 1, category: str, title: str,
                   is_archived: int = 0) -> int:
    cur = db.execute(
        "INSERT INTO documents (doc_number, title, category, file_path, file_name, "
        "is_archived, uploaded_at, updated_at, company_id) "
        "VALUES (?, ?, ?, '/p6/' || ?, ?, ?, '2026-01-01T00:00:00Z', "
        "'2026-01-01T00:00:00Z', ?)",
        (f"DOC-P6-{category}-{title}", title, category, title, title, is_archived,
         company_id),
    )
    db.conn.commit()
    return cur.lastrowid


# ════════════════════════════════════════════════════════════════════════
#  1. DispatcherOverviewResponse — revenue_trend
# ════════════════════════════════════════════════════════════════════════


class TestDispatcherOverviewRevenueTrend:
    def test_revenue_trend_shape_and_values(self, mobile_app, real_db, mobile_client):
        months = _last_n_months(6)
        _seed_trip(real_db, created_at=f"{months[-1]}-10", price=1000.0)
        _seed_trip(real_db, created_at=f"{months[-2]}-10", price=500.0)

        resp = mobile_client.get("/api/v1/mobile/dispatcher/overview")
        assert resp.status_code == 200
        trend = resp.json()["revenue_trend"]
        assert isinstance(trend, list) and len(trend) == 6
        for point in trend:
            assert set(point.keys()) == {"month", "revenue"}
            assert isinstance(point["revenue"], (int, float))
        assert trend[-1] == {"month": months[-1], "revenue": 1000.0}
        assert trend[-2] == {"month": months[-2], "revenue": 500.0}

    def test_revenue_trend_is_last_six_calendar_months(self, mobile_app, real_db, mobile_client):
        months = _last_n_months(6)
        resp = mobile_client.get("/api/v1/mobile/dispatcher/overview")
        assert resp.status_code == 200
        trend = resp.json()["revenue_trend"]
        assert [p["month"] for p in trend] == months

    def test_revenue_trend_company_scoped(self, mobile_app, real_db, mobile_client):
        months = _last_n_months(6)
        _seed_trip(real_db, company_id=1, created_at=f"{months[-1]}-10", price=1000.0)
        # Another company's in-month trip must NOT leak into company 1.
        _seed_trip(real_db, company_id=2, created_at=f"{months[-1]}-10", price=8888.0)

        resp = mobile_client.get("/api/v1/mobile/dispatcher/overview")
        assert resp.status_code == 200
        trend = resp.json()["revenue_trend"]
        assert trend[-1] == {"month": months[-1], "revenue": 1000.0}

    def test_revenue_trend_window_keeps_in_window_revenue(self, mobile_app, real_db, mobile_client):
        """The 6-month window must not be shifted by older data.

        Six months OUTSIDE the window plus one INSIDE: the in-window month's
        revenue must still surface (the real analytics query is date-bounded to
        the window, not ASC-limited to the oldest months on file).
        """
        months = _last_n_months(6)
        target = months[-2]
        outside = _last_n_months(12)[:6]  # 12..7 months ago → outside the window
        for mo in outside:
            _seed_trip(real_db, created_at=f"{mo}-10", price=1.0)
        _seed_trip(real_db, created_at=f"{target}-10", price=700.0)

        resp = mobile_client.get("/api/v1/mobile/dispatcher/overview")
        assert resp.status_code == 200
        trend = resp.json()["revenue_trend"]
        by_month = {p["month"]: p["revenue"] for p in trend}
        assert by_month[target] == 700.0
        assert by_month[months[-1]] == 0.0

    def test_revenue_trend_empty(self, mobile_app, real_db, mobile_client):
        resp = mobile_client.get("/api/v1/mobile/dispatcher/overview")
        assert resp.status_code == 200
        trend = resp.json()["revenue_trend"]
        assert len(trend) == 6
        assert all(p["revenue"] == 0.0 for p in trend)


# ════════════════════════════════════════════════════════════════════════
#  1b. DispatcherOverviewResponse — recent_activity
# ════════════════════════════════════════════════════════════════════════


class TestDispatcherOverviewRecentActivity:
    def test_activity_union_shape_and_order(self, mobile_app, real_db, mobile_client):
        _seed_trip(real_db, created_at="2026-06-10T08:00:00Z", cmr="ACT-TRIP")
        _seed_alert(real_db, alert_id="1", title="Act Alert", created_at="2026-06-11T09:00:00Z")

        resp = mobile_client.get("/api/v1/mobile/dispatcher/overview")
        assert resp.status_code == 200
        activity = resp.json()["recent_activity"]
        assert isinstance(activity, list)
        types = {item["type"] for item in activity}
        assert types == {"trip", "alert"}
        for item in activity:
            assert set(item.keys()) == {"type", "id", "title", "created_at"}
        assert activity[0]["type"] == "alert"  # newest created_at first
        assert activity[1]["type"] == "trip"

    def test_activity_capped_at_ten(self, mobile_app, real_db, mobile_client):
        for i in range(8):
            _seed_trip(real_db, created_at=f"2026-06-{i + 1:02d}T08:00:00Z")
        for i in range(8):
            _seed_alert(real_db, alert_id=str(i + 1), title=f"A{i}",
                        created_at=f"2026-06-{i + 1:02d}T09:00:00Z")

        resp = mobile_client.get("/api/v1/mobile/dispatcher/overview")
        assert resp.status_code == 200
        activity = resp.json()["recent_activity"]
        assert len(activity) == 10
        # ordered by created_at desc
        timestamps = [a["created_at"] for a in activity]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_activity_company_scoped(self, mobile_app, real_db, mobile_client):
        _seed_trip(real_db, company_id=1, created_at="2026-06-10T08:00:00Z", cmr="C1-TRIP")
        _seed_trip(real_db, company_id=2, created_at="2026-06-10T08:00:00Z", cmr="C2-TRIP")
        _seed_alert(real_db, company_id=2, alert_id="99", title="C2 Alert",
                    created_at="2026-06-10T09:00:00Z")

        resp = mobile_client.get("/api/v1/mobile/dispatcher/overview")
        assert resp.status_code == 200
        activity = resp.json()["recent_activity"]
        titles = {a["title"] for a in activity}
        assert titles == {"C1-TRIP"}


# ════════════════════════════════════════════════════════════════════════
#  2. POST /routes/calculate — excluded_countries
# ════════════════════════════════════════════════════════════════════════


class TestRoutesCalculateExcludedCountries:
    _PAYLOAD = {
        "points": [
            {"lat": 48.85, "lng": 2.35},
            {"lat": 45.75, "lng": 4.85},
        ],
        "profile": "truck",
    }

    def test_excluded_countries_passed_to_routing_service(self, mobile_app, real_db, mobile_client):
        payload = {**self._PAYLOAD, "excluded_countries": ["UA", "MD"]}
        with patch("backend.services.route_service.RouteService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.calculate_route.return_value = {"distance_km": 500}
            resp = mobile_client.post("/api/v1/routes/calculate", json=payload)
        assert resp.status_code == 200
        _, kwargs = mock_svc.calculate_route.call_args
        assert kwargs.get("avoid_countries") == ["UA", "MD"]

    def test_excluded_countries_absent_passes_none(self, mobile_app, real_db, mobile_client):
        with patch("backend.services.route_service.RouteService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.calculate_route.return_value = {"distance_km": 500}
            resp = mobile_client.post("/api/v1/routes/calculate", json=self._PAYLOAD)
        assert resp.status_code == 200
        _, kwargs = mock_svc.calculate_route.call_args
        assert kwargs.get("avoid_countries") is None

    def test_real_behavior_no_route_history_row_written(self, mobile_app, real_db, mobile_client):
        """The /routes/calculate endpoint does NOT persist to route_history_v2.

        Real behavior: exclusions are applied by the routing service
        (``avoid_countries`` → country exclusion plan echoed back as
        ``excluded_countries_requested``/``excluded_countries_applied``) and the
        route result is returned to the caller; no history row is created here.
        """
        payload = {**self._PAYLOAD, "excluded_countries": ["BY"]}
        before = real_db.execute("SELECT COUNT(*) AS c FROM route_history_v2").fetchone()
        with patch("backend.services.route_service.RouteService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.calculate_route.return_value = {
                "distance_km": 500,
                "excluded_countries_requested": ["BY"],
                "excluded_countries_applied": ["BY"],
                "exclusions_applied": True,
            }
            resp = mobile_client.post("/api/v1/routes/calculate", json=payload)
        assert resp.status_code == 200
        assert resp.json()["route"]["excluded_countries_requested"] == ["BY"]
        after = real_db.execute("SELECT COUNT(*) AS c FROM route_history_v2").fetchone()
        assert after["c"] == before["c"]


# ════════════════════════════════════════════════════════════════════════
#  3. GET /documents/categories
# ════════════════════════════════════════════════════════════════════════


class TestDocumentCategories:
    def test_categories_counts_and_shape(self, mobile_app, real_db, mobile_client):
        _seed_document(real_db, category="cmr", title="c1")
        _seed_document(real_db, category="cmr", title="c2")
        _seed_document(real_db, category="invoice", title="i1")
        # empty category + archived must be excluded
        _seed_document(real_db, category="", title="empty-cat")
        _seed_document(real_db, category="archive", title="a1", is_archived=1)

        resp = mobile_client.get("/api/v1/documents/categories")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        by_cat = {item["category"]: item["count"] for item in body}
        assert all(set(item.keys()) == {"category", "count"} for item in body)
        assert by_cat["cmr"] == 2
        assert by_cat["invoice"] == 1
        assert "archive" not in by_cat
        assert "" not in by_cat

    def test_categories_company_scoped(self, mobile_app, real_db, mobile_client):
        _seed_document(real_db, company_id=1, category="cmr", title="c1")
        _seed_document(real_db, company_id=2, category="private", title="p1")

        resp = mobile_client.get("/api/v1/documents/categories")
        assert resp.status_code == 200
        by_cat = {item["category"]: item["count"] for item in resp.json()}
        assert by_cat == {"cmr": 1}

    def test_categories_empty(self, mobile_app, real_db, mobile_client):
        resp = mobile_client.get("/api/v1/documents/categories")
        assert resp.status_code == 200
        assert resp.json() == []


# ════════════════════════════════════════════════════════════════════════
#  4. DispatcherJobResponse — start_date / end_date + statuses filter
# ════════════════════════════════════════════════════════════════════════


class TestDispatcherJobsDatesAndStatuses:
    def test_dates_populated(self, mobile_app, real_db, mobile_client):
        _seed_trip(real_db, status="Planned", start_date="2026-07-01",
                   end_date="2026-07-05", created_at="2026-07-01")
        resp = mobile_client.get("/api/v1/mobile/dispatcher/jobs")
        assert resp.status_code == 200
        jobs = resp.json()
        planned = [j for j in jobs if j["status"] == "Planned"]
        assert planned and planned[0]["start_date"] == "2026-07-01"
        assert planned[0]["end_date"] == "2026-07-05"

    def test_statuses_param_returns_delivered(self, mobile_app, real_db, mobile_client):
        _seed_trip(real_db, status="Delivered", start_date="2026-07-01",
                   end_date="2026-07-03", created_at="2026-07-01", cmr="DEL-1")
        _seed_trip(real_db, status="Cancelled", created_at="2026-07-02", cmr="CAN-1")
        _seed_trip(real_db, status="Planned", created_at="2026-07-03", cmr="PLN-1")

        resp = mobile_client.get(
            "/api/v1/mobile/dispatcher/jobs?statuses=Delivered,Cancelled"
        )
        assert resp.status_code == 200
        statuses = {j["status"] for j in resp.json()}
        assert statuses == {"Delivered", "Cancelled"}

    def test_statuses_absent_keeps_existing_exclusion(self, mobile_app, real_db, mobile_client):
        _seed_trip(real_db, status="Delivered", created_at="2026-07-01", cmr="DEL-1")
        _seed_trip(real_db, status="Cancelled", created_at="2026-07-02", cmr="CAN-1")
        _seed_trip(real_db, status="Paid", created_at="2026-07-03", cmr="PAID-1")
        _seed_trip(real_db, status="Planned", created_at="2026-07-04", cmr="PLN-1")

        resp = mobile_client.get("/api/v1/mobile/dispatcher/jobs")
        assert resp.status_code == 200
        statuses = {j["status"] for j in resp.json()}
        assert statuses == {"Planned"}

    def test_statuses_company_scoped(self, mobile_app, real_db, mobile_client):
        _seed_trip(real_db, company_id=1, status="Delivered", created_at="2026-07-01", cmr="C1-DEL")
        _seed_trip(real_db, company_id=2, status="Delivered", created_at="2026-07-01", cmr="C2-DEL")

        resp = mobile_client.get("/api/v1/mobile/dispatcher/jobs?statuses=Delivered")
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) == 1
        assert jobs[0]["load_info"] == "C1-DEL"
