"""Integration tests for PrometheusMiddleware.

Tests cover:
- Middleware dispatches correctly on requests (200, 404, 500)
- HTTP request counter is incremented on each request
- Counter labels include method, normalized endpoint, and status code
- Path normalization for numeric IDs (→ {id}) and UUIDs (→ {uuid})
- Bucket histograms for latency are recorded
- Metrics endpoint returns valid Prometheus exposition format
- SLO recording failure is handled gracefully (no crash)
"""

from __future__ import annotations

import re
import uuid as _uuid

import pytest
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_sample_value(metric_name: str, labels: dict | None = None) -> float:
    """Read the current sample value for a Prometheus metric.

    Returns 0.0 if the metric or label combination does not exist.
    """
    try:
        samples = REGISTRY.get_sample_value(metric_name, labels or {})
        return samples if samples is not None else 0.0
    except Exception:
        return 0.0


def _build_app() -> FastAPI:
    """Create a FastAPI app with PrometheusMiddleware and test routes."""
    from backend.metrics import PrometheusMiddleware

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    @app.get("/test/404")
    async def not_found():
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    @app.get("/test/500")
    async def server_error():
        return JSONResponse(status_code=500, content={"detail": "Server error"})

    @app.get("/trips/123")
    async def trip_with_numeric_id():
        return {"trip_id": 123}

    @app.get("/trips/{item_id}")
    async def trip_with_param(item_id: str):
        return {"trip_id": item_id}

    @app.get("/metrics")
    async def metrics_endpoint():
        from backend.metrics import get_metrics_response
        return get_metrics_response()

    @app.post("/echo")
    async def echo(payload: dict):
        return {"received": payload}

    app.add_middleware(PrometheusMiddleware)
    return app


@pytest.fixture
def prometheus_app() -> FastAPI:
    return _build_app()


@pytest.fixture
def client(prometheus_app: FastAPI) -> TestClient:
    return TestClient(prometheus_app)


# ── Basic dispatch ───────────────────────────────────────────────────────


class TestPrometheusDispatch:
    """Verify the middleware does not interfere with normal request processing."""

    def test_get_request_returns_200(self, client: TestClient):
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_post_request_returns_200(self, client: TestClient):
        resp = client.post("/echo", json={"hello": "world"})
        assert resp.status_code == 200
        assert resp.json() == {"received": {"hello": "world"}}

    def test_404_passes_through(self, client: TestClient):
        resp = client.get("/test/404")
        assert resp.status_code == 404

    def test_500_passes_through(self, client: TestClient):
        resp = client.get("/test/500")
        assert resp.status_code == 500


# ── Request counter ─────────────────────────────────────────────────────


class TestRequestCounter:
    """Verify http_requests_total is incremented."""

    def test_counter_incremented_on_get(self, client: TestClient):
        before = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/test", "status": "200"},
        )
        client.get("/test")
        after = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/test", "status": "200"},
        )
        assert after == before + 1.0

    def test_counter_incremented_on_post(self, client: TestClient):
        before = _get_sample_value(
            "operion_http_requests_total",
            {"method": "POST", "endpoint": "/echo", "status": "200"},
        )
        client.post("/echo", json={"a": 1})
        after = _get_sample_value(
            "operion_http_requests_total",
            {"method": "POST", "endpoint": "/echo", "status": "200"},
        )
        assert after == before + 1.0

    def test_counter_reflects_status_code(self, client: TestClient):
        before = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/test/{id}", "status": "404"},
        )
        client.get("/test/404")
        after = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/test/{id}", "status": "404"},
        )
        # The path /test/404 has a purely numeric last segment → normalized to /test/{id}
        assert after == before + 1.0

    def test_counter_multiple_requests_accumulate(self, client: TestClient):
        before = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/test", "status": "200"},
        )
        for _ in range(5):
            client.get("/test")
        after = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/test", "status": "200"},
        )
        assert after == before + 5.0

    def test_counter_labels_include_method_endpoint_status(self, client: TestClient):
        """Verify the counter exists with proper label structure."""
        client.get("/test")
        value = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/test", "status": "200"},
        )
        assert value > 0


# ── Path normalization ──────────────────────────────────────────────────


class TestPathNormalization:
    """Verify _get_endpoint normalizes paths to avoid metric explosion."""

    def test_numeric_id_normalized_to_id_placeholder(self, client: TestClient):
        """A path segment consisting only of digits becomes {id}."""
        client.get("/trips/123")
        # The route is /trips/{item_id} and receives "123" which is all digits
        value = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/trips/{id}", "status": "200"},
        )
        assert value > 0, "Expected normalized path /trips/{id} for numeric segment"

    def test_uuid_normalized_to_uuid_placeholder(self, client: TestClient):
        """A path segment matching UUID format becomes {uuid}."""
        uid = "550e8400-e29b-41d4-a716-446655440000"
        client.get(f"/trips/{uid}")
        value = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/trips/{uuid}", "status": "200"},
        )
        assert value > 0, "Expected normalized path /trips/{uuid} for UUID segment"

    def test_text_segment_preserved_as_is(self, client: TestClient):
        """Non-numeric, non-UUID segments are left unchanged."""
        client.get("/test")
        value = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/test", "status": "200"},
        )
        assert value > 0

    def test_mixed_path_components_normalized_correctly(self, client: TestClient):
        """Path with multiple segments each normalized independently.

        /api/v1/trips/abc/123 → /api/v1/trips/abc/{id}
        """
        from backend.metrics import PrometheusMiddleware

        class _MockRequest:
            class url:
                path = "/api/v1/trips/abc/123"

        result = PrometheusMiddleware._get_endpoint(_MockRequest())  # type: ignore[arg-type]
        assert result == "/api/v1/trips/abc/{id}"

    def test_mixed_path_with_uuid_normalized(self):
        """Path with a UUID segment gets normalized to {uuid}."""
        from backend.metrics import PrometheusMiddleware

        class _MockRequest:
            class url:
                path = "/api/v1/documents/550e8400-e29b-41d4-a716-446655440000/download"

        result = PrometheusMiddleware._get_endpoint(_MockRequest())  # type: ignore[arg-type]
        assert result == "/api/v1/documents/{uuid}/download"

    def test_empty_path_segments_handled(self):
        """Empty segments (e.g., trailing slash) remain empty in the result."""
        from backend.metrics import PrometheusMiddleware

        class _MockRequest:
            class url:
                path = "/"

        result = PrometheusMiddleware._get_endpoint(_MockRequest())  # type: ignore[arg-type]
        assert result == "/"


# ── Latency histogram ───────────────────────────────────────────────────


class TestLatencyHistogram:
    """Verify http_request_duration_seconds records observations."""

    def test_histogram_has_observation(self, client: TestClient):
        """After a request, the histogram should have at least one observation."""
        client.get("/test")
        # Check the _count sample exists (guaranteed by prometheus_client)
        count = _get_sample_value(
            "operion_http_request_duration_seconds_count",
            {"method": "GET", "endpoint": "/test"},
        )
        assert count > 0, "Expected at least one histogram observation"

    def test_histogram_sum_is_positive(self, client: TestClient):
        """The _sum sample should be a positive duration."""
        client.get("/test")
        total = _get_sample_value(
            "operion_http_request_duration_seconds_sum",
            {"method": "GET", "endpoint": "/test"},
        )
        assert total > 0, "Expected positive duration sum"

    def test_histogram_buckets_configured(self):
        """Verify the histogram has the expected bucket boundaries."""
        from backend.metrics import http_request_duration_seconds

        expected = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        # Prometheus stores upper bounds with +Inf appended
        bounds = list(http_request_duration_seconds._upper_bounds)
        # Strip the +Inf sentinel for comparison
        user_bounds = [b for b in bounds if b != float("inf")]
        assert user_bounds == expected, (
            f"Expected buckets {expected}, got {user_bounds}"
        )

    def test_histogram_multiple_requests_accumulate(self, client: TestClient):
        """Multiple requests increase both count and sum."""
        client.get("/test")
        count_1 = _get_sample_value(
            "operion_http_request_duration_seconds_count",
            {"method": "GET", "endpoint": "/test"},
        )
        client.get("/test")
        count_2 = _get_sample_value(
            "operion_http_request_duration_seconds_count",
            {"method": "GET", "endpoint": "/test"},
        )
        assert count_2 == count_1 + 1.0


# ── Metrics endpoint ────────────────────────────────────────────────────


class TestMetricsEndpoint:
    """Verify the /metrics endpoint returns valid Prometheus exposition format."""

    def test_metrics_endpoint_returns_200(self, client: TestClient):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_content_type_is_prometheus(self, client: TestClient):
        resp = client.get("/metrics")
        ct = resp.headers.get("content-type", "")
        assert ct.startswith("text/plain"), (
            f"Expected text/plain content-type, got {ct!r}"
        )
        assert "charset=utf-8" in ct

    def test_metrics_contains_http_requests_total(self, client: TestClient):
        """The metrics output must include our HTTP request counter."""
        client.get("/test")  # generate at least one sample
        resp = client.get("/metrics")
        body = resp.text
        assert "# HELP operion_http_requests_total" in body
        assert "# TYPE operion_http_requests_total counter" in body

    def test_metrics_contains_http_request_duration_seconds(self, client: TestClient):
        """The metrics output must include our latency histogram."""
        client.get("/test")
        resp = client.get("/metrics")
        body = resp.text
        assert "# HELP operion_http_request_duration_seconds" in body
        assert "# TYPE operion_http_request_duration_seconds histogram" in body

    def test_metrics_format_line_protocol(self, client: TestClient):
        """Each metric line must match Prometheus exposition format."""
        client.get("/test")
        resp = client.get("/metrics")
        body = resp.text
        lines = body.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # comments and HELP/TYPE lines
            # Data lines: metric_name{labels} value
            assert re.match(
                r"^[a-zA-Z_:][a-zA-Z0-9_:]*(\{.+?\})?\s+\S+$", line
            ), f"Line does not match Prometheus format: {line!r}"

    def test_metrics_includes_bucket_lines(self, client: TestClient):
        """Histogram bucket lines (le=...) appear after a request."""
        client.get("/test")
        resp = client.get("/metrics")
        body = resp.text
        assert re.search(
            r'operion_http_request_duration_seconds_bucket\{.*le="0\.01".*\}',
            body,
        ), "Expected a bucket line for le=0.01"

    def test_metrics_includes_inf_bucket(self, client: TestClient):
        """The +Inf bucket line must be present for every histogram."""
        client.get("/test")
        resp = client.get("/metrics")
        body = resp.text
        assert re.search(
            r'operion_http_request_duration_seconds_bucket\{.*le="\+Inf".*\}',
            body,
        ), "Expected +Inf bucket line"


# ── SLO recording failure handling ──────────────────────────────────────


class TestSloFailureHandling:
    """Verify PrometheusMiddleware does not crash when SLO recording fails."""

    def test_slo_failure_does_not_crash(self, client: TestClient, monkeypatch):
        """When get_slo_service raises, the middleware logs a warning and continues."""
        import backend.metrics as metrics_module

        def _broken_slo():
            raise RuntimeError("SLO service unavailable")

        monkeypatch.setattr(metrics_module, "get_slo_service", _broken_slo)

        # This should NOT raise despite the SLO failure
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_counter_still_incremented_on_slo_failure(
        self, client: TestClient, monkeypatch
    ):
        """Even when SLO fails, the HTTP counter must increment."""
        import backend.metrics as metrics_module

        def _broken_slo():
            raise RuntimeError("SLO service unavailable")

        monkeypatch.setattr(metrics_module, "get_slo_service", _broken_slo)

        before = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/test", "status": "200"},
        )
        client.get("/test")
        after = _get_sample_value(
            "operion_http_requests_total",
            {"method": "GET", "endpoint": "/test", "status": "200"},
        )
        assert after == before + 1.0
