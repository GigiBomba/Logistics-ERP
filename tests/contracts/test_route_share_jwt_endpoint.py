"""Contract tests for ``GET /api/v1/mobile/driver/route-share`` (JWT-resolved).

The parallel mobile lane consumes a route-share endpoint that takes NO
``transport_id`` in the path: the server resolves the driver's CURRENT
transport from the JWT (``_resolve_driver_id`` + the same current-trip query
as ``/driver/trip-overview``), so the client can never influence which
transport is shared (no IDOR surface).

Contract guarantees verified here:

- Route is registered at ``/api/v1/mobile/driver/route-share`` (no path param).
- The response matches the EXACT ``RouteShareResponse`` schema used by
  ``/driver/transports/{transport_id}/route-share`` — same 7 snake_case keys,
  same types.
- With a driver JWT + a current (non-terminal) trip → 200 + geometry for that
  trip (transport_id comes from the resolved trip, never from the client).
- With NO current transport → mirrors the existing route-share handler's
  empty behavior (HTTP 404).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.main import create_app
from config import Config

EXPECTED_KEYS = {
    "transport_id",
    "points",
    "instructions",
    "total_distance_meters",
    "total_duration_seconds",
    "generated_at",
    "ttl_seconds",
}

ROUTE_RESULT = {
    "distance_km": 1054.5,
    "duration_min": 600.0,
    "geometry": [(52.52, 13.405), (48.8566, 2.3522)],
    "instructions": [
        {"text": "Turn right", "distance_meters": 150.5, "point_index": 0},
        {"text": "Continue straight", "distance_meters": 800.0, "point_index": 1},
    ],
}


# ── Scripted DB double ───────────────────────────────────────────────────────
# Responds to the exact queries the endpoint issues:
#   1. users lookup in _resolve_driver_id
#   2. drivers lookup in _resolve_driver_id
#   3. the current-trip query (SELECT ... FROM trips ... driver_id = ?)

class _ScriptedDb:
    def __init__(self, current_trip_row: dict | None):
        self._current_trip_row = current_trip_row
        self.executed_sql: list[str] = []

    def execute(self, sql: str, params: tuple = ()):
        self.executed_sql.append(sql)
        if "FROM users" in sql:
            return _Cursor({"email": "driver@test.com"})
        if "FROM drivers" in sql:
            return _Cursor({"id": 5})
        if "FROM trips" in sql:
            return _Cursor(self._current_trip_row)
        return _Cursor(None)


class _Cursor:
    def __init__(self, row: dict | None):
        self._row = row

    def fetchone(self):
        return self._row


# ── App builder (driver JWT, scripted DB) ────────────────────────────────────

def _build_app(monkeypatch: pytest.MonkeyPatch, current_trip_row: dict | None) -> TestClient:
    monkeypatch.setattr(Config, "API_KEY", "")  # disable API-key middleware

    app = create_app()
    db = _ScriptedDb(current_trip_row)

    async def _override_get_db():
        yield db

    async def _mock_driver_user() -> dict:
        return {
            "id": 2,
            "email": "driver@test.com",
            "role": "driver",
            "is_admin": False,
            "company_id": 1,
            "timezone": "UTC",
        }

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _mock_driver_user
    client = TestClient(app)
    client._scripted_db = db  # type: ignore[attr-defined]
    return client


# ── Tests ────────────────────────────────────────────────────────────────────

class TestDriverRouteShareJwtEndpoint:
    """The JWT-resolved route-share endpoint honors the RouteShareResponse contract."""

    def test_route_registered_without_transport_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The new endpoint lives at ``/driver/route-share`` (no path param) and
        the old transport-id variant is still registered."""
        _ = _build_app(monkeypatch, current_trip_row=None)
        from backend.api.v1.mobile import router as mobile_router

        paths = {getattr(r, "path", "") for r in mobile_router.routes}
        assert "/mobile/driver/route-share" in paths
        assert "/mobile/driver/transports/{transport_id}/route-share" in paths

    def test_returns_same_schema_as_transport_id_variant(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With a current trip the response is a full ``RouteShareResponse`` —
        the same 7 snake_case keys as ``/driver/transports/{id}/route-share``."""
        client = _build_app(
            monkeypatch,
            current_trip_row={
                "id": 7,
                "place_of_loading": "Berlin",
                "delivery_country": "Paris",
                "loading_country": "",
            },
        )

        with patch(
            "backend.services.route_service.RouteService.calculate_route",
            return_value=ROUTE_RESULT,
        ):
            resp = client.get("/api/v1/mobile/driver/route-share")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body) == EXPECTED_KEYS, (
            f"RouteShareResponse keys mismatch: {sorted(set(body) ^ EXPECTED_KEYS)}"
        )

        # transport_id comes from the JWT-resolved trip — never from the client.
        assert body["transport_id"] == "7"
        assert isinstance(body["transport_id"], str)

        # Geometry + instructions match the RouteShareResponse types.
        assert len(body["points"]) == 2
        for point in body["points"]:
            assert set(point) == {"lat", "lng"}
            assert isinstance(point["lat"], float) and isinstance(point["lng"], float)
        assert len(body["instructions"]) == 2
        assert set(body["instructions"][0]) == {"text_key", "distance_meters", "point_index"}
        assert body["total_distance_meters"] == 1054.5 * 1000
        assert body["total_duration_seconds"] == int(600.0 * 60)
        assert body["ttl_seconds"] == 300
        assert body["generated_at"]  # ISO-8601 string

    def test_uses_the_drivers_current_trip_query(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The endpoint resolves the driver from the JWT and issues the same
        current-trip query as trip-overview (driver_id + company_id scoped,
        terminal statuses excluded)."""
        client = _build_app(
            monkeypatch,
            current_trip_row={"id": 7, "place_of_loading": "Berlin", "delivery_country": "Paris"},
        )

        with patch(
            "backend.services.route_service.RouteService.calculate_route",
            return_value=ROUTE_RESULT,
        ):
            resp = client.get("/api/v1/mobile/driver/route-share")

        assert resp.status_code == 200, resp.text
        trips_query = next(
            sql for sql in client._scripted_db.executed_sql if "FROM trips" in sql
        )
        assert "driver_id = ?" in trips_query
        assert "company_id = ?" in trips_query
        assert "DELIVERED" in trips_query  # terminal statuses excluded

    def test_no_current_transport_returns_404(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Mirrors the existing route-share handler's empty behavior: no
        current transport → HTTP 404 (not an all-null payload)."""
        client = _build_app(monkeypatch, current_trip_row=None)

        with patch(
            "backend.services.route_service.RouteService.calculate_route",
            return_value=ROUTE_RESULT,
        ):
            resp = client.get("/api/v1/mobile/driver/route-share")

        assert resp.status_code == 404, resp.text
        # The calculate_route mock must NOT have been reached (nothing to share).
        # Asserted via a fresh patch that fails if invoked:
        with patch(
            "backend.services.route_service.RouteService.calculate_route",
            side_effect=AssertionError("route must not be computed without a transport"),
        ):
            resp2 = client.get("/api/v1/mobile/driver/route-share")
        assert resp2.status_code == 404, resp2.text

    def test_geocoding_failure_returns_400(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A current trip without valid origin/destination addresses follows
        the existing handler's 400 behavior (no route to share)."""
        client = _build_app(
            monkeypatch,
            current_trip_row={"id": 7, "place_of_loading": "", "delivery_country": ""},
        )

        with patch(
            "backend.services.route_service.RouteService.calculate_route",
            return_value=ROUTE_RESULT,
        ):
            resp = client.get("/api/v1/mobile/driver/route-share")

        assert resp.status_code == 400, resp.text
