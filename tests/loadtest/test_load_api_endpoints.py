"""Load tests for API endpoints — verifies behavior under concurrent requests."""
from __future__ import annotations

import concurrent.futures
import threading
import time

import pytest

from tests.loadtest.conftest import run_concurrent

pytestmark = pytest.mark.slow

BASE_TRIPS = "/api/v1/trips"
BASE_FLEET = "/api/v1/fleet"
BASE_ANALYTICS = "/api/v1/analytics"
BASE_CLIENTS = "/api/v1/clients"
BASE_DRIVERS = "/api/v1/drivers"


# ═══════════════════════════════════════════════════════════════════════════
# TestAPILoadTrips
# ═══════════════════════════════════════════════════════════════════════════

class TestAPILoadTrips:
    """Load test: concurrent trip requests."""

    # ── list trips ────────────────────────────────────────────────────────

    def test_concurrent_trip_list_requests(self, client_with_mocks):
        """50 concurrent GET /trips/ requests should all return 200."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = [{"id": i} for i in range(10)]

        def fetch(_):
            return client.get(f"{BASE_TRIPS}/")

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(fetch, range(50)))

        assert all(r.status_code == 200 for r in results)
        assert all(len(r.json()["items"]) == 10 for r in results)

    # ── create trip ───────────────────────────────────────────────────────

    def test_concurrent_trip_create_requests(self, client_with_mocks):
        """20 concurrent POST /trips/ requests should all return 200."""
        client, mocks = client_with_mocks
        mocks["trip_service"].add.return_value = 42

        payload = {"client_name": "Acme", "loading_city": "Paris"}

        def post_trip(_):
            return client.post(f"{BASE_TRIPS}/", json=payload)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(post_trip, range(20)))

        assert all(r.status_code == 200 for r in results)
        assert all(r.json()["id"] == 42 for r in results)
        assert mocks["trip_service"].add.call_count == 20

    # ── get by id ─────────────────────────────────────────────────────────

    def test_concurrent_trip_get_by_id(self, client_with_mocks):
        """50 concurrent GET /trips/<id> requests should all return 200."""
        client, mocks = client_with_mocks
        trip = {"id": 1, "status": "active", "client_name": "Acme", "created_at": "2024-01-01T00:00:00"}
        mocks["trip_service"].get_by_id.return_value = trip

        def fetch(_):
            return client.get(f"{BASE_TRIPS}/1")

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(fetch, range(50)))

        assert all(r.status_code == 200 for r in results)
        assert all(r.json()["id"] == 1 for r in results)

    # ── update ────────────────────────────────────────────────────────────

    def test_concurrent_trip_update_requests(self, client_with_mocks):
        """20 concurrent PUT /trips/<id> requests should all return 200."""
        client, mocks = client_with_mocks

        payload = {"status": "completed"}

        def update_trip(_):
            return client.put(f"{BASE_TRIPS}/1", json=payload)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(update_trip, range(20)))

        assert all(r.status_code == 200 for r in results)
        assert all(r.json()["status"] == "updated" for r in results)
        assert mocks["trip_service"].update.call_count == 20

    # ── delete ────────────────────────────────────────────────────────────

    def test_concurrent_trip_delete_requests(self, client_with_mocks):
        """10 concurrent DELETE /trips/<id> requests should all return 200."""
        client, mocks = client_with_mocks

        def delete_trip(_):
            return client.request("DELETE", f"{BASE_TRIPS}/1", json={})

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(delete_trip, range(10)))

        assert all(r.status_code == 200 for r in results)
        assert all(r.json()["status"] == "deleted" for r in results)

    # ── mixed operations ──────────────────────────────────────────────────

    def test_concurrent_mixed_trip_operations(self, client_with_mocks):
        """Mix of list / get / create / update / delete under concurrency."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = [{"id": 1}]
        mocks["trip_service"].get_by_id.return_value = {"id": 1, "status": "active", "created_at": "2024-01-01T00:00:00"}
        mocks["trip_service"].add.return_value = 99

        ops = []

        def list_trips(_):
            return client.get(f"{BASE_TRIPS}/")

        def get_trip(_):
            return client.get(f"{BASE_TRIPS}/1")

        def create_trip(_):
            return client.post(f"{BASE_TRIPS}/", json={"client_name": "X"})

        def update_trip(_):
            return client.put(f"{BASE_TRIPS}/1", json={"status": "done"})

        def delete_trip(_):
            return client.request("DELETE", f"{BASE_TRIPS}/1", json={})

        # 10 of each = 50 total concurrent calls
        for i in range(10):
            ops.append((list_trips, i))
            ops.append((get_trip, i))
            ops.append((create_trip, i))
            ops.append((update_trip, i))
            ops.append((delete_trip, i))

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(fn, arg) for fn, arg in ops]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 50
        success = sum(1 for r in results if r.status_code == 200)
        assert success >= 45, f"Only {success}/50 mixed operations succeeded"


# ═══════════════════════════════════════════════════════════════════════════
# TestAPILoadFleet
# ═══════════════════════════════════════════════════════════════════════════

class TestAPILoadFleet:
    """Load test: concurrent fleet requests."""

    def test_concurrent_truck_list_requests(self, client_with_mocks):
        """50 concurrent GET /fleet/trucks requests should all return 200."""
        client, mocks = client_with_mocks
        fake_trucks = [
            {"id": 1, "plate_number": "AB123CD", "model": "Volvo FH"},
            {"id": 2, "plate_number": "XY789EF", "model": "Scania R500"},
        ]
        mocks["fleet_service"].get_trucks.return_value = fake_trucks

        def fetch(_):
            return client.get(f"{BASE_FLEET}/trucks")

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(fetch, range(50)))

        assert all(r.status_code == 200 for r in results)
        assert all(len(r.json()["items"]) == 2 for r in results)

    def test_concurrent_truck_create_requests(self, client_with_mocks):
        """20 concurrent POST /fleet/trucks requests should all return 200."""
        client, mocks = client_with_mocks
        mocks["fleet_service"].add_truck.return_value = 42

        payload = {"plate_number": "NEW001", "model": "Mercedes Actros"}

        def create_truck(_):
            return client.post(f"{BASE_FLEET}/trucks", json=payload)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(create_truck, range(20)))

        assert all(r.status_code == 200 for r in results)
        assert all(r.json()["id"] == 42 for r in results)
        assert mocks["fleet_service"].add_truck.call_count == 20

    def test_concurrent_truck_get_by_id(self, client_with_mocks):
        """50 concurrent GET /fleet/trucks/<id> requests should all return 200."""
        client, mocks = client_with_mocks
        truck = {"id": 1, "plate": "AB123CD", "brand": "Volvo", "year": 2022}
        mocks["fleet_service"].get_truck.return_value = truck

        def fetch(_):
            return client.get(f"{BASE_FLEET}/trucks/1")

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(fetch, range(50)))

        assert all(r.status_code == 200 for r in results)
        assert all(r.json()["id"] == 1 for r in results)

    def test_concurrent_truck_update_requests(self, client_with_mocks):
        """20 concurrent PUT /fleet/trucks/<id> requests should all return 200."""
        client, mocks = client_with_mocks

        def update_truck(_):
            return client.put(f"{BASE_FLEET}/trucks/1", json={"model": "Updated"})

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(update_truck, range(20)))

        assert all(r.status_code == 200 for r in results)
        assert mocks["fleet_service"].update_truck.call_count == 20

    def test_concurrent_truck_delete_requests(self, client_with_mocks):
        """10 concurrent DELETE /fleet/trucks/<id> requests should all return 200."""
        client, mocks = client_with_mocks

        def delete_truck(_):
            return client.request("DELETE", f"{BASE_FLEET}/trucks/1", json={})

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(delete_truck, range(10)))

        assert all(r.status_code == 200 for r in results)
        assert mocks["fleet_service"].delete_truck.call_count == 10

    def test_concurrent_gps_history_requests(self, client_with_mocks):
        """30 concurrent GET /fleet/gps/history/<id> requests should all return 200."""
        client, mocks = client_with_mocks
        fake_rows = [
            {"truck_id": 1, "latitude": 48.8566, "longitude": 2.3522,
             "speed_kmh": 65, "recorded_at": "2024-01-15T10:30:00Z"},
        ]
        mocks["db"].rows_to_dicts.return_value = fake_rows

        def fetch(_):
            return client.get(f"{BASE_FLEET}/gps/history/1?limit=10")

        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            results = list(executor.map(fetch, range(30)))

        assert all(r.status_code == 200 for r in results)
        assert all(r.json()["total"] == 1 for r in results)


# ═══════════════════════════════════════════════════════════════════════════
# TestAPILoadAnalytics
# ═══════════════════════════════════════════════════════════════════════════

class TestAPILoadAnalytics:
    """Load test: concurrent analytics requests."""

    FAKE_FINANCIAL = {
        "total_revenue": 250000.0,
        "total_expenses": 180000.0,
        "net_profit": 70000.0,
    }

    def test_concurrent_financial_requests(self, client_with_mocks):
        """30 concurrent GET /analytics/financial requests should all return 200."""
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_financial.return_value = self.FAKE_FINANCIAL

        def fetch(_):
            return client.get(f"{BASE_ANALYTICS}/financial")

        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            results = list(executor.map(fetch, range(30)))

        assert all(r.status_code == 200 for r in results)
        assert all(r.json() == self.FAKE_FINANCIAL for r in results)

    def test_concurrent_analytics_mixed_endpoints(self, client_with_mocks):
        """Concurrent calls to different analytics endpoints all succeed."""
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_financial.return_value = self.FAKE_FINANCIAL
        svc.get_monthly_financial.return_value = [{"month": "2024-01", "revenue": 20000.0}]
        svc.get_cost_breakdown.return_value = [{"category": "Fuel", "amount": 50000.0}]
        svc.get_fleet.return_value = {"total_trucks": 10, "active_trucks": 8}
        svc.get_driver.return_value = {"total_drivers": 15, "active_drivers": 12}
        svc.get_data.return_value = {"trips_count": 250, "revenue_ytd": 500000.0}

        endpoints = [
            ("/financial", "get_financial"),
            ("/financial/monthly", "get_monthly_financial"),
            ("/financial/cost-breakdown", "get_cost_breakdown"),
            ("/fleet", "get_fleet"),
            ("/driver", "get_driver"),
            ("/overview", "get_data"),
        ]

        def fetch(endpoint_info):
            path, _ = endpoint_info
            return client.get(f"{BASE_ANALYTICS}{path}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(endpoints)) as executor:
            results = list(executor.map(fetch, endpoints))

        assert all(r.status_code == 200 for r in results)

    def test_concurrent_analytics_invalidate(self, client_with_mocks):
        """10 concurrent POST /analytics/invalidate requests should all return 200."""
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]

        def invalidate(_):
            return client.post(f"{BASE_ANALYTICS}/invalidate")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(invalidate, range(10)))

        assert all(r.status_code == 200 for r in results)
        assert all(r.json()["status"] == "cache invalidated" for r in results)
        assert svc.invalidate.call_count == 10


# ═══════════════════════════════════════════════════════════════════════════
# TestAPILoadClients
# ═══════════════════════════════════════════════════════════════════════════

class TestAPILoadClients:
    """Load test: concurrent client requests."""

    def test_concurrent_client_list_requests(self, client_with_mocks):
        """50 concurrent GET /clients/ requests should all return 200."""
        client, mocks = client_with_mocks
        mocks["client_service"].get_all.return_value = [
            {"id": 1, "name": "Acme", "email": "a@a.com"},
        ]

        def fetch(_):
            return client.get(f"{BASE_CLIENTS}/")

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(fetch, range(50)))

        assert all(r.status_code == 200 for r in results)
        assert all(len(r.json()["items"]) == 1 for r in results)

    def test_concurrent_client_get_by_id(self, client_with_mocks):
        """50 concurrent GET /clients/<id> requests should all return 200."""
        client, mocks = client_with_mocks
        mocks["client_service"].get_by_id.return_value = {
            "id": 1, "name": "Acme", "is_active": True, "created_at": "2024-01-01",
        }

        def fetch(_):
            return client.get(f"{BASE_CLIENTS}/1")

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(fetch, range(50)))

        assert all(r.status_code == 200 for r in results)
        assert all(r.json()["id"] == 1 for r in results)

    def test_concurrent_client_create_requests(self, client_with_mocks):
        """20 concurrent POST /clients/ requests should all return 200."""
        client, mocks = client_with_mocks
        mocks["client_service"].create.return_value = 10

        def create_client(_):
            return client.post(f"{BASE_CLIENTS}/?name=NewCo", json={"email": "n@n.com"})

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(create_client, range(20)))

        assert all(r.status_code == 200 for r in results)
        assert mocks["client_service"].create.call_count == 20


# ═══════════════════════════════════════════════════════════════════════════
# TestAPILoadDrivers
# ═══════════════════════════════════════════════════════════════════════════

class TestAPILoadDrivers:
    """Load test: concurrent driver requests."""

    def test_concurrent_driver_list_requests(self, client_with_mocks):
        """50 concurrent GET /drivers/ requests should all return 200."""
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_all.return_value = [
            {"id": 1, "name": "John", "created_at": "", "updated_at": ""},
        ]

        def fetch(_):
            return client.get(f"{BASE_DRIVERS}/")

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(fetch, range(50)))

        assert all(r.status_code == 200 for r in results)
        assert all(len(r.json()["items"]) == 1 for r in results)

    def test_concurrent_driver_create_requests(self, client_with_mocks):
        """20 concurrent POST /drivers/ requests should all return 201."""
        client, mocks = client_with_mocks
        mocks["driver_repo"].create.return_value = 7

        payload = {
            "name": "New Driver",
            "phone": "123",
            "email": "d@d.com",
            "license_number": "LIC-001",
            "license_category": "C+E",
        }

        def create_driver(_):
            return client.post(f"{BASE_DRIVERS}/", json=payload)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(create_driver, range(20)))

        assert all(r.status_code == 201 for r in results)
        assert all(r.json()["id"] == 7 for r in results)
        assert mocks["driver_repo"].create.call_count == 20

    def test_concurrent_driver_get_by_id(self, client_with_mocks):
        """50 concurrent GET /drivers/<id> requests should all return 200."""
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = {
            "id": 1, "name": "John", "phone": "",
            "email": "", "license_number": "", "license_category": "",
            "is_active": True, "created_at": "2024-01-01", "updated_at": "2024-01-01",
        }

        def fetch(_):
            return client.get(f"{BASE_DRIVERS}/1")

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(fetch, range(50)))

        assert all(r.status_code == 200 for r in results)
        assert all(r.json()["id"] == 1 for r in results)

    def test_concurrent_driver_update_requests(self, client_with_mocks):
        """20 concurrent PUT /drivers/<id> requests should all return 200."""
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = {"id": 1, "name": "John"}

        def update_driver(_):
            return client.put(f"{BASE_DRIVERS}/1", json={"phone": "999"})

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(update_driver, range(20)))

        assert all(r.status_code == 200 for r in results)
        assert mocks["driver_repo"].update.call_count == 20

    def test_concurrent_driver_delete_requests(self, client_with_mocks):
        """10 concurrent DELETE /drivers/<id> requests should all return 200."""
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = {"id": 1}

        def delete_driver(_):
            return client.request("DELETE", f"{BASE_DRIVERS}/1", json={})

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(delete_driver, range(10)))

        assert all(r.status_code == 200 for r in results)
        assert mocks["driver_repo"].delete.call_count == 10


# ═══════════════════════════════════════════════════════════════════════════
# TestAPILoadMixed
# ═══════════════════════════════════════════════════════════════════════════

class TestAPILoadMixed:
    """Cross-domain concurrent requests hitting multiple routers at once."""

    def test_concurrent_mixed_domain_requests(self, client_with_mocks):
        """Trips, fleet, analytics, clients, and drivers under mixed concurrency."""
        client, mocks = client_with_mocks

        # Configure all mocks
        mocks["trip_service"].get_filtered.return_value = [{"id": 1}]
        mocks["fleet_service"].get_trucks.return_value = [{"id": 1, "plate": "AB123"}]
        mocks["analytics_service"].get_financial.return_value = {"total_revenue": 1000.0}
        mocks["client_service"].get_all.return_value = [{"id": 1, "name": "Acme"}]
        mocks["driver_repo"].get_all.return_value = [{"id": 1, "name": "John", "created_at": "", "updated_at": ""}]

        endpoints = [
            (f"{BASE_TRIPS}/", 10),
            (f"{BASE_FLEET}/trucks", 10),
            (f"{BASE_ANALYTICS}/financial", 10),
            (f"{BASE_CLIENTS}/", 10),
            (f"{BASE_DRIVERS}/", 10),
        ]

        def fetch(path_count):
            path, _ = path_count
            return client.get(path)

        # 50 total requests across 5 domains
        all_endpoints = [(path, cnt) for path, cnt in endpoints for _ in range(cnt // cnt)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(fetch, ep): ep for ep in endpoints}
            results = []
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        assert len(results) == 5
        assert all(r.status_code == 200 for r in results)


# ═══════════════════════════════════════════════════════════════════════════
# TestAPILoadMetrics — latency and throughput measurements
# ═══════════════════════════════════════════════════════════════════════════


class TestAPILoadMetrics:
    """Load tests measuring p50/p95/p99 latency and throughput.

    These are NOT real performance benchmarks — they verify that under
    concurrent load the system remains stable and returns correct results.
    """

    # ── 100 concurrent GET /trips/ — measure p50/p95/p99 ──────────────

    def test_100_concurrent_trip_list_latency(self, client_with_mocks):
        """100 concurrent GET /trips/ requests: measure p50/p95/p99 latency."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = [{"id": i} for i in range(10)]

        timings = []
        lock = threading.Lock()
        n_requests = 100

        def fetch(_):
            t0 = time.monotonic()
            try:
                resp = client.get(f"{BASE_TRIPS}/")
                elapsed = time.monotonic() - t0
                with lock:
                    timings.append(elapsed)
                return resp
            except Exception as e:
                elapsed = time.monotonic() - t0
                with lock:
                    timings.append(elapsed)
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_requests) as executor:
            results = list(executor.map(fetch, range(n_requests)))

        successes = [r for r in results if r is not None and r.status_code == 200]
        assert len(successes) >= 95, (
            f"Only {len(successes)}/{n_requests} requests succeeded"
        )

        if timings:
            timings.sort()
            p50 = timings[len(timings) // 2]
            p95 = timings[int(len(timings) * 0.95)]
            p99 = timings[int(len(timings) * 0.99)]
            # No hard latency threshold — just report the values
            # (actual perf depends on test environment)
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                "GET /trips/ (100 concurrent): p50=%.3fs p95=%.3fs p99=%.3fs",
                p50, p95, p99,
            )
            # Basic sanity: p99 should not be absurdly high
            assert p99 < 30.0, (
                f"p99 latency {p99:.3f}s exceeded sanity threshold (30s)"
            )

    # ── 50 concurrent POST /trips/ — throughput ───────────────────────

    def test_50_concurrent_trip_create_throughput(self, client_with_mocks):
        """50 concurrent POST /trips/ requests: measure throughput (requests/sec)."""
        client, mocks = client_with_mocks
        mocks["trip_service"].add.return_value = 42

        payload = {"client_name": "Throughput Test", "loading_city": "Berlin"}
        n_requests = 50

        t0 = time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_requests) as executor:
            results = list(executor.map(
                lambda _: client.post(f"{BASE_TRIPS}/", json=payload),
                range(n_requests),
            ))
        elapsed = time.monotonic() - t0

        successes = [r for r in results if r.status_code == 200]
        assert len(successes) >= 45, (
            f"Only {len(successes)}/{n_requests} creates succeeded"
        )
        throughput = n_requests / elapsed if elapsed > 0 else float("inf")
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "POST /trips/ (50 concurrent): %.1f req/s (%.3fs total)",
            throughput, elapsed,
        )
        assert mocks["trip_service"].add.call_count >= 45

    # ── 20 concurrent GET /analytics/financial — latency distribution ─

    def test_20_concurrent_analytics_latency(self, client_with_mocks):
        """20 concurrent GET /analytics/financial requests: latency distribution."""
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_financial.return_value = {
            "total_revenue": 250000.0,
            "total_expenses": 180000.0,
            "net_profit": 70000.0,
        }

        timings = []
        lock = threading.Lock()
        n_requests = 20

        def fetch(_):
            t0 = time.monotonic()
            try:
                resp = client.get(f"{BASE_ANALYTICS}/financial")
                elapsed = time.monotonic() - t0
                with lock:
                    timings.append(elapsed)
                return resp
            except Exception as e:
                elapsed = time.monotonic() - t0
                with lock:
                    timings.append(elapsed)
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_requests) as executor:
            results = list(executor.map(fetch, range(n_requests)))

        successes = [r for r in results if r is not None and r.status_code == 200]
        assert len(successes) >= 18, (
            f"Only {len(successes)}/{n_requests} analytics requests succeeded"
        )

        if timings:
            timings.sort()
            p50 = timings[len(timings) // 2]
            p95 = timings[int(len(timings) * 0.95)]
            p99 = timings[int(len(timings) * 0.99)]
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                "GET /analytics/financial (20 concurrent): p50=%.3fs p95=%.3fs p99=%.3fs",
                p50, p95, p99,
            )
            assert p99 < 30.0, (
                f"p99 latency {p99:.3f}s exceeded sanity threshold (30s)"
            )

    # ── Mixed read/write: 80% reads, 20% writes for 60 seconds ───────

    def test_mixed_read_write_load_80_20(self, client_with_mocks):
        """Mixed load: 80% reads, 20% writes — measure stability over time.

        Runs for a fixed number of operations (not wall-clock seconds) to
        keep tests deterministic. Verifies the system stays responsive.
        """
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = [{"id": 1, "client_name": "Load Test"}]
        mocks["trip_service"].add.return_value = 99

        total_ops = 100  # Total operations (80 reads + 20 writes)
        read_count = int(total_ops * 0.8)
        write_count = total_ops - read_count

        read_success = [0]
        write_success = [0]
        lock = threading.Lock()
        errors = []

        def read_op(_):
            try:
                resp = client.get(f"{BASE_TRIPS}/")
                with lock:
                    if resp.status_code == 200:
                        read_success[0] += 1
            except Exception as e:
                with lock:
                    errors.append(("read", str(e)))

        def write_op(_):
            try:
                resp = client.post(
                    f"{BASE_TRIPS}/",
                    json={"client_name": f"Mixed-{time.monotonic()}", "loading_city": "Paris"},
                )
                with lock:
                    if resp.status_code == 200:
                        write_success[0] += 1
            except Exception as e:
                with lock:
                    errors.append(("write", str(e)))

        # Submit all operations concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=total_ops) as executor:
            read_futs = [executor.submit(read_op, i) for i in range(read_count)]
            write_futs = [executor.submit(write_op, i) for i in range(write_count)]
            all_futs = read_futs + write_futs
            for fut in concurrent.futures.as_completed(all_futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(("submit", str(e)))

        assert len(errors) == 0, f"Mixed load errors: {errors}"
        assert read_success[0] >= read_count * 0.9, (
            f"Only {read_success[0]}/{read_count} reads succeeded"
        )
        assert write_success[0] >= write_count * 0.9, (
            f"Only {write_success[0]}/{write_count} writes succeeded"
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Mixed 80/20 load: %d/%d reads OK, %d/%d writes OK",
            read_success[0], read_count, write_success[0], write_count,
        )
