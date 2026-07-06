"""Tests for repositories.analytics_repository — SQL query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from repositories.analytics_repository import AnalyticsRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> AnalyticsRepository:
    repo = AnalyticsRepository(db)
    AnalyticsRepository._month_check_done = False
    AnalyticsRepository._month_col_available = None
    return repo


def _trip(db, **kw):
    d = dict(created_at="2026-01-15", truck_number="TRK-1",
             driver_name="John", client_name="ACME",
             distance_km=500, total_price_eur=2500, net_profit=800,
             status="completed", delivery_country="DE",
             loading_country="FR", extra_costs=0, fuel_cost=0,
             toll_cost=0, salary_cost=0)
    d.update(kw)
    cols, vals = ", ".join(d.keys()), list(d.values())
    db.conn.execute(f"INSERT INTO trips ({cols}) VALUES ({', '.join('?' for _ in d)})", vals)
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestGetStatsByPeriod:
    def test_empty_db(self, repo):
        assert repo.get_stats_by_period() is None or repo.get_stats_by_period()["total"] == 0

    def test_aggregates(self, db, repo):
        _trip(db, net_profit=1000, distance_km=500, total_price_eur=3000)
        _trip(db, net_profit=-200, distance_km=300, total_price_eur=1500)
        _trip(db, net_profit=500, distance_km=200, total_price_eur=1000)
        r = repo.get_stats_by_period()
        assert r["total"] == 3 and r["profitable"] == 2 and r["losing"] == 1
        assert r["total_p"] == 1300 and r["total_km"] == 1000 and r["total_rev"] == 5500

    def test_date_filter(self, db, repo):
        _trip(db, created_at="2026-01-01", net_profit=100)
        _trip(db, created_at="2026-02-15", net_profit=200)
        _trip(db, created_at="2026-03-20", net_profit=300)
        r = repo.get_stats_by_period(start="2026-02-01", end="2026-03-01")
        assert r["total"] == 1 and r["total_p"] == 200


class TestGetAvailableYears:
    def test_returns_years(self, db, repo):
        _trip(db, created_at="2025-06-01")
        _trip(db, created_at="2026-01-15")
        years = repo.get_available_years()
        assert "2025" in years and "2026" in years

    def test_empty_db(self, repo):
        assert repo.get_available_years() == []


class TestGetKpiStats:
    def test_empty_db(self, repo):
        s = repo.get_kpi_stats()
        assert s["rev"] == 0 and s["profit"] == 0 and s["km"] == 0

    def test_monthly_kpis(self, db, repo):
        import datetime
        m = datetime.datetime.now().strftime("%Y-%m")
        _trip(db, created_at=f"{m}-01", total_price_eur=3000, net_profit=500, distance_km=400)
        _trip(db, created_at=f"{m}-15", total_price_eur=1500, net_profit=300, distance_km=200)
        s = repo.get_kpi_stats()
        assert s["rev"] == 4500 and s["profit"] == 800 and s["km"] == 600


class TestGetClientGrowth:
    """Queries the ``clients`` table — seed with clients, not trips."""

    def test_empty_db(self, repo):
        assert repo.get_client_growth() == []

    def test_returns_monthly_counts(self, db, repo):
        db.conn.execute(
            "INSERT INTO clients (name, created_at, is_active) VALUES (?, ?, ?)",
            ("Client A", "2026-01-05", 1),
        )
        db.conn.execute(
            "INSERT INTO clients (name, created_at, is_active) VALUES (?, ?, ?)",
            ("Client B", "2026-01-20", 1),
        )
        db.conn.execute(
            "INSERT INTO clients (name, created_at, is_active) VALUES (?, ?, ?)",
            ("Client C", "2026-02-10", 1),
        )
        db.conn.commit()
        result = repo.get_client_growth(months=6)
        assert len(result) >= 2


class TestGetTruckUtilization:
    """Queries trucks LEFT JOIN trips — seed both tables."""

    def test_returns_truck_stats(self, db, repo):
        db.conn.execute("INSERT INTO trucks (plate_number, active_status) VALUES (?, ?)",
                        ("TRK-1", 1))
        db.conn.execute("INSERT INTO trucks (plate_number, active_status) VALUES (?, ?)",
                        ("TRK-2", 1))
        db.conn.commit()
        t1 = db.conn.execute("SELECT last_insert_rowid() FROM trucks").fetchone()
        db.conn.execute("INSERT INTO trips (truck_id, distance_km, created_at) VALUES (?, ?, ?)",
                        (1, 1000, "2026-01-01"))
        db.conn.execute("INSERT INTO trips (truck_id, distance_km, created_at) VALUES (?, ?, ?)",
                        (1, 500, "2026-02-01"))
        db.conn.execute("INSERT INTO trips (truck_id, distance_km, created_at) VALUES (?, ?, ?)",
                        (2, 200, "2026-01-15"))
        db.conn.commit()
        result = repo.get_truck_utilization()
        assert len(result) == 2
        t1_data = [r for r in result if r["truck"] == "TRK-1"][0]
        assert t1_data["trip_count"] == 2
        assert t1_data["total_km"] == 1500


class TestGetProfitPerKmByCountry:
    def test_returns_by_country(self, db, repo):
        _trip(db, delivery_country="DE", distance_km=100, net_profit=50)
        _trip(db, delivery_country="DE", distance_km=200, net_profit=100)
        _trip(db, delivery_country="FR", distance_km=300, net_profit=90)
        result = repo.get_profit_per_km_by_country()
        countries = {r["country"]: r for r in result}
        assert countries["DE"]["profit"] == 150
        assert countries["DE"]["total_km"] == 300

    def test_empty_db(self, repo):
        assert repo.get_profit_per_km_by_country() == []


class TestGetRevenueConcentration:
    def test_returns_client_revenues(self, db, repo):
        _trip(db, client_name="Big Co", total_price_eur=8000, net_profit=2000)
        _trip(db, client_name="Small Co", total_price_eur=2000, net_profit=500)
        _trip(db, client_name="Big Co", total_price_eur=2000, net_profit=600)
        result = repo.get_revenue_concentration()
        big = [r for r in result if r["client"] == "Big Co"][0]
        assert big["revenue"] == 10000
        assert big["profit"] == 2600

    def test_empty_db(self, repo):
        assert repo.get_revenue_concentration() == []


class TestGetMonthlyFinancialSummary:
    def test_returns_monthly_data(self, db, repo):
        _trip(db, created_at="2026-01-01", total_price_eur=3000, net_profit=800, status="Invoiced")
        _trip(db, created_at="2026-01-15", total_price_eur=2000, net_profit=500, status="Paid")
        _trip(db, created_at="2026-02-01", total_price_eur=4000, net_profit=1000, status="Completed")
        result = repo.get_monthly_financial_summary(months=6)
        assert len(result) >= 2
        by_month = {r["month"]: r for r in result}
        jan = by_month.get("2026-01")
        if jan:
            assert jan["revenue"] == 5000
            assert jan["profit"] == 1300
            assert jan["trip_count"] == 2

    def test_empty_db(self, repo):
        assert repo.get_monthly_financial_summary() == []


class TestGetDocumentUploadTrend:
    @pytest.mark.xfail(reason="documents table not in InMemoryDB schema")
    def test_returns_list(self, db, repo):
        result = repo.get_document_upload_trend()
        assert isinstance(result, list)


class TestGetDriverTachoViolations:
    def test_returns_list(self, db, repo):
        result = repo.get_driver_tacho_violations()
        assert isinstance(result, list)


class TestGetDriverProfitPerKm:
    def test_returns_by_driver(self, db, repo):
        _trip(db, driver_name="Alice", distance_km=1000, net_profit=500)
        _trip(db, driver_name="Alice", distance_km=500, net_profit=300)
        _trip(db, driver_name="Bob", distance_km=300, net_profit=90)
        result = repo.get_driver_profit_per_km()
        names = {r["driver_name"]: r for r in result}
        assert names["Alice"]["total_profit"] == 800
        assert names["Alice"]["total_km"] == 1500

    def test_empty_db(self, repo):
        assert repo.get_driver_profit_per_km() == []
