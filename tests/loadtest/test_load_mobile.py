"""Load tests for the mobile endpoint suite (runbook §13.7).

Scenarios — all authenticated (auth dependencies overridden to a dispatcher),
asserting HTTP 200 and the envelope/JSON shape each router returns:

  GET /api/v1/mobile/fleet?page=1&page_size=20
  GET /api/v1/mobile/drivers?search=&status=
  GET /api/v1/mobile/clients?search=
  GET /api/v1/mobile/invoices?page=1&page_size=20
  GET /api/v1/mobile/history/trips?page=1&page_size=20
  GET /api/v1/mobile/search?q=
  GET /api/v1/mobile/sync?entity=fleet&since=0
  GET /api/v1/mobile/sync?entity=drivers&since=<ISO>

Follows the existing test_load_clients.py pattern (FastAPI TestClient +
``run_concurrent``) — no live server needed.  The ``real_db`` / ``mobile_app`` /
``mobile_client`` fixtures are re-exported from tests.mobile.conftest so the
endpoints hit the real schema and repositories (same pattern the mobile API
tests use).
"""
from __future__ import annotations

import pytest

from tests.loadtest.conftest import run_concurrent
from tests.mobile.conftest import (  # noqa: F401  (fixture re-exports)
    dispatcher_user,
    mobile_app,
    mobile_client,
    real_db,
    seed_records,
)

pytestmark = pytest.mark.slow

BASE = "/api/v1/mobile"

# A cursor older than every seeded driver.updated_at so delta-sync returns rows.
_SINCE_ISO = "2020-01-01T00:00:00Z"


@pytest.fixture
def seeded(real_db):
    """Seed the standard record set (company 1) for the load scenarios."""
    return seed_records(real_db, company_id=1)


def _assert_paginated(body: dict) -> None:
    assert isinstance(body, dict)
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body, f"paginated envelope missing {key}"


def _assert_sync(body: dict) -> None:
    assert isinstance(body, dict)
    for key in ("records", "cursor", "has_more"):
        assert key in body, f"sync envelope missing {key}"


def _assert_search(body: dict) -> None:
    assert isinstance(body, dict)
    for key in ("trips", "clients", "drivers", "trucks", "documents"):
        assert key in body, f"search section missing {key}"
        assert "items" in body[key], f"search section {key} missing items"
        assert "total_count" in body[key], f"search section {key} missing total_count"


def _run(mobile_client, url: str, n: int):
    def make_request():
        return mobile_client.get(url)

    results, timings, errors, elapsed = run_concurrent(make_request, n)
    success_rate = len(results) / n if n else 1.0
    assert success_rate >= 0.99, f"{url} success_rate={success_rate:.3f} at n={n}"
    assert not errors, f"{url} raised errors at n={n}: {errors[:3]}"
    for r in results:
        assert r.status_code == 200, f"{url} returned {r.status_code}: {r.text[:200]}"
    return results


class TestLoadMobileReads:
    """Concurrent GETs on the mobile entity list endpoints."""

    def test_fleet_list(self, mobile_app, mobile_client, seeded):
        for n in (1, 10, 50):
            results = _run(mobile_client, f"{BASE}/fleet?page=1&page_size=20", n)
            for r in results:
                body = r.json()
                _assert_paginated(body)
                for item in body["items"]:
                    assert "id" in item and "plate" in item and "status" in item

    def test_drivers_list(self, mobile_app, mobile_client, seeded):
        for n in (1, 10, 50):
            results = _run(mobile_client, f"{BASE}/drivers?search=&status=", n)
            for r in results:
                body = r.json()
                _assert_paginated(body)
                for item in body["items"]:
                    assert "id" in item and "name" in item and "status" in item

    def test_clients_list(self, mobile_app, mobile_client, seeded):
        for n in (1, 10, 50):
            results = _run(mobile_client, f"{BASE}/clients?search=", n)
            for r in results:
                body = r.json()
                _assert_paginated(body)
                for item in body["items"]:
                    assert "id" in item and "name" in item and "is_active" in item

    def test_invoices_list(self, mobile_app, mobile_client, seeded):
        for n in (1, 10, 50):
            results = _run(mobile_client, f"{BASE}/invoices?page=1&page_size=20", n)
            for r in results:
                body = r.json()
                _assert_paginated(body)
                for item in body["items"]:
                    assert "id" in item and "invoice_number" in item and "status" in item

    def test_history_trips(self, mobile_app, mobile_client, seeded):
        for n in (1, 10, 50):
            results = _run(mobile_client, f"{BASE}/history/trips?page=1&page_size=20", n)
            for r in results:
                body = r.json()
                _assert_paginated(body)
                for item in body["items"]:
                    assert "id" in item and "client_name" in item and "status" in item

    def test_search(self, mobile_app, mobile_client, seeded):
        for n in (1, 10, 50):
            results = _run(mobile_client, f"{BASE}/search?q=ACME", n)
            for r in results:
                _assert_search(r.json())


class TestLoadMobileSync:
    """Concurrent GETs on the delta-sync endpoint."""

    def test_sync_fleet(self, mobile_app, mobile_client, seeded):
        for n in (1, 10, 50):
            results = _run(mobile_client, f"{BASE}/sync?entity=fleet&since=0", n)
            for r in results:
                body = r.json()
                _assert_sync(body)
                for record in body["records"]:
                    assert "id" in record and "plate_number" in record

    def test_sync_drivers(self, mobile_app, mobile_client, seeded):
        url = f"{BASE}/sync?entity=drivers&since={_SINCE_ISO}"
        for n in (1, 10, 50):
            results = _run(mobile_client, url, n)
            for r in results:
                body = r.json()
                _assert_sync(body)
                for record in body["records"]:
                    assert "id" in record and "name" in record
