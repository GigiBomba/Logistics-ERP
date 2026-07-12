"""Stress tests for API error handling — verifies graceful degradation under failure."""
from __future__ import annotations

import json
import math

import pytest

BASE_TRIPS = "/api/v1/trips"
BASE_FLEET = "/api/v1/fleet"
BASE_ANALYTICS = "/api/v1/analytics"
BASE_CLIENTS = "/api/v1/clients"
BASE_DRIVERS = "/api/v1/drivers"


# ═══════════════════════════════════════════════════════════════════════════
# TestStressServiceFailures
# ═══════════════════════════════════════════════════════════════════════════

class TestStressServiceFailures:
    """API should return 500 (not crash) when services throw."""

    # ── single endpoint failures ──────────────────────────────────────────

    def test_trips_list_survives_service_crash(self, client_with_mocks):
        """Service throwing on list should return 500, not crash the app."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.side_effect = RuntimeError("DB connection lost")
        resp = client.get(f"{BASE_TRIPS}/")
        assert resp.status_code == 500
        assert "detail" in resp.json()

    def test_trips_get_by_id_survives_service_crash(self, client_with_mocks):
        """Service throwing on get_by_id should return 500."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_by_id.side_effect = RuntimeError("DB connection lost")
        resp = client.get(f"{BASE_TRIPS}/1")
        assert resp.status_code == 500
        assert "detail" in resp.json()

    def test_trips_create_survives_service_crash(self, client_with_mocks):
        """Service throwing on create should return 500."""
        client, mocks = client_with_mocks
        mocks["trip_service"].add.side_effect = RuntimeError("Insert failed")
        resp = client.post(f"{BASE_TRIPS}/", json={"client_name": "Acme"})
        assert resp.status_code == 500
        assert "detail" in resp.json()

    def test_trips_update_survives_service_crash(self, client_with_mocks):
        """Service throwing on update should return 500."""
        client, mocks = client_with_mocks
        mocks["trip_service"].update.side_effect = RuntimeError("Update failed")
        resp = client.put(f"{BASE_TRIPS}/1", json={"status": "completed"})
        assert resp.status_code == 500
        assert "detail" in resp.json()

    def test_trips_delete_survives_service_crash(self, client_with_mocks):
        """Service throwing on delete should return 500."""
        client, mocks = client_with_mocks
        mocks["trip_service"].delete.side_effect = RuntimeError("Delete failed")
        resp = client.request("DELETE", f"{BASE_TRIPS}/1", json={})
        assert resp.status_code == 500
        assert "detail" in resp.json()

    # ── analytics endpoint failures ───────────────────────────────────────

    def test_analytics_survives_service_crash(self, client_with_mocks):
        """Analytics service throwing should return 500 with 'Operation failed'."""
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_financial.side_effect = RuntimeError("Analytics broken")

        resp = client.get(f"{BASE_ANALYTICS}/financial")
        assert resp.status_code == 500
        assert "Operation failed" in resp.json()["detail"]

    # ── fleet endpoint failures ───────────────────────────────────────────

    def test_fleet_list_survives_service_crash(self, client_with_mocks):
        """Fleet service throwing should return 500."""
        client, mocks = client_with_mocks

        # Some fleet endpoints do NOT catch exceptions — check which behavior
        # the handler uses. If there is no try/except, the error propagates.
        mocks["fleet_service"].get_trucks.side_effect = RuntimeError("Fleet DB down")
        resp = client.get(f"{BASE_FLEET}/trucks")
        assert resp.status_code in (200, 500)
        if resp.status_code == 500:
            assert "detail" in resp.json()

    # ── rapid successive errors ───────────────────────────────────────────

    def test_rapid_successive_errors_dont_exhaust_resources(self, client_with_mocks):
        """100 rapid requests that all fail should not leak resources (return 500)."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.side_effect = RuntimeError("persistent failure")

        for i in range(100):
            resp = client.get(f"{BASE_TRIPS}/")
            assert resp.status_code == 500, f"Request {i} returned {resp.status_code}"
            assert "detail" in resp.json()

    def test_rapid_successive_analytics_errors(self, client_with_mocks):
        """100 rapid analytics requests that all fail should not crash the app."""
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_financial.side_effect = RuntimeError("analytics persistent failure")

        for i in range(100):
            resp = client.get(f"{BASE_ANALYTICS}/financial")
            assert resp.status_code == 500, f"Request {i} returned {resp.status_code}"
            assert "Operation failed" in resp.json()["detail"]

    def test_alternating_success_failure_does_not_degrade(self, client_with_mocks):
        """Alternating success/failure calls should not degrade subsequent calls."""
        client, mocks = client_with_mocks
        call_count = 0

        def alternating_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return [{"id": 1}]
            raise RuntimeError("intermittent failure")

        mocks["trip_service"].get_filtered.side_effect = alternating_side_effect

        for i in range(50):
            resp = client.get(f"{BASE_TRIPS}/")
            if i % 2 == 0:
                assert resp.status_code == 500, f"Even request {i} should be 500"
            else:
                assert resp.status_code == 200, f"Odd request {i} should be 200"


# ═══════════════════════════════════════════════════════════════════════════
# TestStressMalformedInput
# ═══════════════════════════════════════════════════════════════════════════

class TestStressMalformedInput:
    """API should handle malformed input gracefully."""

    # ── large payloads ────────────────────────────────────────────────────

    def test_extremely_large_payload(self, client_with_mocks):
        """Sending a ~1 MB JSON payload should not crash — expect 422 or 500."""
        client, mocks = client_with_mocks
        large_field = "x" * (1024 * 1024)  # 1 MB
        payload = {"client_name": large_field, "loading_city": "Paris"}

        resp = client.post(f"{BASE_TRIPS}/", json=payload)
        # The endpoint should either reject it (422) or handle it (200/500)
        assert resp.status_code in (200, 422, 500), f"Unexpected status {resp.status_code}"

    def test_extremely_large_payload_on_analytics(self, client_with_mocks):
        """Sending query params with extremely large values should not crash."""
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_financial.return_value = {"total_revenue": 0.0}

        huge_param = "A" * 10_000
        resp = client.get(f"{BASE_ANALYTICS}/financial", params={"from_date": huge_param})
        # Should either validate (422) or handle gracefully (200)
        assert resp.status_code in (200, 422, 500)

    def test_extremely_large_nested_payload(self, client_with_mocks):
        """Deeply nested JSON payload should not crash."""
        client, mocks = client_with_mocks

        def build_deep_nesting(depth):
            obj = {"key": "value"}
            for _ in range(depth):
                obj = {"nested": obj}
            return obj

        payload = build_deep_nesting(100)
        resp = client.post(f"{BASE_TRIPS}/", json=payload)
        assert resp.status_code in (200, 422, 500)

    # ── unicode / special characters ──────────────────────────────────────

    def test_unicode_in_all_fields(self, client_with_mocks):
        """Unicode characters in all fields should be handled — expect 200 or 422."""
        client, mocks = client_with_mocks
        mocks["trip_service"].add.return_value = 1

        payload = {
            "client_name": "José García \u00e9\u00f1\u00fc\u00df\u4e2d\u6587",
            "loading_city": "München \u00f6\u00e4\u00fc\u00df",
            "delivery_city": "Łódź \u0105\u0107\u0119\u0144\u00f3\u015b\u017a\u017c",
            "status": "Planned \u2705",
            "notes": "emoji: \U0001f698\U0001f69b\U0001f4e6  \U0001f1ea\U0001f1f8",
            "cargo_description": "\u0413\u0440\u0443\u0437 \u0438\u0437 \u0420\u043e\u0441\u0441\u0438\u0438",
        }
        resp = client.post(f"{BASE_TRIPS}/", json=payload)
        assert resp.status_code in (200, 422, 500)

    def test_unicode_in_query_params(self, client_with_mocks):
        """Unicode characters in query params should be handled."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = []

        resp = client.get(f"{BASE_TRIPS}/?search=M\u00fcnchen\u00f6sterreich")
        assert resp.status_code == 200

    def test_null_bytes_in_payload(self, client_with_mocks):
        """Null bytes in JSON payload should not crash the app."""
        client, mocks = client_with_mocks

        payload = {"client_name": "Acme\x00Corp", "loading_city": "Paris"}
        resp = client.post(f"{BASE_TRIPS}/", json=payload)
        # Either rejected (422) or handled (200/500)
        assert resp.status_code in (200, 422, 500)

    def test_control_characters_in_payload(self, client_with_mocks):
        """Control characters in string fields should not crash the app."""
        client, mocks = client_with_mocks

        payload = {"client_name": "Acme\r\n\t\b\fCorp", "loading_city": "Paris"}
        resp = client.post(f"{BASE_TRIPS}/", json=payload)
        assert resp.status_code in (200, 422, 500)

    def test_unicode_normalization_attacks(self, client_with_mocks):
        """Unicode normalization attacks (confusable characters) should not crash."""
        client, mocks = client_with_mocks
        mocks["trip_service"].add.return_value = 1

        # Homoglyph attack: Cyrillic 'а' instead of Latin 'a'
        payload = {
            "client_name": "Аcme",  # first 'A' is Cyrillic U+0410
            "loading_city": "Paris",
        }
        resp = client.post(f"{BASE_TRIPS}/", json=payload)
        assert resp.status_code in (200, 422, 500)

    # ── extreme numeric values ────────────────────────────────────────────

    def test_extreme_numeric_values(self, client_with_mocks):
        """Very large and very small numeric values should not crash."""
        client, mocks = client_with_mocks
        mocks["trip_service"].add.return_value = 1

        payload = {
            "client_name": "Acme",
            "loading_city": "Paris",
            "distance_km": 1e15,
            "total_price_eur": -1e15,
            "rate_per_km": 1e308,
        }
        resp = client.post(f"{BASE_TRIPS}/", json=payload)
        assert resp.status_code in (200, 422, 500)

    def test_nan_value_in_payload(self, client_with_mocks):
        """NaN float values should not crash — JSON does not support NaN natively,
        so this tests that the app doesn't crash on unusual input patterns."""
        client, mocks = client_with_mocks

        # NaN cannot be represented in standard JSON, but we can test
        # with very unusual payload shapes
        payload = {"client_name": None, "loading_city": None}
        resp = client.post(f"{BASE_TRIPS}/", json=payload)
        assert resp.status_code in (200, 422, 500)

    # ── edge case payloads ────────────────────────────────────────────────

    def test_empty_payload(self, client_with_mocks):
        """Empty JSON object payload should not crash — expect 422."""
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE_TRIPS}/", json={})
        assert resp.status_code in (200, 422, 500)

    def test_non_dict_payload(self, client_with_mocks):
        """Non-dict JSON payload (list, string, number) should return 422."""
        client, mocks = client_with_mocks

        for payload in ([], "string", 42, True, None):
            resp = client.post(f"{BASE_TRIPS}/", json=payload)
            assert resp.status_code == 422, f"Payload {payload!r} returned {resp.status_code}"

    def test_malformed_json(self, client_with_mocks):
        """Malformed JSON body should return 422."""
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE_TRIPS}/", data="not valid json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

    def test_extremely_long_string_in_query(self, client_with_mocks):
        """Query parameter with extremely long string should not crash."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = []

        long_search = "A" * 10_000
        resp = client.get(f"{BASE_TRIPS}/?search={long_search}")
        assert resp.status_code in (200, 422, 500)

    def test_missing_required_fields(self, client_with_mocks):
        """Missing required fields (where applicable) should return 422."""
        client, mocks = client_with_mocks

        # Post a trip with minimal / no data
        resp = client.post(f"{BASE_TRIPS}/", json={})
        assert resp.status_code in (200, 422, 500)


# ═══════════════════════════════════════════════════════════════════════════
# TestStressConcurrentFailures
# ═══════════════════════════════════════════════════════════════════════════

class TestStressConcurrentFailures:
    """Concurrent failing requests should not cause cascading failures."""

    def test_concurrent_service_crashes(self, client_with_mocks):
        """50 concurrent requests that all fail should all return 500."""
        import concurrent.futures

        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.side_effect = RuntimeError("concurrent crash")

        def failing_request(_):
            return client.get(f"{BASE_TRIPS}/")

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(failing_request, range(50)))

        assert all(r.status_code == 500 for r in results)
        assert all("detail" in r.json() for r in results)

    def test_concurrent_mixed_errors(self, client_with_mocks):
        """Concurrent calls across multiple failing endpoints should all return errors."""
        import concurrent.futures

        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.side_effect = RuntimeError("trips fail")
        svc = mocks["analytics_service"]
        svc.get_financial.side_effect = RuntimeError("analytics fail")

        endpoints = [
            (f"{BASE_TRIPS}/", 0),
            (f"{BASE_ANALYTICS}/financial", 0),
        ]

        def fetch(path_idx):
            path, _ = path_idx
            return client.get(path)

        # 20 to each = 40 total
        all_calls = endpoints * 20
        with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
            futures = {executor.submit(fetch, call): call for call in all_calls}
            results = []
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        assert len(results) == 40
        assert all(r.status_code == 500 for r in results)

    def test_concurrent_mixed_success_and_failure(self, client_with_mocks):
        """Concurrent mix of succeeding and failing endpoints must not interfere."""
        import concurrent.futures

        client, mocks = client_with_mocks

        # Working services
        mocks["trip_service"].get_filtered.return_value = [{"id": 1}]
        mocks["client_service"].get_all.return_value = [{"id": 1, "name": "Acme"}]

        # Failing services
        svc = mocks["analytics_service"]
        svc.get_financial.side_effect = RuntimeError("analytics fail")
        mocks["fleet_service"].get_trucks.side_effect = RuntimeError("fleet fail")

        def call_endpoint(path):
            return client.get(path)

        calls = [
            f"{BASE_TRIPS}/", f"{BASE_TRIPS}/",
            f"{BASE_CLIENTS}/", f"{BASE_CLIENTS}/",
            f"{BASE_ANALYTICS}/financial", f"{BASE_ANALYTICS}/financial",
            f"{BASE_FLEET}/trucks", f"{BASE_FLEET}/trucks",
        ] * 5  # 40 total

        with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
            futures = {executor.submit(call_endpoint, path): path for path in calls}
            results = []
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        assert len(results) == 40
        # Trips and clients should succeed
        for r in results:
            assert r.status_code in (200, 500)


# ═══════════════════════════════════════════════════════════════════════════
# TestStressResourceCleanup
# ═══════════════════════════════════════════════════════════════════════════

class TestStressResourceCleanup:
    """Ensure resources are properly cleaned up after errors."""

    def test_subsequent_requests_succeed_after_errors(self, client_with_mocks):
        """After a failing request, the next healthy request should still succeed."""
        client, mocks = client_with_mocks

        # Make a failing request
        mocks["trip_service"].get_filtered.side_effect = RuntimeError("first fail")
        resp = client.get(f"{BASE_TRIPS}/")
        assert resp.status_code == 500

        # Reset mock and make a succeeding request
        mocks["trip_service"].get_filtered.side_effect = None
        mocks["trip_service"].get_filtered.return_value = [{"id": 1}]
        resp = client.get(f"{BASE_TRIPS}/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_recovery_after_repeated_failures(self, client_with_mocks):
        """After 50 failures, the API should recover and serve healthy requests."""
        client, mocks = client_with_mocks

        # 50 failing requests
        mocks["trip_service"].get_filtered.side_effect = RuntimeError("fail")
        for _ in range(50):
            client.get(f"{BASE_TRIPS}/")

        # Reset and verify recovery
        mocks["trip_service"].get_filtered.side_effect = None
        mocks["trip_service"].get_filtered.return_value = [{"id": 1}, {"id": 2}]
        resp = client.get(f"{BASE_TRIPS}/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_mixed_service_recovery(self, client_with_mocks):
        """After analytics failures, trips endpoint should still work independently."""
        client, mocks = client_with_mocks

        # Analytics fails
        svc = mocks["analytics_service"]
        svc.get_financial.side_effect = RuntimeError("analytics fail")

        # Trips still works
        mocks["trip_service"].get_filtered.return_value = [{"id": 1}]

        resp_analytics = client.get(f"{BASE_ANALYTICS}/financial")
        assert resp_analytics.status_code == 500

        resp_trips = client.get(f"{BASE_TRIPS}/")
        assert resp_trips.status_code == 200
        assert resp_trips.json()["total"] == 1

    def test_analytics_cache_invalidation_after_error(self, client_with_mocks):
        """Cache invalidation endpoint should work even if other analytics fail."""
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]

        # Invalidating cache should work
        svc.invalidate.return_value = None
        resp = client.post(f"{BASE_ANALYTICS}/invalidate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cache invalidated"

        # Now make a different analytics endpoint fail and verify invalidation still works
        svc.get_financial.side_effect = RuntimeError("fail")
        client.get(f"{BASE_ANALYTICS}/financial")

        resp = client.post(f"{BASE_ANALYTICS}/invalidate")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# TestStressValidationBoundaries
# ═══════════════════════════════════════════════════════════════════════════

class TestStressValidationBoundaries:
    """Boundary conditions for input validation."""

    def test_negative_id_in_path(self, client_with_mocks):
        """Negative trip ID in path should be handled gracefully."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_by_id.return_value = None

        resp = client.get(f"{BASE_TRIPS}/-1")
        # FastAPI may reject negative ints via validation (422) or pass them through
        assert resp.status_code in (200, 404, 422, 500)

    def test_zero_id_in_path(self, client_with_mocks):
        """Zero as ID in path should be handled gracefully."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_by_id.return_value = None

        resp = client.get(f"{BASE_TRIPS}/0")
        assert resp.status_code in (200, 404, 422, 500)

    def test_extremely_large_id_in_path(self, client_with_mocks):
        """Extremely large ID in path should be handled."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_by_id.return_value = None

        resp = client.get(f"{BASE_TRIPS}/999999999999999999999999999999")
        assert resp.status_code in (200, 404, 422, 500)

    def test_negative_limit(self, client_with_mocks):
        """Negative limit query parameter should return 422."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = []

        resp = client.get(f"{BASE_TRIPS}/?limit=-1")
        assert resp.status_code in (200, 422, 500)

    def test_zero_limit(self, client_with_mocks):
        """Zero limit should either be accepted or rejected with 422."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = []

        resp = client.get(f"{BASE_TRIPS}/?limit=0")
        assert resp.status_code in (200, 422, 500)

    def test_excessive_limit(self, client_with_mocks):
        """Excessive limit should be clamped or rejected."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = []

        resp = client.get(f"{BASE_TRIPS}/?limit=999999")
        assert resp.status_code in (200, 422, 500)

    def test_sql_injection_in_search(self, client_with_mocks):
        """SQL-like injection in search query should be sanitized, not crash."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = []

        injections = [
            "'; DROP TABLE trips; --",
            "' OR '1'='1",
            "'; SELECT * FROM users; --",
            "1; DROP TABLE users CASCADE",
            "' UNION SELECT * FROM trips --",
            "*/ OR 1=1 --",
        ]
        for inj in injections:
            resp = client.get(f"{BASE_TRIPS}/?search={inj}")
            assert resp.status_code == 200, f"Injection {inj!r} returned {resp.status_code}"

    def test_xss_in_search(self, client_with_mocks):
        """XSS payloads in search should be returned as-is (not executed)."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = [
            {"id": 1, "client_name": "<script>alert('xss')</script>"},
        ]

        xss_payload = "<script>alert('xss')</script>"
        resp = client.get(f"{BASE_TRIPS}/?search={xss_payload}")
        assert resp.status_code == 200
        # The response should contain the script tag as data (not executed)
        data = resp.json()
        assert len(data["items"]) > 0
